# Arquitectura

## Capas (de hardware a negocio)

```
┌─────────────────────────────────────────────────────────────┐
│ CAPA DE NEGOCIO   Pro · Marketplace · Enterprise on-prem      │
├─────────────────────────────────────────────────────────────┤
│ INTERFACES        CLI · TUI · Dashboard web · App Flutter     │
├─────────────────────────────────────────────────────────────┤
│ API LOCAL         FastAPI — HTTP + WebSocket (contrato único) │
├─────────────────────────────────────────────────────────────┤
│ NÚCLEO MAGNUS     skills · memoria/RAG · agentes · medidor    │
├─────────────────────────────────────────────────────────────┤
│ RUNTIMES          Ollama · vLLM · TensorRT-LLM (+ fallback)   │
├─────────────────────────────────────────────────────────────┤
│ HARDWARE NVIDIA   B200 · DGX Spark · RTX                       │
└─────────────────────────────────────────────────────────────┘
```

Cada capa solo conoce la de abajo. Los clientes solo conocen la **API local**.

## Topología cliente/servidor

El daemon corre en la máquina con GPU. Los clientes (CLI local, Flutter de escritorio en otra
máquina, Flutter móvil) se conectan por la API local:

- En la **misma máquina**: `127.0.0.1:8420`.
- Desde **otra máquina de la red** (móvil → server): publicar el puerto con **auth + firewall**,
  o exponerlo por un túnel seguro. Nunca abrir el daemon a Internet sin autenticación.

## Reglas de dependencia

```
cli/  ─┐
       ├─→  core/        (lógica pura, sin framework, sin GPU obligatoria)
daemon/─┘
```

- `core/` no importa de `daemon/` ni de `cli/`.
- El daemon traduce HTTP ↔ `core`. La CLI hoy llama a `core` directo; cuando el daemon
  estabilice, podrá llamar a la API en su lugar.

## Por qué Python en el núcleo y Flutter en la cara

- **Python**: todo el stack de IA de NVIDIA es Python (CUDA, vLLM, TensorRT-LLM, NIM,
  embeddings, fine-tuning). El núcleo necesita estar cerca de ese ecosistema.
- **Flutter**: un solo código para escritorio (Win/Mac/Linux) y móvil. Como solo consume la
  API, no necesita nada del stack de ML. Desacople total.

## Estado (stateful vs stateless)

- **Stateless** (Fase 0): hardware, registro de modelos, compatibilidad. Puro cálculo.
- **Stateful** (Fase 1+): modelos cargados, skills, memoria/RAG, agentes, métricas. Persisten
  en `data/` (SQLite + archivos). El volumen `magnus-data` del compose conserva esto.
