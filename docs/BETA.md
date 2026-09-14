# Qué falta para la beta (0.9)

Revisión hecha el 2026-09-13 sobre `main` (`c5ad9a6`) + la rama `feature/jetson-orin`.

## Para quién es la beta

NVIDIA y Microsoft ya venden equipos que corren IA en local, y mucha gente tiene GPUs
capaces de servir varios modelos. La beta tiene que funcionar **sin configurar nada** en
toda la familia NVIDIA:

| Familia | Ejemplos | Memoria | Qué espera el usuario |
|---|---|---|---|
| Laptop / PC RTX | RTX 4060 laptop, 4070, 5080, GTX 1650 | 4–16 GB dedicados | Instalar, elegir un modelo que quepa, chatear |
| Entusiasta | RTX 4090 / 5090, 2× GPU | 24–64 GB | Varios modelos a la vez, agentes, RAG sobre sus documentos |
| Memoria unificada | DGX Spark, laptops con N1X, Jetson Orin | 8–128 GB compartidos | Lo mismo, sin colgar el equipo |
| Servidor | B200 / H100 | 80–192 GB | Multiusuario; en la beta, Ollama; vLLM después |

## Estado actual

| Área | Estado | Nota |
|---|---|---|
| Detección de hardware | ✅ | Incluye Jetson / memoria unificada, también dentro de Docker |
| Compatibilidad VRAM | ✅ | Con aviso de memoria libre en unificada |
| Load / unload en Ollama | ✅ | Probado en Jetson Orin Nano real |
| Perfil por familia (`/platform`) | ✅ | Jetson, DGX Spark, GeForce, workstation, datacenter; varias GPUs |
| Telemetría en vivo (`/system`) | ✅ | nvidia-smi y sysfs de Jetson (W, °C, uso) |
| Chat con streaming | ✅ | `WebSocket /chat` y `POST /chat`; `magnus chat` |
| Medidor de tokens / ahorro vs nube | ✅ | Energía medida, amortización, tabla de precios versionada |
| Conversaciones persistentes | ✅ | SQLite en la carpeta de datos; `/conversations`, `/usage` |
| Descarga de modelos con progreso | ✅ | NDJSON; `magnus fetch` con barra |
| Catálogo recomendado por hardware | ✅ | `/catalog`, `magnus catalog` |
| Guarda de memoria al cargar | ✅ | Se niega en unificada, libera caché sin root, reintenta una vez |
| Configuración / carpeta de datos por SO | ✅ | `config.json` + variables de entorno; `/settings` |
| Skills | ✅ | `SKILL.md` con recarga en caliente; `/skills`, `magnus skill`; 3 incluidas |
| Memoria + RAG local | ✅ | Embeddings locales vía Ollama, SQLite; `/rag`, `/memory`, `magnus rag`/`mem` |
| Agentes con herramientas | ✅ | YAML, tool calling de Ollama, herramientas seguras; `/agents`, `magnus agent` |
| Auth si se expone en red | ✅ | Token obligatorio fuera de loopback; `magnus token new` |
| Cliente Flutter conectado | ✅ | Todas las secciones con la API real; probado contra el Jetson |
| Instalador | 🟡 | Scripts por usuario (Windows, Linux) y `.msix` de la app firmado con certificado de prueba; falta certificado real |
| Prueba e2e en vivo | ✅ | `scripts/e2e.py`: 19 ok en el Jetson Orin Nano (chat, RAG, agentes, cambios de modelo, concurrencia, token, persistencia) |
| CI verde | ✅ | ruff limpio, 264 tests |
| Contrato OpenAPI congelado | ✅ | `docs/api/openapi-v1.json`, versión `0.9.0b1` |

## Lo que queda abierto en la beta

- **Agentes con modelos pequeños**: el bucle funciona, pero por debajo de ~3 B el modelo no
  usa las herramientas de forma fiable (medido con qwen3:0.6b). Magnus lo avisa; validar
  con un modelo de 4 B o más en un equipo con memoria para él.
- **Instalador firmado** para Windows (hoy es un script de PowerShell) y paquete `.msix`
  de la app.
- **macOS**: la app compila, pero Magnus está pensado para NVIDIA; en Mac solo tiene
  sentido como cliente de un daemon remoto.

Hallazgos del Jetson (memoria, NvMap, versión de Ollama): [`JETSON.md`](JETSON.md).

## Plan, en orden

Cada hito entra con `core` + endpoint + CLI + tests, y se verifica en el Jetson.

1. **Plataforma y telemetría** — `GET /platform` (familia, runtimes, cuántos modelos,
   tamaño sugerido) y `GET /system` (uso de GPU, W, °C, memoria). Base del medidor.
2. **Modelos de verdad** — catálogo recomendado según el perfil, descarga con progreso
   por streaming, borrar, y negarse a cargar lo que no cabe en la memoria libre.
3. **Chat + medidor** — `WebSocket /chat` con tokens en vivo; al cerrar cada turno:
   tokens in/out, tok/s, tiempo al primer token, energía medida, coste local contra
   coste nube (tabla de precios versionada). Conversaciones en SQLite.
4. **Skills** — `skills/<nombre>/SKILL.md`, recarga en caliente, se inyectan en el chat.
5. **Memoria + RAG** — embeddings locales vía Ollama, SQLite, top-k por coseno.
6. **Agentes** — `agents/<nombre>.yaml`, loop con herramientas (skills, RAG, memoria).
7. **Configuración y seguridad** — carpeta de datos por SO, archivo de config, token
   obligatorio si el daemon escucha fuera de loopback.
8. **Cliente Flutter conectado** — chat, descargas, recursos en vivo, skills, RAG, agentes.
9. **Empaquetado** — instalador Windows (daemon + detección de Ollama), compose para
   Linux / Jetson / DGX Spark, guía de inicio por familia.
10. **Cierre** — CI verde, OpenAPI v1 congelado, versión `0.9.0b1`.

## Fuera de la beta

vLLM y TensorRT-LLM como backends, multiusuario/SSO, marketplace, app móvil, builds
firmados. El contrato de la beta tiene que dejarlos entrar sin romper nada.
