# Handoff para la IA ejecutora del backend

Este documento es el punto de entrada si vas a **construir el backend de Magnus**. Léelo
entero antes de tocar código. El frontend (Flutter) se hace en otra sesión y no es tu tarea.

## 0. Contexto en 60 segundos

Magnus es un SO de agentes local-first. El núcleo (`core/`) es Python puro; el daemon
(`daemon/`) lo expone por una API local (FastAPI); la CLI (`cli/`) y, más tarde, clientes
Flutter, consumen esa API. **El contrato de la API es sagrado**: todo cliente depende de él.

Hardware de destino real del proyecto: un **servidor con GPU NVIDIA B200** (~192 GiB HBM3e).
El desarrollo del núcleo se puede hacer sin GPU usando los presets de `core/hardware.py`.

## 1. Reglas que no se rompen

1. **La lógica vive en `core/`.** El daemon y la CLI son envoltorios delgados. Si te ves
   metiendo cálculo en `daemon/app.py`, muévelo a `core/`.
2. **`core/` no importa de `daemon/` ni de `cli/`.** Dependencia en un solo sentido.
3. **`core/` debe correr y testearse SIN GPU.** Usa presets/inyección, nunca asumas `nvidia-smi`.
4. **No rompas el contrato de la API.** Añadir endpoints/campos: sí. Cambiar o quitar lo
   existente: solo con versión nueva y nota en el PR.
5. **Local-first y privacidad.** Nada de telemetría que mande datos del usuario fuera. Si una
   feature requiere salir a la red (p. ej. fallback a nube), es **opt-in explícito**.
6. **Convención de nombres.** Contenedores/servicios con prefijo `nim_` + nombre del proyecto
   (convención de la organización): este es `nim_magnus`. Despliega solo en servidores autorizados.
7. **Convenciones de estilo:** ver [`CONVENTIONS.md`](CONVENTIONS.md). Español en docs y
   mensajes de usuario; inglés en identificadores de código.

## 2. Qué ya está hecho (Fase 0)

- `core/hardware.py` — detección de GPU + presets de destino.
- `core/model_registry.py` — metadatos de modelos para el cálculo de memoria.
- `core/compatibility.py` — estimación de VRAM + veredicto + recomendación de cuantización.
- `core/compatibility.py` — incluye `quant_matrix()` (analiza todas las cuantizaciones).
- `core/downloader.py` — descarga de modelos envolviendo la CLI de Hugging Face.
- `core/runtimes.py` — abstracción de runtimes y soporte de cuantizaciones.
- `daemon/app.py` — endpoints de solo lectura: `/health /hardware /models /compatibility`.
- `cli/main.py` — `magnus hardware | models | check | quants | pull | serve`.
- `deploy/` — Dockerfile + compose (`nim_magnus`).

## 3. Qué construir (Fase 1) — en orden

Cada bloque: implementación en `core/`, endpoints en `daemon/`, comando en `cli/`, y tests.

### 3.1 Runtime manager (montar modelos de verdad)
- `core/runtime_manager.py`: interfaz `serve(model, quant, runtime, context)` →
  arranca/para un backend (empieza por **Ollama** vía su HTTP API; deja `vLLM` detrás de la
  misma interfaz). Estado de modelos cargados.
- API: `POST /models/{id}/load`, `POST /models/{id}/unload`, `GET /models/loaded`.
- CLI: `magnus load <model>`, `magnus unload <model>`, `magnus ps`.
- **Aceptación:** cargar `llama-3.1-8b` en Ollama y responder a un prompt por la API.

### 3.2 Chat + medidor de tokens (el diferenciador)
- `core/metering.py`: cuenta tokens (in/out) con el tokenizer del modelo, mide tokens/seg, y
  calcula **coste estimado local** (amortización HW + energía) vs **coste nube equivalente**
  (tabla de precios por proveedor). Devuelve "ahorro".
- API: `WebSocket /chat` con streaming de tokens; cada respuesta cierra con el resumen de medición.
- CLI: `magnus chat <model>`.
- **Aceptación:** una conversación muestra tokens en vivo y, al terminar, "ahorro vs nube: $X".

### 3.3 Skills (crear / editar / hot-reload)
- Formato: archivo `skills/<nombre>/SKILL.md` con frontmatter YAML (nombre, descripción,
  triggers, herramientas) + cuerpo en Markdown. Mismo espíritu que las skills de Claude Code.
- `core/skills.py`: cargar, validar, recargar en caliente, resolver qué skill aplica.
- API: `GET/POST/PUT /skills`, `POST /skills/reload`.
- CLI: `magnus skill new|edit|list|test`.

### 3.4 Memoria + mini-RAG local
- Store: **SQLite con `sqlite-vec`** (un archivo, cero servidores) o LanceDB.
- Embeddings **locales** (p. ej. `nomic-embed-text` / `bge-m3` vía Ollama). Nunca remoto por defecto.
- `core/memory.py`: memoria de hechos cortos + RAG sobre documentos del usuario
  (`magnus mem add ./docs`). Recuperación top-k por similitud.
- API: `POST /memory`, `POST /memory/search`, `POST /rag/ingest`.

### 3.5 Runtime de agentes (que el usuario cree el suyo)
- Definición declarativa `agents/<nombre>.yaml`: modelo, system prompt, skills habilitadas,
  herramientas, límites de tokens/coste.
- `core/agent.py`: loop de agente (modelo ↔ herramientas) reutilizando skills, memoria y medidor.
- API: `POST /agents/{name}/run`. CLI: `magnus agent run <name>`.

### 3.6 Auto-registro de modelos desde Hugging Face
- Hoy `model_registry` es manual. Tras `magnus pull`, leer el `config.json` del repo y poblar un
  `ModelSpec` automáticamente (n_layers, hidden, n_heads, n_kv_heads, context). Mapear nombres de
  campo según arquitectura (llama/qwen/mistral/mixtral). Así `check`/`quants` funcionan con
  cualquier modelo descargado, no solo los del registro embebido.
- Exponer además `pull` y `quants` por la API del daemon para que los clientes Flutter los usen.

## 4. Cómo verificar tu trabajo

- `pip install -e ".[dev]" && pytest` debe pasar sin GPU.
- `magnus check llama-3.1-70b --target b200` debe dar un veredicto coherente.
- `magnus serve` levanta la API; `GET /health` responde `ok`.
- Cada feature nueva entra con: función en `core/`, endpoint, comando CLI y test.

## 5. Cuando termines la Fase 1

Estabiliza y documenta el contrato de la API (FastAPI ya genera `/openapi.json`). Ese OpenAPI
es lo que la sesión de Flutter usará para generar el cliente. Avisa en el README qué endpoints
están congelados.
