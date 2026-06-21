# Roadmap

Estado: `Fase 0` entregada (esqueleto). `Fase 1` es el grueso del backend.

## Fase 0 — Núcleo + esqueleto  ✅ (este commit)
- [x] `core/hardware.py` — detección de GPU + presets de destino
- [x] `core/model_registry.py` — metadatos de modelos
- [x] `core/compatibility.py` — cálculo de VRAM, veredicto, recomendación de cuant
- [x] `core/runtimes.py` — abstracción de runtimes
- [x] `daemon/app.py` — API de solo lectura (`/health /hardware /models /compatibility`)
- [x] `cli/main.py` — `hardware | models | check | serve`
- [x] `deploy/` — Dockerfile + compose (`magnus-daemon`)
- [ ] tests de `core/` (siguiente: añadir `tests/` y CI)

## Fase 1 — Backend funcional (lo ejecuta la IA, ver AGENT_HANDOFF)
- [ ] Runtime manager: load/unload real (Ollama → vLLM) `[3.1]`
- [ ] Chat + medidor de tokens/coste con WebSocket streaming `[3.2]`  ← diferenciador
- [ ] Skills: crear/editar/hot-reload `[3.3]`
- [ ] Memoria + mini-RAG local (sqlite-vec + embeddings locales) `[3.4]`
- [ ] Runtime de agentes declarativo (YAML) `[3.5]`
- [ ] Congelar y documentar el contrato de la API (OpenAPI)

## Fase 2 — Cliente Flutter de escritorio (otra sesión)
- [ ] Generar cliente desde el OpenAPI del daemon
- [ ] Vistas: chat, editor de skills, dashboard de coste/ahorro, gestor de modelos
- [ ] Builds firmados Win/Mac/Linux

## Fase 3 — Producto
- [ ] App móvil Flutter (conexión al server por red local / túnel)
- [ ] Marketplace de skills/agentes
- [ ] Edición enterprise on-prem: SSO, auditoría, multi-usuario
- [ ] Empaquetado/instalador del daemon

## Hitos de validación de negocio
1. Demo del **medidor de ahorro vs nube** (Fase 1.2) → contenido para captar comunidad.
2. Primer agente útil de extremo a extremo (Fase 1.5) → caso de uso real.
3. Primer despliegue on-prem en cliente con datos sensibles → validación de pago.
