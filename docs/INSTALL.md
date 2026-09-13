# Instalar Magnus

Magnus tiene dos piezas:

- **El daemon** (Python): corre donde está la GPU, habla con Ollama y expone la API en
  `http://127.0.0.1:8420`.
- **La app** (Flutter): puede correr en el mismo equipo o en otro de la red.

En todos los casos hace falta **Ollama**, que es quien ejecuta los modelos.

## Elige tu caso

| Tengo… | Camino |
|---|---|
| Laptop o PC con Windows y GPU RTX | [Windows](#windows-laptop-o-pc-con-rtx) |
| PC con Linux y RTX, o DGX Spark | [Linux](#linux-rtx-o-dgx-spark) |
| Jetson Orin (Nano, NX, AGX) | [Jetson](#jetson-orin) |
| Servidor con varias GPUs | [Servidor](#servidor) |

## Windows (laptop o PC con RTX)

1. Instala el driver de NVIDIA, Python y Ollama:

   ```powershell
   winget install Python.Python.3.12
   winget install Ollama.Ollama
   ```

2. Desde la carpeta del repo, instala el daemon (sin permisos de administrador):

   ```powershell
   powershell -ExecutionPolicy Bypass -File deploy\windows\install.ps1
   ```

   Queda en `%LOCALAPPDATA%\Magnus` y arranca solo al iniciar sesión.

3. Mira qué modelos caben en tu GPU y descarga uno:

   ```powershell
   & "$env:LOCALAPPDATA\Magnus\venv\Scripts\magnus.exe" catalog
   & "$env:LOCALAPPDATA\Magnus\venv\Scripts\magnus.exe" fetch qwen3:4b
   ```

Referencia: con 4 GB de VRAM caben modelos de hasta ~3 B; con 8 GB, hasta ~8 B; con
16 GB, hasta ~14 B; con 24 GB, hasta ~32 B (todos en q4).

## Linux (RTX o DGX Spark)

```bash
curl -fsSL https://ollama.com/install.sh | sh     # si no tienes Ollama
bash deploy/linux/install.sh
~/.local/share/magnus/venv/bin/magnus catalog
```

El daemon queda como servicio del usuario: `systemctl --user status magnus`.

En **DGX Spark** la memoria es unificada (128 GB compartidos): Magnus lo detecta, reserva
memoria para el sistema y usa la guarda de memoria antes de cargar cada modelo.

## Jetson Orin

Con Docker, que ya viene con JetPack:

```bash
git clone https://github.com/HugoLifes/magnus ~/magnus
cd ~/magnus
docker compose -f deploy/docker-compose.jetson.yml up -d --build
curl localhost:8420/platform
```

Levanta `nim_ollama` (imagen oficial de Ollama, con soporte JetPack 6) y `nim_magnus`.
Lo que hay que saber de la memoria compartida está en [JETSON.md](JETSON.md). Lo más
importante: en un Orin Nano de 8 GB, cerrar el escritorio gráfico libera ~1 GB para modelos.

## Servidor

`deploy/docker-compose.yml` levanta el daemon con acceso a la GPU. En la beta el runtime
es Ollama (instálalo en el host o en otro contenedor y apunta `MAGNUS_OLLAMA_URL`); vLLM
llega después.

## Conectar la app

1. Compila la app: `cd clients/desktop && flutter build windows --release`.
2. En **Ajustes → Daemon**, pon la URL (`http://127.0.0.1:8420` si el daemon está en el
   mismo equipo).

### Usar el daemon desde otro equipo

Por seguridad el daemon solo escucha en `127.0.0.1`. Dos opciones:

- **Túnel SSH** (lo más simple, sin tocar nada):
  `ssh -L 8420:localhost:8420 usuario@servidor` y en la app `http://127.0.0.1:8420`.
- **Escuchar en la red** con token:

  ```bash
  magnus token new                 # muestra el token una sola vez
  magnus serve --host 0.0.0.0
  ```

  En la app pon la URL del servidor y el token. Sin token, `magnus serve --host 0.0.0.0`
  se niega a arrancar.

## Primeros pasos

```bash
magnus platform              # qué familia NVIDIA detectó y qué conviene
magnus catalog               # modelos que caben
magnus fetch qwen3:4b        # descargar
magnus chat qwen3:4b         # chatear, con el medidor de coste al final de cada respuesta
magnus rag new docs && magnus rag add docs ~/Documentos
magnus chat qwen3:4b --coleccion docs
magnus agent run asistente "¿cuánto es 1250 más IVA?" -m qwen3:4b
magnus usage                 # cuánto has ahorrado frente a la nube
```
