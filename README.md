# Magnus

> **SO de agentes _local-first_ sobre hardware NVIDIA.**
> El cerebro (núcleo + daemon) vive donde está la GPU y se programa en Python.
> La cara (CLI y app de escritorio Flutter; móvil después) habla con él por una
> única API local. Los datos del usuario nunca salen de su máquina — ese es el producto.

**Estado: beta `0.9.0b1`.** Chat con medidor de coste, modelos según tu hardware, skills,
documentos (RAG local), memoria y agentes con herramientas, en toda la familia NVIDIA:
laptops RTX, DGX Spark, Jetson Orin y servidores. **Instalar:** [`docs/INSTALL.md`](docs/INSTALL.md) ·
**Qué falta:** [`docs/BETA.md`](docs/BETA.md) · **API:** [`docs/api/openapi-v1.json`](docs/api/openapi-v1.json)

---

## 1. La idea en una frase

Las nuevas máquinas con GPU NVIDIA (RTX AI PCs, DGX Spark, servidores B200) pueden correr
modelos potentes en local, pero el software encima es pobre: te sirven el modelo y poco más.
**Magnus es la capa de agente que falta**: skills editables, memoria con mini-RAG local,
constructor de agentes, y un medidor de tokens/coste con el cálculo de _"cuánto te ahorras
frente a la nube"_. Todo corriendo en hardware propio, sin mandar datos a terceros.

El argumento de venta no es "otro wrapper de chat". Es **privacidad real + control de coste +
agentes propios**, sobre tu hardware. Eso es lo que paga una empresa que no puede mandar sus
datos a una API externa.

## 2. Principio de arquitectura: separa cerebro y cara

```
   HARDWARE NVIDIA            NÚCLEO MAGNUS (Python)        API LOCAL          CLIENTES
   (B200 / Spark / RTX)  ->   skills · memoria/RAG    ->  FastAPI       ->   CLI (Python)
                              agentes · medidor           HTTP + WS          Flutter desktop
   runtimes: ollama /                                                        Flutter móvil
   vLLM / TensorRT-LLM
```

- **Núcleo + daemon + CLI → Python.** Es donde vive todo el ecosistema de IA de NVIDIA
  (CUDA, vLLM, TensorRT-LLM, NIM, embeddings). El núcleo (`core/`) es lógica pura y testeable.
- **GUI multiplataforma → Flutter, pero como _cliente delgado_.** Flutter no toca el modelo;
  consume la API local. Con un solo código cubres escritorio (Win/Mac/Linux) y móvil
  ("controla tu servidor de IA desde el teléfono").
- **El contrato es la API local** (`daemon/`). Si la CLI, el escritorio y el móvil hablan todos
  por esa API, añadir Flutter es **añadir una vista, no reescribir el producto.**

> Por qué NO Dart/Flutter para el núcleo: Dart no tiene ecosistema de IA. Habría que
> reimplementar RAG/embeddings o llamar a Python igualmente. Dart en la cara, Python en el cerebro.

## 3. Cómo se montan los modelos

Magnus **no implementa inferencia**: orquesta runtimes existentes. El flujo de montaje es:

1. **Elegir destino** — la GPU real (`auto`) o un preset (`b200`, `dgx-spark`, `rtx-4090`…).
2. **Comprobar compatibilidad** — `magnus check <modelo> --target <destino> --quant <q>`
   estima la VRAM y da un veredicto antes de descargar nada (ver §4).
3. **Elegir runtime según el perfil de uso:**
   | Perfil | Runtime | Por qué |
   |---|---|---|
   | Desarrollo / 1 usuario | **Ollama** | Simple, GGUF, arranca en segundos. |
   | Servir a varios usuarios | **vLLM** | _Continuous batching_ + paged attention. **Backend principal en B200.** |
   | Máximo rendimiento | **TensorRT-LLM** | Lo más rápido en NVIDIA; más complejo de montar. |

   > Un B200 corriendo Ollama en single-stream está desaprovechado. En datacenter, vLLM/TRT-LLM.
