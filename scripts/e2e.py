"""Prueba de extremo a extremo contra un daemon de Magnus en vivo.

Recorre la API como lo haría un usuario — hardware, modelos, chat, skills,
documentos, memoria, agentes, medidor — y además fuerza lo que falla en equipos
reales: cambios de modelo seguidos (en memoria compartida cada cambio libera
caché y recarga) y peticiones simultáneas. Limpia todo lo que crea.

Sirve para cualquier equipo de la familia NVIDIA:

    python scripts/e2e.py --modelo qwen3:0.6b
    python scripts/e2e.py --url http://jetson:8420 --token XXX --modelo qwen3:4b
    docker exec nim_magnus python scripts/e2e.py --modelo qwen3:0.6b --json /app/data/e2e.json

Sale con código 1 si alguna comprobación falla. Los avisos (p. ej. un modelo
pequeño que no usa la herramienta) no cuentan como fallo: son calidad del modelo,
no del sistema.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import traceback
from collections.abc import Callable
from dataclasses import asdict, dataclass, field

import httpx
from websockets.sync.client import connect

PREFIX = "e2e-prueba"
SECRET = "4711"


@dataclass
class Check:
    name: str
    status: str = "ok"          # ok | aviso | fallo | omitida
    seconds: float = 0.0
    detail: str = ""
    data: dict = field(default_factory=dict)


class Failed(Exception):
    pass


class Warn(Exception):
    pass


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise Failed(message)


class E2E:
    def __init__(self, url: str, token: str | None, model: str, agent_model: str,
                 cycles: int, allow_downloads: bool) -> None:
        self.url = url.rstrip("/")
        self.token = token
        self.model = model
        self.agent_model = agent_model
        self.cycles = cycles
        self.allow_downloads = allow_downloads
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self.http = httpx.Client(base_url=self.url, headers=headers,
                                 timeout=httpx.Timeout(30.0, read=900.0))
        self.checks: list[Check] = []
        self.conversations: list[str] = []

    # --- utilidades ---------------------------------------------------------

    def run(self, name: str, fn: Callable[[Check], None]) -> Check:
        check = Check(name)
        start = time.monotonic()
        try:
            fn(check)
        except Warn as exc:
            check.status, check.detail = "aviso", str(exc)
        except Failed as exc:
            check.status, check.detail = "fallo", str(exc)
        except Exception as exc:  # noqa: BLE001 — la prueba reporta, no se cae
            check.status = "fallo"
            check.detail = f"{type(exc).__name__}: {exc}"
            check.data["traceback"] = traceback.format_exc(limit=3)
        check.seconds = round(time.monotonic() - start, 2)
        self.checks.append(check)
        mark = {"ok": "✓", "aviso": "!", "fallo": "✗", "omitida": "-"}[check.status]
        line = f"{mark} {name:<42} {check.seconds:>7.2f} s"
        print(f"{line}  {check.detail}" if check.detail else line, flush=True)
        return check

    def get(self, path: str, **kw) -> dict:
        r = self.http.get(path, **kw)
        expect(r.status_code == 200, f"GET {path} → {r.status_code}: {r.text[:200]}")
        return r.json()

    def send(self, method: str, path: str, body: dict | None = None, status: int = 200) -> dict:
        r = self.http.request(method, path, json=body)
        expect(r.status_code == status, f"{method} {path} → {r.status_code}: {r.text[:300]}")
        return r.json() if r.content else {}

    def ndjson(self, path: str, body: dict | None = None) -> list[dict]:
        events = []
        with self.http.stream("POST", path, json=body) as r:
            expect(r.status_code == 200, f"POST {path} → {r.status_code}")
            for line in r.iter_lines():
                if line.strip():
                    events.append(json.loads(line))
        return events

    def ws_turn(self, body: dict) -> list[dict]:
        ws_url = self.url.replace("http", "ws", 1) + "/chat"
        if self.token:
            ws_url += f"?token={self.token}"
        events = []
        with connect(ws_url, open_timeout=15) as ws:
            ws.send(json.dumps(body))
            while True:
                event = json.loads(ws.recv(timeout=900))
                events.append(event)
                if event["type"] in ("done", "error"):
                    break
        return events

    def memory_free(self) -> float | None:
        try:
            return self.get("/system").get("ram_available_gib")
        except Failed:
            return None

    # --- comprobaciones -------------------------------------------------------

    def health(self, c: Check) -> None:
        body = self.get("/health")
        expect(body["status"] == "ok", "el daemon no responde ok")
        expect(body["ollama"], "Ollama no está disponible")
        c.detail = f"daemon {body['version']} · Ollama {body.get('ollama_version')}"

    def platform(self, c: Check) -> None:
        p = self.get("/platform")
        expect(p["family"] != "unknown", "no se reconoció la GPU NVIDIA")
        expect(p["total_memory_gib"] > 0, "memoria total en 0")
        c.detail = (f"{p['family']} · {p['total_memory_gib']} GiB"
                    f"{' unificada' if p['unified_memory'] else ''} · hasta ~{p['suggested_max_params_b']} B")
        c.data = p

    def system(self, c: Check) -> None:
        s = self.get("/system")
        expect(bool(s["gpus"]), "sin GPUs en la telemetría")
        g = s["gpus"][0]
        c.detail = (f"GPU {g.get('utilization_pct')} % · {s.get('power_w')} W · "
                    f"{g.get('temperature_c')} °C · RAM libre {s.get('ram_available_gib')} GiB")
        if s.get("power_w") is None:
            raise Warn(c.detail + " · sin sensor de potencia: el coste de energía será 0")

    def catalog(self, c: Check) -> None:
        cat = self.get("/catalog")
        fits = [m["id"] for m in cat["models"] if m["fits"]]
        expect(bool(cat["models"]), "catálogo vacío")
        c.detail = f"{len(fits)} de {len(cat['models'])} caben en {cat['usable_gib']} GiB"
        if not fits:
            raise Warn(c.detail + " · no cabe ninguno ahora mismo (¿memoria ocupada?)")

    def ensure_model(self, model: str) -> Callable[[Check], None]:
        def check(c: Check) -> None:
            local = [m["model_id"] for m in self.get("/models/local")["models"]]
            if model in local or f"{model}:latest" in local:
                c.detail = "ya descargado"
                return
            if not self.allow_downloads:
                raise Failed(f"{model} no está descargado (usa --descargar)")
            events = self.ndjson(f"/models/{model}/pull")
            expect(events and events[-1]["status"] == "success",
                   f"descarga fallida: {events[-1] if events else 'sin eventos'}")
            c.detail = f"descargado ({len(events)} eventos de progreso)"
        return check

    def load(self, c: Check) -> None:
        body = self.send("POST", f"/models/{self.model}/load", {"pull_if_missing": False})
        loaded = [m["model_id"] for m in self.get("/models/loaded")["loaded"]]
        expect(any(self.model in m for m in loaded), f"{self.model} no aparece cargado")
        c.detail = f"{body.get('size_vram_gib')} GiB en memoria"
        if body.get("notes"):
            raise Warn(c.detail + " · " + " ".join(body["notes"]))

    def chat_ws(self, c: Check) -> None:
        first = self.ws_turn({"model": self.model, "think": False,
                              "message": "Responde solo con la palabra: hola"})
        expect(first[-1]["type"] == "done", f"turno 1: {first[-1]}")
        tokens = [e for e in first if e["type"] == "token"]
        expect(len(tokens) > 0, "no llegaron tokens en vivo")
        conv = first[-1]["conversation_id"]
        self.conversations.append(conv)
        second = self.ws_turn({"model": self.model, "conversation_id": conv, "think": False,
                               "message": "Ahora responde solo con: adiós"})
        expect(second[-1]["type"] == "done", f"turno 2: {second[-1]}")
        detail = self.get(f"/conversations/{conv}")
        expect(len(detail["messages"]) == 4, f"se esperaban 4 mensajes, hay {len(detail['messages'])}")
        m = second[-1]["metrics"]
        expect(m["tokens_out"] > 0, "métricas sin tokens de salida")
        c.detail = (f"{len(tokens)} eventos token · {m['tokens_per_s']} tok/s · "
                    f"1er token {m['ttft_s']} s · {m['avg_power_w']} W · ahorro ${m['savings_usd']:.6f}")
        c.data = m

    def think(self, c: Check) -> None:
        on = self.send("POST", "/chat", {"model": self.model, "message": "¿Cuánto es 2+2?"})
        off = self.send("POST", "/chat", {"model": self.model, "think": False,
                                          "message": "¿Cuánto es 2+2?"})
        self.conversations += [on["conversation_id"], off["conversation_id"]]
        a, b = on["metrics"]["tokens_out"], off["metrics"]["tokens_out"]
        c.detail = f"con razonamiento {a} tok · sin razonamiento {b} tok"

    def skills(self, c: Check) -> None:
        builtin = {s["name"] for s in self.get("/skills")["skills"]}
        expect({"resumir", "traducir", "revisar-codigo"} <= builtin, f"faltan incluidas: {builtin}")
        name = PREFIX
        self.send("PUT", f"/skills/{name}", {
            "description": "Skill de prueba", "triggers": ["palabra-magica-e2e"],
            "body": "Termina tu respuesta con la palabra PRUEBA.",
        })
        try:
            resolved = self.send("POST", "/skills/resolve", {"message": "usa palabra-magica-e2e"})
            expect(resolved["skills"] == [name], f"resolve devolvió {resolved}")
            events = self.ws_turn({"model": self.model, "think": False,
                                   "message": f"/{name} di hola"})
            expect(events[-1]["type"] == "done", f"chat con skill: {events[-1]}")
            expect(events[0]["skills"] == [name], f"la skill no se aplicó: {events[0]}")
            self.conversations.append(events[-1]["conversation_id"])
            c.detail = "crear · resolver · aplicar en chat · borrar"
        finally:
            self.http.delete(f"/skills/{name}")

    def rag(self, c: Check) -> None:
        name = PREFIX
        self.http.delete(f"/rag/collections/{name}")
        self.send("POST", "/rag/collections", {"name": name, "chunk_chars": 400})
        try:
            text = ("Manual de la prueba de Magnus.\n\n"
                    f"El código secreto de la bóveda es {SECRET}. Solo lo conoce el equipo.\n\n"
                    "La cafetería abre a las ocho y cierra a las cinco.")
            ingest = self.send("POST", "/rag/ingest", {"collection": name, "text": text,
                                                       "source": "manual-e2e"})
            expect(ingest["indexed"] == 1 and ingest["chunks"] >= 1, f"ingesta: {ingest}")
            hits = self.send("POST", "/rag/search", {"collection": name,
                                                     "query": "¿cuál es el código secreto?", "k": 2})["hits"]
            expect(bool(hits) and SECRET in hits[0]["text"], f"búsqueda no encontró el dato: {hits}")
            events = self.ws_turn({"model": self.model, "collection": name, "rag_k": 2,
                                   "think": False,
                                   "message": "Según los documentos, ¿cuál es el código secreto de la bóveda?"})
            expect(events[-1]["type"] == "done", f"chat con RAG: {events[-1]}")
            expect(bool(events[0]["sources"]), "el chat no trajo fuentes")
            self.conversations.append(events[-1]["conversation_id"])
            answer = events[-1]["content"]
            c.detail = f"ingesta {ingest['chunks']} fragmentos · búsqueda {hits[0]['score']} · fuentes en chat"
            if SECRET not in answer:
                raise Warn(c.detail + f" · el modelo no citó {SECRET}: «{answer[:80]}»")
        finally:
            self.http.delete(f"/rag/collections/{name}")

    def memory(self, c: Check) -> None:
        added = self.send("POST", "/memory", {"text": "La prueba e2e usa el color turquesa"})
        try:
            hits = self.send("POST", "/memory/search", {"query": "¿qué color usa la prueba e2e?"})["memories"]
            expect(any(h["id"] == added["id"] for h in hits), f"no se encontró la memoria: {hits}")
            c.detail = f"guardar · buscar (score {hits[0].get('score')}) · borrar"
        finally:
            self.http.delete(f"/memory/{added['id']}")

    def agent(self, c: Check) -> None:
        tools = {t["name"] for t in self.get("/tools")["tools"]}
        expect("calcular" in tools, f"faltan herramientas: {tools}")
        name = PREFIX
        self.send("PUT", f"/agents/{name}", {
            "description": "Agente de prueba", "tools": ["calcular"], "max_steps": 4,
            "system": "Para cualquier cuenta usa SIEMPRE la herramienta calcular y responde con el resultado.",
        })
        try:
            events = self.ndjson(f"/agents/{name}/run", {
                "message": "¿Cuánto es 1250 multiplicado por 1.16, más 80?",
                "model": self.agent_model,
            })
            expect(events[-1]["type"] == "done", f"agente: {events[-1]}")
            calls = [e for e in events if e["type"] == "tool_call"]
            results = [e["result"] for e in events if e["type"] == "tool_result"]
            done = events[-1]
            self.conversations.append(done["conversation_id"])
            m = done["metrics"]
            expressions = [e["arguments"].get("expresion") for e in calls]
            c.detail = (f"{self.agent_model} · {m['steps']} pasos · herramientas {expressions} → "
                        f"{results} · {m['duration_s']} s · respuesta «{done['content'][:60]}»")
            c.data = {"calls": calls, "results": results}
            if not calls:
                raise Warn(c.detail + " · el modelo no usó la calculadora")
            if not any("1530" in r for r in results):
                raise Warn(c.detail + " · usó la herramienta con una expresión incorrecta")
            if "1530" not in done["content"]:
                raise Warn(c.detail + " · calculó bien pero la respuesta no lo refleja")
        finally:
            self.http.delete(f"/agents/{name}")

    def stability(self, c: Check) -> None:
        """Alterna embeddings y chat: en equipos de un solo modelo cada vuelta cambia de modelo."""
        name = f"{PREFIX}-estabilidad"
        self.http.delete(f"/rag/collections/{name}")
        self.send("POST", "/rag/collections", {"name": name})
        before = self.memory_free()
        times = []
        try:
            self.send("POST", "/rag/ingest", {"collection": name, "source": "e2e",
                                              "text": "Magnus corre modelos en hardware NVIDIA."})
            for i in range(self.cycles):
                t0 = time.monotonic()
                hits = self.send("POST", "/rag/search", {"collection": name, "query": "¿dónde corre Magnus?"})
                expect(bool(hits["hits"]), f"vuelta {i + 1}: búsqueda vacía")
                r = self.send("POST", "/chat", {"model": self.model, "think": False,
                                                "message": f"Vuelta {i + 1}: di ok"})
                self.conversations.append(r["conversation_id"])
                times.append(round(time.monotonic() - t0, 1))
        finally:
            self.http.delete(f"/rag/collections/{name}")
        after = self.memory_free()
        c.detail = (f"{self.cycles} vueltas embeddings↔chat · s/vuelta {times} · "
                    f"RAM libre {before} → {after} GiB")
        c.data = {"seconds": times, "free_before": before, "free_after": after}

    def concurrency(self, c: Check) -> None:
        async def turn(i: int) -> list[dict]:
            return await asyncio.to_thread(self.ws_turn, {
                "model": self.model, "think": False, "message": f"Cliente {i}: di hola"})

        async def both() -> list[list[dict]]:
            return await asyncio.gather(turn(1), turn(2))

        t0 = time.monotonic()
        results = asyncio.run(both())
        for i, events in enumerate(results, 1):
            expect(events[-1]["type"] == "done", f"cliente {i}: {events[-1]}")
            self.conversations.append(events[-1]["conversation_id"])
        c.detail = f"2 chats simultáneos completados en {time.monotonic() - t0:.1f} s"

    def settings_roundtrip(self, c: Check) -> None:
        original = self.get("/settings")["electricity_usd_per_kwh"]
        try:
            changed = self.send("PUT", "/settings", {"electricity_usd_per_kwh": 0.321})
            expect(changed["electricity_usd_per_kwh"] == 0.321, "no se guardó la tarifa")
        finally:
            self.send("PUT", "/settings", {"electricity_usd_per_kwh": original})
        c.detail = "cambiar y restaurar tarifa eléctrica"

    def usage(self, c: Check) -> None:
        u = self.get("/usage")
        expect(u["turns"] > 0, "el medidor no registró respuestas")
        c.detail = (f"{u['turns']} respuestas · {u['tokens_out']} tokens · {u['energy_wh']} Wh · "
                    f"local ${u['local_cost_usd']:.6f} · nube ${u['cloud_cost_usd']:.6f} · "
                    f"ahorro ${u['savings_usd']:.6f}")

    def token_required(self, c: Check) -> None:
        r = httpx.get(f"{self.url}/platform", timeout=10)
        expect(r.status_code == 401, f"sin token debería dar 401 y dio {r.status_code}")
        c.detail = "sin token → 401, con token → 200"

    def cleanup(self, c: Check) -> None:
        for conv in self.conversations:
            self.http.delete(f"/conversations/{conv}")
        c.detail = f"{len(self.conversations)} conversaciones de prueba borradas"


def main() -> int:
    parser = argparse.ArgumentParser(description="Prueba de extremo a extremo de Magnus.")
    parser.add_argument("--url", default="http://127.0.0.1:8420")
    parser.add_argument("--token", default=None)
    parser.add_argument("--modelo", required=True, help="Modelo de chat (descargado o con --descargar).")
    parser.add_argument("--agente-modelo", default=None, help="Modelo para el agente (por omisión, --modelo).")
    parser.add_argument("--vueltas", type=int, default=5, help="Vueltas de la prueba de estabilidad.")
    parser.add_argument("--descargar", action="store_true", help="Descargar los modelos que falten.")
    parser.add_argument("--rapido", action="store_true", help="Sin estabilidad ni concurrencia.")
    parser.add_argument("--json", default=None, help="Guardar el informe en este archivo.")
    args = parser.parse_args()

    e2e = E2E(args.url, args.token, args.modelo, args.agente_modelo or args.modelo,
              args.vueltas, args.descargar)
    print(f"Magnus e2e · {args.url} · modelo {args.modelo}\n")
    started = time.monotonic()

    health = e2e.run("salud del daemon y Ollama", e2e.health)
    if health.status == "fallo":
        return 1
    e2e.run("plataforma (familia NVIDIA)", e2e.platform)
    e2e.run("telemetría en vivo", e2e.system)
    e2e.run("catálogo según la memoria", e2e.catalog)
    e2e.run(f"modelo {args.modelo} descargado", e2e.ensure_model(args.modelo))
    e2e.run("modelo de embeddings descargado", e2e.ensure_model("nomic-embed-text"))
    if e2e.agent_model != args.modelo:
        e2e.run(f"modelo {e2e.agent_model} descargado", e2e.ensure_model(e2e.agent_model))
    e2e.run("cargar modelo con guarda de memoria", e2e.load)
    e2e.run("chat por WebSocket (2 turnos)", e2e.chat_ws)
    e2e.run("razonamiento encendido/apagado", e2e.think)
    e2e.run("skills: crear, aplicar, borrar", e2e.skills)
    e2e.run("documentos (RAG) en el chat", e2e.rag)
    e2e.run("memoria", e2e.memory)
    e2e.run("agente con calculadora", e2e.agent)
    if not args.rapido:
        e2e.run("estabilidad: cambios de modelo", e2e.stability)
        e2e.run("concurrencia: 2 chats a la vez", e2e.concurrency)
    e2e.run("ajustes del medidor", e2e.settings_roundtrip)
    e2e.run("medidor acumulado", e2e.usage)
    if args.token:
        e2e.run("token de acceso", e2e.token_required)
    e2e.run("limpieza", e2e.cleanup)

    counts = {s: sum(1 for c in e2e.checks if c.status == s) for s in ("ok", "aviso", "fallo")}
    total = round(time.monotonic() - started, 1)
    print(f"\n{counts['ok']} ok · {counts['aviso']} avisos · {counts['fallo']} fallos · {total} s")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"url": args.url, "model": args.modelo, "seconds": total, "summary": counts,
                       "checks": [asdict(c) for c in e2e.checks]}, f, indent=2, ensure_ascii=False)
    return 1 if counts["fallo"] else 0


if __name__ == "__main__":
    sys.exit(main())
