# Montaje de modelos y compatibilidad

## El flujo completo

```
elegir modelo ─→ elegir destino ─→ check de compatibilidad ─→ elegir runtime ─→ cargar ─→ servir
                  (GPU real o          (estima VRAM,            (perfil de uso)   (runtime    (daemon
                   preset)              recomienda cuant)                          manager)    orquesta + mide)
```

## 1. Destino

`core/hardware.py` resuelve el destino de tres formas:

| Entrada | Resultado |
|---|---|
| `auto` / vacío | VRAM de la GPU 0 real (vía `nvidia-smi`) |
| preset (`b200`, `dgx-spark`, `rtx-4090`, `h100`…) | VRAM tabulada del preset |
| número (`48`) | esos GiB exactos |

Esto permite validar **desde una laptop sin GPU** si un modelo cabría en el B200 del server.

## 2. Cálculo de compatibilidad

Implementado en `core/compatibility.py`.

```
total_VRAM = (pesos + kv_cache) * 1.20 + 1 GiB
```

- **Pesos** = `params * bytes_por_parámetro`:

  | Cuant | bytes/param | Uso típico |
  |---|---|---|
  | fp16 | 2.0  | calidad máxima, si sobra VRAM |
  | fp8  | 1.0  | datacenter (B200/H100), gran calidad/coste |
  | q8   | 1.0  | GGUF alta calidad |
  | q6   | 0.75 | equilibrio |
  | q5   | 0.65 | ajustado |
  | q4   | 0.5  | máxima compresión usable |

- **KV cache** = `2 * n_layers * n_kv_heads * head_dim * context * batch * 2 bytes`.
  Crece **lineal con el contexto y con el batch** — por eso un modelo "entra" con 4k de
  contexto y "no entra" con 128k. Modelos con GQA (`n_kv_heads` pequeño) gastan mucho menos KV.

- **×1.20**: activaciones, fragmentación y buffers del runtime. **+1 GiB**: contexto CUDA.

> Es una estimación de planificación. Para producción, medir con el runtime real bajo carga.

## 3. Veredicto y recomendación

`check_fit()` devuelve: VRAM requerida, % de uso del destino, margen, runtimes válidos y notas
(p. ej. "margen <10%: arriesgado bajo carga"). Si no entra, `recommend_quant()` busca la mejor
cuantización que sí entra con ≥10% de margen.

Casos ilustrativos en un B200 (192 GiB):

| Modelo | fp16 | Comentario |
|---|---|---|
| llama-3.1-8b | entra sobrado | corre a 128k de contexto sin problema |
| llama-3.1-70b | entra | ~141 GiB de pesos + KV; vigila contexto/batch altos |
| llama-3.1-405b | NO entra | ~810 GiB en fp16 → multi-GPU o q4/q3 agresivo |
| mixtral-8x7b | entra | OJO MoE: cargan los 8 expertos (~46.7B) aunque se activen 2 |

## 4. Elección de runtime

| Perfil | Runtime | Cuantizaciones | Notas |
|---|---|---|---|
| dev / 1 usuario | Ollama | q8 q6 q5 q4 (GGUF) | arranque trivial; single-stream |
| servir a varios | **vLLM** | fp16 fp8 q8 q4 | continuous batching; **principal en B200** |
| máximo throughput | TensorRT-LLM | fp16 fp8 q4 | el más rápido en NVIDIA; setup más complejo |

`core/runtimes.py::runtimes_for_quant(quant)` devuelve qué runtimes pueden con una cuant dada.

## 5. Carga real (Fase 1)

El `runtime_manager` (pendiente, ver AGENT_HANDOFF §3.1) hará el `load`/`unload` real. Empieza
por Ollama (HTTP API), con vLLM detrás de la misma interfaz para el camino de datacenter.