4. **Servir** — el runtime levanta el modelo; el daemon de Magnus lo orquesta y mide el consumo.

Detalle completo del flujo y de la matriz runtime×cuantización en
[`docs/MODEL_MOUNTING.md`](docs/MODEL_MOUNTING.md).

## 4. Cómo se sabe si un modelo es compatible

Implementado en [`core/compatibility.py`](core/compatibility.py). Estimación de planificación
(no garantía; para producción, medir con el runtime real), pero distingue bien
_"ni de broma"_ de _"entra sobrado"_:

```
total_VRAM = (pesos + kv_cache) * 1.20 + 1 GiB
  pesos    = params * bytes_por_parámetro(cuant)       # fp16=2, fp8/q8=1, q6=0.75, q5=0.65, q4=0.5
  kv_cache = 2 * n_layers * n_kv_heads * head_dim * context * batch * 2 bytes
  *1.20    = activaciones + fragmentación + buffers del runtime
  +1 GiB   = contexto CUDA + workspace
```

El veredicto incluye: VRAM requerida, % de uso del destino, margen libre, runtimes capaces de
esa cuantización y — si no entra — **qué cuantización sí entraría** (`recommend_quant`).

Ejemplo:

```bash
magnus check llama-3.1-70b --target b200 --quant fp16     # ✓ entra, con margen
magnus check llama-3.1-405b --target b200 --quant fp16    # ✗ no entra -> sugiere q4 / multi-GPU
```

## 5. Quickstart

```bash
# 1. Clonar e instalar (en el server con GPU, o en la laptop para desarrollar el núcleo)
git clone https://github.com/HugoLifes/magnus.git && cd magnus
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e .

# 2. Probar el núcleo SIN GPU (usando presets)
magnus models
magnus check  llama-3.1-70b --target b200 --quant fp16
magnus quants llama-3.1-70b --target b200          # analiza TODAS las cuantizaciones

# 3. En la máquina con GPU
magnus hardware                                    # lee la GPU real
magnus pull meta-llama/Llama-3.1-8B                # descarga desde Hugging Face
magnus serve                                       # API local en http://127.0.0.1:8420 (/docs)

# 4. Despliegue en servidor (Docker + NVIDIA Container Toolkit)
docker compose -f deploy/docker-compose.yml up -d --build   # contenedor nim_magnus
```

## 5.1 Adquisición de modelos (Hugging Face) y análisis de cuantizaciones

Magnus integra la **CLI de Hugging Face** para traer pesos directamente al servidor
(`core/downloader.py`). No reimplementa la descarga: envuelve `hf download`.

```bash
# Descargar un repo completo, o solo una cuantización concreta con --include
magnus pull Qwen/Qwen2.5-32B-Instruct
magnus pull bartowski/Qwen2.5-32B-Instruct-GGUF --include "*Q4_K_M*.gguf"
magnus pull meta-llama/Llama-3.1-8B --dry-run     # muestra el comando sin descargar
```
> Repos privados/gated: `hf auth login` (o exporta `HF_TOKEN`) antes. Magnus no guarda credenciales.

Y para **darle alcance al CLI sobre cuantizaciones**, `magnus quants` cruza el modelo con el
destino y dice qué formatos entran y en qué runtime:

```
$ magnus quants llama-3.1-70b --target b200
 Cuant  VRAM req.  % destino  Margen  ¿Entra?  Runtimes
 fp16    161.8       84.3%     30.2     ✓       vllm, trtllm
 fp8      91.0       47.4%    101.0     ✓       vllm, trtllm
 q8       91.0       47.4%    101.0     ✓       ollama, vllm
 q6       70.6       36.8%    121.4     ✓       ollama
 q4       50.3       26.2%    141.7     ✓       ollama, vllm, trtllm
```
> Que una cuant "entre" no garantiza que exista un repo prequantizado: revisa en HF o baja el
> formato concreto con `magnus pull --include`.

