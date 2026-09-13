# Magnus en Jetson Orin

Probado el 2026-09-13 en un **Jetson Orin Nano Engineering Reference Developer Kit
Super** (8 GB, JetPack 6.2 / L4T R36.4.2, modo MAXN), compartiendo el equipo con otro
contenedor pesado (1.5 GB) y el escritorio GNOME con Firefox abierto.

## Arranque

```bash
git clone https://github.com/HugoLifes/magnus ~/magnus
cd ~/magnus
docker compose -f deploy/docker-compose.jetson.yml up -d --build
curl localhost:8420/platform
```

Desde otra máquina, sin exponer nada: `ssh -L 8420:localhost:8420 usuario@jetson`.

## Cifras medidas

| | valor |
|---|---|
| Descarga de `qwen2.5:0.5b` (400 MB, Wi-Fi) | 1 min 14 s |
| Carga en frío de `qwen2.5:1.5b` | 2.5 s |
| Velocidad `qwen2.5:1.5b` | 37.4 tok/s |
| Velocidad `qwen2.5:0.5b` | 59–62 tok/s |
| Primer token `qwen2.5:0.5b` | 0.30 s (1.er turno), 0.10 s (2.º) |
| Potencia de la placa en reposo | 7.4 W |
| Potencia generando | 12.7–13.8 W |

## Lo que hay que saber

### 1. `nvidia-smi` no da la memoria

Responde `[N/A]` en `memory.total` y `memory.free`. La GPU usa la RAM del sistema, así
que Magnus la lee de `/proc/meminfo` y marca la GPU con `unified_memory: true`.

Dentro de Docker `/proc/device-tree/model` no existe (Docker oculta `/sys/firmware`).
El compose monta el archivo del host y lo indica con `MAGNUS_DEVICE_TREE_MODEL`.

### 2. "Disponible" no es "libre" para CUDA

Con `MemAvailable` en 2.7 GiB y `MemFree` en 253 MiB (el resto era caché de archivos),
Ollama decidió que un modelo de 1.7 GiB cabía y CUDA falló:

```
NvMapMemAllocInternalTagged: 1075072515 error 12
cudaMalloc failed: out of memory
```

En Tegra las reservas de GPU salen de NvMap, que no espera a que el kernel desaloje la
caché. `drop_caches` lo resuelve pero exige root. Magnus lo hace sin root
(`core/reclaim.py`): escribe en memoria anónima el hueco que falta y la suelta. Medido:
MemFree de 265 MiB a 1.68 GiB, y la carga que fallaba entró en 2.5 s.

### 3. La carga necesita más que la estimación de Ollama

Con ~2.1 GiB libres para una carga estimada en 1.9 GiB entraron los pesos (935 MiB) y
falló el búfer de cómputo (300 MiB); en otro intento, la creación del handle de cuBLAS.
Magnus suma **0.6 GiB de holgura CUDA** en memoria unificada: la guarda se niega a
cargar si no cabe, el catálogo usa el mismo criterio, y si aun así CUDA falla se libera
toda la caché y se reintenta una vez.

### 4. El escritorio se come la memoria

| proceso | RSS |
|---|---|
| Firefox | ~560 MB |
| GNOME Shell + Xorg | ~400 MB |

En un Orin Nano de 8 GB eso decide entre un modelo de 1.5 B y uno de 0.5 B. Para
servir modelos conviene arrancar sin escritorio (`sudo systemctl set-default
multi-user.target`, reversible con `graphical.target`) o al menos cerrar el navegador.

### 5. La versión de Ollama importa: usar la imagen oficial

`dustynv/ollama:r36.4.0` trae **Ollama 0.6.5** y el tag más reciente de esa imagen es
0.6.8 (mayo 2025). Con 0.6.5 el registro rechaza `qwen3` con un 412 "requires a newer
version of Ollama". Magnus lo traduce a un mensaje accionable y expone la versión en
`/health`.

La imagen **oficial** `ollama/ollama` sí sirve en Jetson: su build arm64 incluye
`cuda_jetpack5` y `cuda_jetpack6`. Comprobado con 0.34.0 en JetPack 6.2:

```
inference compute ... library=CUDA compute=8.7 description=Orin
libdirs=ollama,cuda_jetpack6 driver=12.6 type=iGPU total="7.4 GiB"
```

El compose usa la oficial con la versión fijada. Ojo si se reemplaza la de dustynv:
la oficial ya tiene `ollama` como ENTRYPOINT, así que `command: ["ollama", "serve"]`
la rompería (quedaría `ollama ollama serve`).

## Modelos que caben (Orin Nano 8 GB)

Consulta en vivo: `magnus catalog` o `GET /catalog`. Con el escritorio y otro contenedor
de 1.5 GB corriendo quedan ~1.3–2.1 GiB utilizables: modelos de 0.5–1.5 B en q4. Sin
escritorio ni otros contenedores: hasta ~3–4 B.