## 6. Estructura del repositorio

```
magnus/
├── core/                  # Lógica pura, sin framework, testeable sin GPU
│   ├── hardware.py        #   GPU real (incluye Jetson / memoria unificada) + presets
│   ├── platform.py        #   familia NVIDIA y cómo conviene servir en ella
│   ├── telemetry.py       #   uso, W y °C (nvidia-smi o sysfs del Jetson)
│   ├── compatibility.py   #   ¿cabe el modelo? — VRAM, guarda de memoria, cuants
│   ├── catalog.py         #   modelos de Ollama recomendados según la memoria real
│   ├── runtime_manager.py #   descargar, cargar, liberar (Ollama; vLLM después)
│   ├── reclaim.py         #   libera la caché antes de cargar en memoria unificada
│   ├── chat.py            #   chat en streaming con skills, RAG y medición
│   ├── metering.py        #   energía medida, coste local vs nube, ahorro
│   ├── skills.py          #   SKILL.md con recarga en caliente
│   ├── rag.py             #   colecciones, embeddings locales, memoria
│   ├── agent.py           #   agentes YAML con herramientas seguras
│   ├── store.py           #   conversaciones y registro del medidor (SQLite)
│   ├── config.py          #   carpeta de datos por SO y ajustes
│   └── security.py        #   token de acceso fuera de loopback
├── daemon/app.py          # API local (FastAPI + WebSocket) — contrato de todos los clientes
├── cli/main.py            # CLI (Typer): platform, catalog, fetch, chat, rag, agent…
├── skills/  agents/       # skills y agentes incluidos
├── clients/desktop/       # app Flutter (Windows / macOS / Linux)
├── deploy/                # Docker (servidor y Jetson) e instaladores Windows/Linux
├── docs/                  # INSTALL, BETA, JETSON, API, arquitectura y handoff
└── tests/                 # 264 tests, corren sin GPU
```

## 7. Estado y hoja de ruta (resumen)

- **Fase 0 ✅** núcleo, daemon y CLI; compatibilidad de VRAM.
- **Fase 1 ✅** runtime manager, chat en streaming con medidor de coste, skills, memoria y RAG
  local, agentes con herramientas, token de acceso. Probado en un Jetson Orin Nano real.
- **Fase 2 ✅ (beta)** app de escritorio Flutter conectada a toda la API.
- **Después de la beta:** vLLM y TensorRT-LLM, instalador firmado, app móvil, marketplace de
  skills, edición enterprise on-prem.

Pendientes de la beta en [`docs/BETA.md`](docs/BETA.md); hoja de ruta en [`docs/ROADMAP.md`](docs/ROADMAP.md).

## 8. Modelo de negocio (resumen)

| Capa | Qué | Quién paga |
|---|---|---|
| OSS | CLI + núcleo + RAG local | Gratis — embudo de comunidad |
| Pro | sync entre máquinas, backup cifrado, dashboard de coste avanzado | prosumidor / dev |
| Marketplace | skills/agentes de terceros (comisión) | creadores + usuarios |
| **Enterprise on-prem** | SSO, auditoría, multi-usuario, soporte | **empresas con datos sensibles ← el dinero** |
| Servicios | fine-tuning + agentes a medida sobre Magnus | clientes de consultoría |

## 9. División de trabajo (humano + IA)

- **Backend (núcleo, daemon, runtimes, skills, RAG, medidor):** lo ejecuta una IA siguiendo
  [`docs/AGENT_HANDOFF.md`](docs/AGENT_HANDOFF.md), que contiene el plan, las convenciones y los
  criterios de aceptación.
- **Frontend (Flutter, escritorio y móvil):** se desarrolla en otra sesión, consumiendo la API
  local del daemon. No empieza hasta que la Fase 1 estabilice el contrato de la API.

## 10. Convención de despliegue

El contenedor se llama **`nim_magnus`**, siguiendo la convención de la organización
(`nim_` + nombre del proyecto). Desplegar solo en **servidores autorizados**.
