# Informe de producto, experiencia, diseño y negocio

**Para:** la IA principal del proyecto Magnus.
**De:** un fork de esa sesión, dedicado a investigación de mercado, diseño y monetización.
**Fecha:** 2026-09-13.
**Complementa a:** [`BETA.md`](BETA.md) (plan técnico de la beta). No lo reemplaza.
**Versión visual:** https://claude.ai/code/artifact/7bd6906e-54be-4ddb-af82-d1fe2041e981
(página con las pantallas dibujadas; este documento contiene lo mismo en texto).

Cómo leer este informe:

- **[Verificado]** = medido en este proyecto o leído del código/equipo.
- **[Publicado]** = dato de una fuente externa de 2026 (ver §12). No verificado por nosotros.
- **[Propuesta]** = decisión de producto que sugiero. Requiere visto bueno del usuario (Hugo).

---

## 0. Resumen en diez líneas

1. Todas las piezas de la IA local ya existen por separado y gratis: motores (Ollama,
   LM Studio, llama.cpp), red entre PCs (NVIDIA PAIR), agentes (OpenClaw), interfaces
   (Open WebUI, Msty, Jan) y calculadoras de "¿cabe?" en la web. **Nadie las junta.**
2. Magnus no debe reemplazar motores ni construir un router de red. Debe ser **la cabina**
   que los detecta, los orquesta y añade lo que falta.
3. Lo que falta, y es la propuesta de valor: **ajuste al hardware antes de descargar,
   agentes con permisos y aprobaciones, y ahorro medido con vatios reales.**
4. El chat local es gratis en todos los competidores: **no se puede cobrar por chatear.**
5. Se cobra: **Conocimiento (RAG)** y agentes avanzados confiables (Pro), coordinación de
   personas (Team) y despliegues on-prem (Enterprise). Al principio el dinero viene de
   servicios y Enterprise. Decisión de Hugo (2026-09-18): el RAG es de pago (§14).
6. La beta debe salir en **octubre de 2026**, cuando llegan las laptops RTX Spark (N1X).
7. La seguridad es argumento de venta: OpenClaw acabó con decenas de miles de instancias
   expuestas y varios CVE.
8. La interfaz cambia según la clase de equipo (Borde, Personal, Potencia, Servidor).
9. Identidad: monograma de barras de nivel, violeta de la app actual + ámbar solo para ahorro,
   sin verde (es de NVIDIA). Archivos en `brand/`.
10. En §9 hay cambios concretos sugeridos al plan de `BETA.md`.

---

## 1. Estado observado del repo y del Jetson

Tomado el 2026-09-13, rama `feature/jetson-orin`, sin commits nuevos sobre `c5ad9a6`.

- **[Verificado]** 158 tests pasan en local (`pytest`).
- **[Verificado]** Módulos nuevos sin commitear: `core/catalog.py`, `chat.py`, `config.py`,
  `metering.py`, `platform.py`, `reclaim.py`, `store.py`, `telemetry.py`, más sus tests y
  `docs/BETA.md`. Los escribió la sesión principal; este fork no los tocó.
- **[Verificado]** Archivos que sí aportó este fork: `brand/magnus-mark.svg`,
  `brand/magnus-app-icon.svg` y este informe. Antes, en la misma sesión: soporte de Jetson en
  `core/hardware.py`, `tests/test_hardware_jetson.py`, `deploy/Dockerfile.jetson`,
  `deploy/docker-compose.jetson.yml`, modelos pequeños en `core/model_registry.py` y
  `unified_memory_note` en `core/compatibility.py`.
- **[Verificado]** Endpoints actuales del daemon: `/health`, `/hardware`, `/platform`, `/system`,
  `/compatibility`, `/models`, `/catalog`, `/models/local`, `/models/loaded`,
  `/models/{id}/load|unload|pull`, `DELETE /models/{id}`, `WS /chat`, `POST /chat`,
  `/conversations`, `/usage`, `/settings`.
- **[Verificado]** En el Jetson (`ssh apia@10.197.1.156`, proyecto en `~/magnus`) corren
  `nim_magnus` y `nim_ollama`. `/health` responde `ollama: true`. El contenedor
  `aforo-vehicular` (otro proyecto) sigue arriba y **no se debe reiniciar**.
- **[Verificado]** Hay un proceso `docker pull dustynv/ollama:r36.4.0` vivo aunque la imagen
  ya existe (9.83 GB). Parece un duplicado lanzado por este fork; se puede matar sin daño.
- **Hallazgo [Verificado]:** `GET /platform` en el Jetson devuelve
  `suggested_max_params_b: 7.5`. Se calcula sobre la memoria total menos una reserva fija,
  no sobre la memoria libre. Con el aforo corriendo solo hay ~2.8 GiB libres, y un 7B q4 no
  cabe. Sugiero calcular la sugerencia con `min(total - reserva, libre)` en memoria unificada.

---

## 2. Mercado en 2026: hechos que cambian el plan

| Hecho | Tipo | Consecuencia para Magnus |
|---|---|---|
| NVIDIA descontinuó ChatRTX (21-ene-2026) y ahora optimiza llama.cpp, Ollama y LM Studio | [Publicado] | El espacio de la app está libre y los motores mejoran solos. No competir con motores. |
| **NVIDIA PAIR** (IFA, sep-2026): gratis, open source, reparte peticiones entre PCs de la red local; mDNS + mTLS; expone un endpoint compatible con Ollama; soporta RTX 20+, RTX PRO, DGX Spark | [Publicado] | **No construir un router propio.** Integrarlo y darle interfaz. |
| **LM Studio 0.4** (ene-2026): motor sin interfaz (`llmster`), concurrencia, claves por cliente, endpoint compatible con Anthropic | [Publicado] | LM Studio también es un motor que Magnus puede orquestar, igual que Ollama. |
| **RTX Spark / N1X** (sale oct-2026): Blackwell + Grace, 32–128 GB unificada, Windows on Arm, >30 laptops | [Publicado] | Público nuevo con mucha memoria y sin saber qué hacer con ella. Fecha de la beta. |
| **NVFP4** en llama.cpp (mar–abr 2026); acelerado en Blackwell | [Publicado] | Magnus debe elegir el formato por el usuario cuando el equipo lo acelera. |
| **MTP / speculative decoding** en llama.cpp (may-2026); Qwen3.6 27B pasa de 38 a 65 tok/s | [Publicado] | Activarlo automáticamente cuando mida que ayuda. |
| **OpenClaw**: 113 mil estrellas en 5 días (ene-2026); luego ~40 mil instancias expuestas, CVE-2026-25253, "ClawJacked", credenciales en texto plano | [Publicado] | La gente quiere agentes que actúen en su PC y los actuales son peligrosos. La seguridad vende. |
| LM Studio, Jan, Msty (núcleo) y AnythingLLM de escritorio son gratis; Msty Aurum cuesta $149/año o $349 de por vida; Ollama Cloud $0/$20/$100 al mes | [Publicado] | No cobrar por chat. Hay precedente de pago por funciones avanzadas. |
| Microsoft Foundry Local + Windows ML acelerado con TensorRT for RTX | [Publicado] | Posible motor adicional en Windows. No prioritario para la beta. |
| Apps móviles para servidores locales ya existen (Reins, Off Grid, LocalLM) | [Publicado] | El móvil no es diferenciador por sí solo; sí lo es aprobar agentes desde el móvil. |

---

## 3. Posicionamiento [Propuesta]

**Frase:** «Tu IA, en tu GPU. Con la cuenta a la vista.»

**Qué es Magnus:** la cabina para IA local en hardware NVIDIA. Detecta el equipo y los
motores instalados, recomienda con datos de ese equipo, corre chat, conocimiento y agentes
con permisos, integra PAIR para usar las demás PCs, y lleva la cuenta del ahorro.

**Qué NO es:** otro motor de inferencia, otro router de red, otra ventana de chat.

### Cuatro promesas verificables

1. **Nunca descargas algo que no corre.** Ajuste a GPU, tok/s estimados en *ese* equipo y
   alternativa si no cabe. Motivo: el derrame a RAM baja un 7B de ~45 a ~8 tok/s [Publicado],
   y es la principal razón de abandono.
2. **De instalar a la primera respuesta en ~3 minutos**, sin terminal ni jerga en la primera
   pantalla.
3. **Tus agentes no hacen nada que no apruebes.** Permisos por carpeta y herramienta, red
   apagada por defecto, aprobación de acciones irreversibles con vista previa, bitácora con
   deshacer.
4. **Cada respuesta dice cuánto costó.** Tokens del motor, vatios del sensor, tarifa
   eléctrica configurable, precio de nube de referencia con fecha. Fórmula publicada.

---

## 4. Hardware: una experiencia por clase de equipo

Rendimiento en q4 salvo que se indique. Magnus debe reemplazar la estimación por la medida
real después de la primera respuesta.

| Equipo | Memoria | Rendimiento | Oferta por defecto | Modo |
|---|---|---|---|---|
| Jetson Orin Nano Super | 8 GB unificada (7.4 GiB útiles) | [Verificado] detección y memoria | 1 modelo de 1–3B, agentes de borde | Borde |
| RTX 5060 Ti 16 GB | 16 GB | [Publicado] ~32 tok/s en 14B | 1 modelo de 9–14B | Personal |
| RTX 5070 Ti / 5080 | 16 GB | [Publicado] ~105 tok/s en 8B (5070 Ti); ~58 tok/s en 14B (5080) | gpt-oss-20b o un 14B | Personal |
| RTX 5090 | 32 GB | [Publicado] ~45–48 tok/s en 32B | Qwen3.6-35B-A3B o 27–32B, NVFP4 | Potencia |
| RTX Spark (N1X) | 32–128 GB unificada | Sin benchmarks independientes aún | Varios modelos, routing por tarea | Potencia |
| RTX PRO 6000 Blackwell | 96 GB | [Publicado] ~2.9× una 5060 Ti | Modelos grandes, equipo pequeño con vLLM | Estación |
| DGX Spark · H100 · B200 | 128–192 GB | — | vLLM / TensorRT-LLM, cuotas, auditoría | Servidor |

**Regla de interfaz [Propuesta]:** el modo cambia lo que se muestra.

- **Borde y Personal:** «un modelo a la vez»; se esconde la concurrencia.
- **Potencia:** aparecen chat dividido, modelos simultáneos y router por tarea.
- **Servidor:** aparecen usuarios, cuotas y bitácora.

Esto encaja con `PlatformFamily` y `max_loaded_models` de `core/platform.py`.

**Modelos a tener en el catálogo** [Publicado, sep-2026]: Qwen3.5 9B (8 GB), gpt-oss-20b
(16 GB, herramientas y razonamiento), Gemma 4 (12B denso y 26B MoE con ~4B activos; visión,
128K), Qwen3.6 27B y Qwen3.6-35B-A3B (MoE, ~3B activos; ~32 GB), más los de 1–3B para Jetson.

---

## 5. Flujos clave [Propuesta]

### 5.1 Primer arranque (meta: primera respuesta en ~3 min)

1. **Escanear equipo** (~5 s): GPU, VRAM, RAM, controlador y memoria unificada. Si el
   controlador es viejo, avisarlo con el enlace oficial y seguir.
2. **Encontrar motor** (~10 s): buscar Ollama y LM Studio. Si no hay ninguno, ofrecer
   instalar Ollama con permiso explícito, mostrando tamaño y origen.
3. **Elegir primer modelo:** tres tarjetas para ese equipo (Rápido, Equilibrado, Máximo) con
   tamaño de descarga, tok/s estimados y distintivo de ajuste. Detectar y ofrecer los modelos
   que el usuario ya tenga en Ollama.
4. **Descargar sin esperar mirando:** barra reanudable y un chat de bienvenida que explica la
   barra de GPU mientras baja.
5. **Primera respuesta con su cuenta:** ya muestra tokens, velocidad, vatios y costo contra la
   nube. Es el momento que convence.

### 5.2 Agente que pide permiso

1. **Describir la tarea** en lenguaje natural. Magnus propone modelo, herramientas y
   **permisos mínimos**.
2. **Revisar el plan antes de correr:** el usuario puede quitar pasos o permisos.
3. **Correr con línea de tiempo:** cada paso con estado, herramienta, archivos tocados y
   tiempo. Leer dentro de la carpeta permitida no interrumpe.
4. **Aprobar lo irreversible:** escribir, borrar, enviar o salir a la red se detiene con
   vista previa. Tres opciones fijas: permitir una vez, permitir en esta carpeta, rechazar.
5. **Deshacer y aprender:** bitácora con deshacer para archivos. Las aprobaciones repetidas
   *sugieren* subir la autonomía; nunca la suben solas.

Niveles de autonomía: «Preguntar siempre» · «Solo lo irreversible» (por defecto) · «Autónomo».

---

## 6. Pantallas (especificación en texto)

Navegación lateral: **Cabina · Chat · Modelos · Agentes · Conocimiento · Equipos · Ahorro ·
Ajustes.** Paleta de comandos global con `Ctrl K`.

**Barra de GPU** en la barra de título de todas las pantallas: uso %, VRAM usada/total,
vatios y °C. En memoria unificada dice «Memoria» en lugar de «VRAM». Al hacer clic abre Cabina.
Fuente de datos: `GET /system`, muestreo cada 1 s.

### 6.1 Primer arranque, paso 3

- Indicador de pasos: Equipo ✓ · Motor ✓ · Primer modelo · Descarga.
- Tarjeta de escaneo: `RTX 5080 Laptop · 16 GB (14.9 libres) · 32 GB RAM · Ollama 0.30 ✓`.
- Tres tarjetas (ejemplo en RTX 5080 de 16 GB):
  - **Rápido:** Qwen3.5 9B · 5.6 GB · ~95 tok/s · Todo en GPU.
  - **Equilibrado (recomendado):** gpt-oss 20B · 13 GB · ~60 tok/s · Todo en GPU.
  - **Máximo:** Qwen3.6 35B-A3B · 21 GB · ~14 tok/s · Se desborda a RAM, con el texto
    «5 GB no caben en tu GPU».
- Botón principal con verbo y tamaño: «Descargar gpt-oss 20B · 13 GB».

### 6.2 Modelos (catálogo)

- **Filtros:** Cabe en mi GPU (activo por defecto), Herramientas, Visión, Razonamiento, Buen
  español, Descargados.
- **Orden por defecto:** mejor para tu equipo.
- **Cada fila:** nombre, capacidades, distintivo de ajuste, tamaño y tok/s estimados.
- **Panel de detalle:**
  - Selector de formato (q4 · MXFP4 · q8 · NVFP4), con la nota «NVFP4 se acelera en GPUs
    Blackwell».
  - Barra de memoria apilada: pesos, contexto (KV) y libre.
  - Deslizador de contexto que recalcula la barra y avisa del umbral de desborde, por ejemplo
    «A partir de 24K se desborda a RAM y baja a ~15 tok/s».
  - Botones: Descargar y Comparar.

### 6.3 Chat con dos modelos

- Pregunta del usuario arriba; dos respuestas en columnas, cada una con cabecera
  (modelo + distintivo) y **línea de medidor** al pie:
  `312 tok · 94 tok/s · 118 W · $0.00002 · nube $0.0019`.
- Compositor:
  - Chips de conocimiento («Contratos 2026 · 14 archivos») y de modelos.
  - Nota «Los dos caben juntos: 14.1 de 16 GB».
  - Barra de contexto `3.1K / 32K`.
- La comparación solo se permite si los modelos caben juntos en memoria.

### 6.4 Agente esperando aprobación

- **Cabecera:** nombre del agente, modelo, estado y tiempo, más el selector de autonomía.
- **Línea de tiempo:** pasos completados con detalle («lectura · dentro de la carpeta
  permitida · 18 s»), paso en pausa y pasos pendientes.
- **Tarjeta de aprobación:** «El agente quiere **crear un archivo nuevo** en
  `Documentos/Contratos`. No modifica ni borra nada existente.» Incluye vista previa del
  cambio (`+ penalizaciones.xlsx · 4 filas · 9 KB`) y las tres opciones fijas.
- **Panel de permisos:**

  | Permiso | Nivel |
  |---|---|
  | Leer carpeta | SÍ |
  | Escribir en carpeta | PREGUNTAR |
  | Borrar | NO |
  | Internet | NO |
  | Enviar correos | NO |
  | Ejecutar programas | NO |

  Nota al pie: «Lo que lee de los PDF se trata como texto, nunca como instrucciones.»

---

## 7. Funciones por etapa [Propuesta]

Etapas: **Beta = oct-2026**, **v1 = ene-2027**, **v2 = mar-2027**.

| Función | Qué hace | Hoy lo resuelve | Etapa |
|---|---|---|---|
| Escaneo y perfil del equipo | Clase de equipo, memoria unificada, sensores (nvidia-smi; INA3221 en Jetson) | Nadie dentro de una app | Beta |
| Gestor de motores | Detecta Ollama y LM Studio, instala Ollama con permiso, muestra versión y salud | Manual | Beta |
| Catálogo con ajuste | Distintivo de 4 estados, tok/s estimados, contexto que recalcula memoria | LM Studio (verde/rojo), calculadoras web | Beta |
| Chat con medidor | Streaming; tokens, tok/s, W, costo local contra nube por respuesta | Nadie muestra el costo | Beta |
| Conocimiento local (**Pro, de pago**) | Carpetas vivas, búsqueda híbrida con reranker, citas con archivo y página (§14) | Open WebUI, Msty, AnythingLLM (gratis) | Beta como prueba; cobro al lanzar Pro |
| Magnus Code | Agente que lee y edita código y usa PowerShell o la terminal, con permisos (§15) | Claude Code, Codex CLI, OpenCode, Aider | v1 |
| Servidor compatible | Endpoints OpenAI **y Anthropic** en localhost, claves por cliente (Claude Code, OpenClaw) | LM Studio 0.4, Ollama | Beta |
| Aceleración automática | MTP/speculative decoding y NVFP4 en Blackwell cuando se mide que ayuda | Flags manuales | v1 |
| Chat dividido | 2–3 modelos a la vez, solo si caben juntos | Msty, Cherry Studio | v1 |
| Agentes con permisos | Plan revisable, línea de tiempo, aprobaciones, bitácora con deshacer, MCP | OpenClaw (sin garantías) | v1 |
| Equipos en red | Interfaz sobre NVIDIA PAIR; política «nunca salir de este equipo» | PAIR sin interfaz | v1 |
| App móvil | Emparejar por QR; chat y aprobaciones de agentes | Reins, Off Grid | v1 |
| Router por tarea | Elige modelo según la petición entre los cargados | Nadie para usuario final | v2 |
| Voz local | Dictado y respuesta hablada sin nube | Open WebUI (parcial) | v2 |
| Multiusuario | Usuarios, roles, cuotas, SSO, bitácora | Open WebUI | v2 |

---

## 8. Sistema de diseño

Base existente que se respeta [Verificado en `clients/desktop/lib/core/theme/magnus_theme.dart`]:

- **Tres pieles:** Windows (Fluent, glass/Mica), Material You y macOS.
- **Acento:** `#8B7BFF` en oscuro y `#5A4FCF` en claro.
- **Fondo oscuro:** `#0B0817`.
- **Tipografía:** Plus Jakarta Sans por defecto, JetBrains Mono para cifras e iconos Lucide.
- **Apariencia:** oscuro por defecto.

### 8.1 Identidad [Propuesta]

- **Monograma:** una M formada por 5 barras de nivel (como lectura de VRAM). Barras de 8
  unidades con 4 de separación, alineadas abajo, alturas 48 · 34 · 20 · 34 · 48 en un
  viewBox de 64. La barra central (la más baja) va en ámbar y representa el ahorro.
  Archivos: `brand/magnus-mark.svg` y `brand/magnus-app-icon.svg` (radio 56 sobre 256).
- **Tipografía de marca:** Bricolage Grotesque para titulares; Plus Jakarta Sans para texto;
  JetBrains Mono para cifras.
- **Voz:** el número antes que el adjetivo. «llama-3.1-8b necesita 6.1 GiB y hay 2.8 libres.
  Prueba qwen2.5-3b.» Nunca «¡Desata el poder de la IA!» ni «Error 503».
- **Marcas registradas:** sin acuerdo con NVIDIA se dice «para hardware NVIDIA», nunca
  «powered by NVIDIA». El prefijo `nim_` de los contenedores es convención interna y no debe
  aparecer de cara al cliente.

### 8.2 Color con significado

| Token | Hex (oscuro) | Uso exclusivo |
|---|---|---|
| Violeta | `#8B7BFF` | Acción principal, selección, pesos del modelo |
| Ámbar | `#F2B441` | Dinero ahorrado y acciones en pausa. Nunca decoración |
| Turquesa | `#2DD4BF` | Todo en GPU, paso completado, permiso concedido |
| Celeste | `#60C8FF` | Memoria compartida, contexto, información |
| Coral | `#FF8A65` | Se desborda a RAM (siempre con rayado diagonal) |
| Rosa | `#FB6F92` | No cabe, error, acción destructiva |

- **Sin verde:** el éxito usa turquesa.
- **Cambio frente al tema actual:** hoy `ok` es `#34D399` (verde) y `warn` es `#FBBF24`, que
  se confunde con el ámbar de ahorro. Sugiero `ok → #2DD4BF` y usar coral para las
  advertencias de derrame.

### 8.3 Distintivo de ajuste (4 estados)

Cada estado lleva **forma + texto + color**, nunca solo color:

| Estado | Icono | Texto | Cuándo |
|---|---|---|---|
| `gpu` | ✓ | Todo en GPU | Cabe entero en VRAM con margen |
| `shared` | dos círculos | Memoria compartida | Equipo de memoria unificada y cabe en la memoria libre |
| `spill` | triángulo, fondo rayado | Se desborda a RAM | No cabe entero en VRAM dedicada; decir cuánto y a qué velocidad |
| `no` | ✕ | No cabe | No cabe ni con desborde razonable, o no cabe en la memoria libre unificada; proponer alternativa |

Sugerencia de contrato: que `GET /catalog` y `POST /compatibility` devuelvan
`fit: "gpu"|"shared"|"spill"|"no"`, `est_tokens_per_s` y `spill_gib`, para que Flutter no
recalcule nada.

### 8.4 Tipografía, espacio y movimiento

| Elemento | Valor |
|---|---|
| Título de página | Bricolage 24/28 · 700 |
| Título de tarjeta | Bricolage 17/22 · 700 |
| Cuerpo | Plus Jakarta 13.5/20 · 400 |
| Etiqueta | Plus Jakarta 11.5/16 · 600 |
| Cifras | JetBrains Mono 12/16, tabulares |
| Espaciado | 4 · 8 · 12 · 16 · 24 · 32 |
| Radio | Fluent 8 · Material 16 · macOS 10 |
| Hover/presionado | 120 ms |
| Entrada de tarjeta | 250 ms, desaceleración |
| Cambio de sección | Fluent 333 ms · Material 3 Expressive con resorte estándar |
| Tokens en streaming | Sin animación por token; cursor parpadeante |
| Barra de GPU | Muestra cada 1 s, suavizado de 400 ms |
| Reducir movimiento | Solo quedan cambios de color |

### 8.5 Componentes propios

| Componente | Dónde | Regla |
|---|---|---|
| Barra de GPU | Barra de título, todas las pantallas | Uso, VRAM/Memoria, W, °C. Clic → Cabina |
| Distintivo de ajuste | Catálogo, primer arranque, selector del chat | Se recalcula al cambiar contexto o formato; tooltip con desglose |
| Línea de medidor | Pie de cada respuesta | Tokens · tok/s · W · costo local · nube. El ahorro es la única cifra en ámbar |
| Barra de contexto | Compositor | Aviso al 80 %. Al llenarse ofrece resumir; nunca corta en silencio |
| Tarjeta de aprobación | Agente, notificación, móvil | Verbo concreto, destino, vista previa y tres opciones fijas. No se aprueba con Enter |
| Paleta de comandos | `Ctrl K` global | Cargar modelo, nueva conversación, ir a agente, cambiar piel |

### 8.6 Textos en momentos difíciles

- **No cabe:** «Qwen3.6 27B necesita 16.8 GB y tu GPU tiene 16. Con Qwen3.5 9B respondes a
  ~95 tok/s sin salir de la GPU.»
- **Motor caído:** «Ollama dejó de responder. Tu conversación está guardada.»
  Botones: Reiniciar Ollama · Ver registro.
- **Vacío (agentes):** «Aún no hay agentes. Empieza con una plantilla: revisar contratos,
  ordenar descargas o resumir correos.» Las plantillas vienen con permisos ya limitados.

---

## 9. Cambios sugeridos al plan de `BETA.md`

Ordenados por impacto. Ninguno rompe el contrato existente.

1. **Integrar NVIDIA PAIR en lugar de construir red propia.** Tratar el endpoint de PAIR como
   un backend compatible con Ollama más (URL configurable). Pantalla «Equipos» en v1.
2. **LM Studio como segundo backend** detrás de `RuntimeManager` (API compatible con OpenAI).
   Detección en el gestor de motores de la beta.
3. **`fit` de 4 estados y `est_tokens_per_s` en `/catalog` y `/compatibility`** (§8.3). Para
   estimar la velocidad bastan una tabla de ancho de banda de memoria por GPU y el tamaño del
   modelo; luego se sustituye por la medida real guardada en `/usage`.
4. **Corregir `suggested_max_params_b` en memoria unificada** para usar la memoria libre (§1).
5. **Endpoint compatible con Anthropic** (`/v1/messages`) además del de OpenAI, con claves por
   cliente. Es lo que usan Claude Code y OpenClaw.
6. **Modelo de permisos de agentes desde el diseño del paso 6 de `BETA.md`:**
   - Alcance por carpeta.
   - Herramientas con nivel SÍ / PREGUNTAR / NO.
   - Red apagada por defecto.
   - Contenido leído marcado como no confiable.
   - Bitácora con deshacer.

   Añadir estado de ejecución «esperando aprobación» al contrato del agente.
7. **Seguridad por defecto en el paso 7 de `BETA.md`** (§10). Nunca aceptar tokens por query
   string (CVE-2026-25253 de OpenClaw).
8. **Medidor creíble:** versionar la tabla de precios de nube con fecha, publicar la fórmula,
   tarifa eléctrica configurable (México: tarifa doméstica de alto consumo cambia mucho la
   cuenta) y marcar como «estimado» cuando no haya sensor de potencia.
9. **Actualizar el registro de modelos** con la generación actual (§4) y soportar MoE (parámetros
   totales para memoria, activos para velocidad).
10. **Aceleración automática (v1):** detectar Blackwell para NVFP4 y activar MTP en modelos
    que traen drafter (Qwen3.6, Gemma 4).

---

## 10. Seguridad por defecto [Propuesta]

- **Solo este equipo:** el daemon escucha en `127.0.0.1`. Abrirlo a la red es una acción
  explícita que exige emparejar por QR y mTLS (el mismo patrón que PAIR).
- **Una clave por cliente:** revocable y con permisos. Nunca se aceptan tokens desde la URL.
- **Secretos en el sistema:** Administrador de credenciales de Windows o llavero de macOS.
  Nunca en texto plano.
- **Agentes con alcance:** carpetas permitidas, internet apagado, no ejecutar programas por
  defecto. Lo leído de documentos y webs se marca como no confiable.

---

## 11. Negocio [Propuesta]

**Tesis:** PAIR es gratis y LM Studio también. Magnus no cobra por red ni por chat: cobra por
agentes en los que se puede confiar y por coordinar personas.

| Plan | Incluye | Precio (USD) |
|---|---|---|
| **Community** | Catálogo con ajuste, chat con medidor, servidor compatible (motor para Claude Code y otros agentes), equipos en red con PAIR, chat dividido. **Sin RAG** | $0, código abierto |
| **Pro** | **Conocimiento (RAG) local**; **Magnus Code** con modo autónomo en sandbox; agentes con permisos, programados y con MCP; móvil fuera de casa con relay cifrado; reportes de ahorro; respaldo cifrado | $9/mes · $89/año · $219 de por vida (revisar al alza: ver §14) |
| **Team** | Multiusuario, roles, cuotas por persona, SSO, agentes compartidos, bitácora | $39 por equipo al mes, usuarios ilimitados |
| **Enterprise** | Instalación sin conexión, flota de Jetson / DGX Spark / B200, cumplimiento LFPDPPP, soporte con SLA en español | desde $12,000/año |

Team se cobra **por equipo y no por usuario** porque el límite real es la GPU.

**Ingresos fuera de suscripción:**

- **Servicios:** instalación, fine-tuning y agentes a medida, de $3k a $25k por proyecto. Es
  el dinero del primer año. Caso de referencia: el aforo vehicular en el Jetson.
- **Marketplace:** paquetes de skills y agentes por industria (contable con CFDI del SAT,
  legal, clínicas, tránsito), con comisión de 20–30 %.
- **Magnus Box:** equipo NVIDIA con Magnus instalado, vendido con integradores. Margen de
  instalación más el primer año de Team.

**Escenario ilustrativo del primer año** (para dimensionar, no es una proyección):

| Fuente | Supuesto | USD/año |
|---|---|---|
| Pro | 15,000 instalaciones, 2 % pagan anual | 26,700 |
| Team | 20 equipos todo el año | 9,360 |
| Enterprise | 2 contratos | 24,000 |
| Servicios | 5 proyectos de $8,000 | 40,000 |
| **Total** | | **100,060** |

Servicios y Enterprise suman el 64 %: al principio el dinero viene de pocas empresas.

**Orden de lanzamiento:**

| Fecha | Qué se lanza | Qué hace falta |
|---|---|---|
| Oct–nov 2026 | Beta Community | Chat con medidor, «¿Cabe aquí?», instalador de Windows |
| Nov 2026 | Servicios y primer Enterprise | Una página, el caso del aforo documentado, despliegue sin conexión probado |
| Ene 2027 | Pro | Agentes con permisos, app móvil, sistema de licencias sin cuenta obligatoria |
| Mar 2027 | Team y marketplace | Autenticación, roles, cuotas, SSO, paquetes de skills firmados |

**Riesgos:**

- **NVIDIA hace lo mismo.** Defensa: español, pymes latinoamericanas, verticales locales y
  servicio cercano.
- **Marcas registradas.** Buscar «Magnus» en el IMPI (clases 9 y 42) antes de invertir en la
  marca.
- **El usuario gratuito nunca paga.** Por eso el dinero temprano viene de empresas.
- **El ahorro es una estimación.** Si la cifra no se sostiene, se pierde la confianza: publicar
  la fórmula y medir vatios reales.

---

## 11b. Respaldo en la nube cuando la memoria no alcanza

Petición de Hugo: ofrecer las APIs de NVIDIA gratis como alternativa cuando un modelo no cabe.

### Lo que dicen los términos de NVIDIA [Verificado, leído del PDF oficial]

Fuente: *NVIDIA API Trial Terms of Service* (build.nvidia.com).

- **§1.2:** acceso «for limited trial purposes only and without use of the API Service or
  Generated Content in production».
- **§1.4:** sin una suscripción pagada con NVIDIA o un proveedor, solo se permite «internal
  testing and evaluation purposes, not in production».
- **§4.2:** no se puede «sell, rent, sublicense, transfer or distribute or make available to
  others any portion of the API Service or Generated Content».
- **§3.3:** NVIDIA puede usar el contenido enviado «to improve NVIDIA products and services,
  including AI models».
- **§2.6(a) y §4.3:** prohibido enviar datos personales, confidenciales, de salud o financieros.

**Conclusión:** Magnus **no puede** ofrecer la API gratuita de NVIDIA como servicio propio. No
puede usar una clave compartida ni hacer de proxy para sus usuarios. Además, §3.3 choca con la
promesa de privacidad de Magnus. La cuenta gratuita de NVIDIA ya no publica límites fijos; en
2026 se citaban ~1,000 créditos y 40 RPM [Publicado].

### Diseño propuesto [Propuesta]

**1. «Trae tu clave» (gratis, Community).**
- El usuario conecta **su propia** clave de build.nvidia.com o de otro proveedor compatible con
  OpenAI (Groq: 30 RPM y 14,400 peticiones/día gratis; OpenRouter: modelos `:free` a 20 RPM
  [Publicado]).
- Magnus solo enruta; la clave va al llavero del sistema.
- Advertencia fija al conectar la clave de NVIDIA: «Prueba gratuita de NVIDIA: no apta para
  datos personales o confidenciales, y NVIDIA puede usar lo que envíes para mejorar sus modelos.»

**2. Nunca automático.**
- Cuando algo no cabe, el aviso ofrece tres salidas en este orden:
  1. Modelo local más pequeño.
  2. Otra PC de la red (PAIR).
  3. Enviar a la nube.
- La nube se activa **por conversación** y la conversación muestra el distintivo
  «Sale de tu equipo».
- Las colecciones de conocimiento y los agentes pueden marcarse «Nunca salir de este equipo»;
  ahí la opción de nube no aparece.

**3. Contrato sugerido.**
- `Runtime.CLOUD` detrás de `RuntimeManager`, con `base_url` y clave por proveedor.
- Campo `location: "local"|"lan"|"cloud"` en cada respuesta.
- El medidor registra el costo real de nube y la cuota restante, en lugar del precio de
  referencia.

### Cómo se monetiza [Propuesta]

La nube gratuita de terceros no deja dinero; la nube propia sí.

**Magnus Cloud en el B200 de Hugo** (vLLM con modelos de pesos abiertos y licencia comercial):
- **Es legal:** es infraestructura propia; no se revende NVIDIA API. Para producción conviene
  vLLM y no NIM autoalojado, que exige licencia AI Enterprise (el programa de desarrolladores
  solo cubre prototipos en hasta 16 GPUs).
- **Es coherente con la marca:** servidor en México, sin retención de datos y sin entrenar con
  lo que envía el cliente. Cumple LFPDPPP.
- **Costo por millón de tokens** = costo por hora del servidor ÷ (tokens por hora / 1e6).
  Ejemplo con supuestos por medir: $3/h todo incluido y 5,000 tok/s agregados con batching dan
  18 M tok/h, o **~$0.17 por millón**. Hay que medirlo con vLLM en el B200 antes de fijar precios.

**Oferta:**

| Nivel | Qué recibe | Propósito |
|---|---|---|
| Community | Cuota gratuita pequeña en Magnus Cloud (p. ej. 200K tokens/mes por cuenta verificada) | Cumplir la promesa de «nunca te quedas sin IA» de forma legal. Es costo de adquisición |
| Pro ($9/mes) | Créditos mensuales incluidos | Precedente: Ollama Cloud Pro, $20 con $60 de uso |
| Paquetes de créditos | Precio de mercado de modelos abiertos (~$0.10–1.20/M [Publicado]) | Margen sobre el costo medido del B200 |
| Team / Enterprise | Horas dedicadas del B200 o instalación on-prem | Contrato |

**Cuando el B200 no alcance:** comprar capacidad con suscripción de pago (NVIDIA pay-as-you-go o
proveedores de DGX Cloud Lepton). Revender requiere acuerdo explícito. Solicitar **NVIDIA
Inception** (gratis, sin equity) para créditos y descuentos; las cifras de créditos que circulan
no están confirmadas por NVIDIA [Publicado].

---

## 13. Implementado por el fork (2026-09-13)

Rama `feature/jetson-orin`, commits `e9d2197`, `8bf7480`, `cb26793` (y `9ce0ea8` con marca e
informe). 321 tests, ruff limpio, `flutter analyze` sin problemas, OpenAPI regenerado solo con
adiciones.

### Backend

- **`core/providers.py`**:
  - Proveedores compatibles con OpenAI: `vllm`, `nvidia`, `groq`, `openrouter`,
    `openai-compatible` y `magnus-cloud`.
  - `OpenAICompatClient` devuelve fragmentos con forma de Ollama, así `ChatService` no cambia
    su lógica.
  - Validaciones: un servidor fuera de la red exige https; el id `local` está reservado; la
    red local se detecta con rangos explícitos (RFC1918, CGNAT de Tailscale, ULA).
- **`core/secrets.py`**: llavero del sistema con respaldo en `secrets.json` para Docker y Jetson.
- **Chat**: `provider` por turno, sin cambiar el orden validar → skills → RAG → cargar modelo.
  Un turno remoto no carga modelos locales ni atribuye energía de este equipo.
- **Medidor**: campos nuevos `provider`, `location` y `provider_cost_usd`. El ahorro se calcula
  contra lo que cobró el proveedor.
- **Daemon**: `/providers` (GET, PUT, DELETE, `models`, `test`) y, solo para Magnus Cloud,
  `/providers/{id}/account`, `/packs` y `/redeem`. La clave nunca vuelve en las respuestas.
- **`cloud/`**, el gateway de créditos delante de cualquier vLLM:
  - Libro mayor en SQLite con saldo como suma de movimientos y `(account_id, ref)` único.
  - Bono mensual de 100 créditos.
  - Cobro con los tokens que reporta el servidor, redondeando hacia arriba.
  - `max_tokens` se recorta a lo que paga el saldo; sin saldo responde 402.
  - Vales en Crockford base32, canjeables una sola vez.
  - CLI del operador en `python -m cloud.admin`.
  - Despliegue en `deploy/docker-compose.cloud.yml`.
  - Paquetes: Chispa $5 / 5,000; **Impulso $20 / 22,000**; Turbo $50 / 60,000; Estudio
    $200 / 260,000 créditos. 1 crédito = $0.001.

### App (Flutter)

- **Kit** `shared/widgets/magnus_kit.dart`: `AuroraBackdrop`, `GlowButton`, `SpotlightCard` con
  borde giratorio para la opción destacada, `FitBadge` de 4 estados, `LocationChip` y
  `CreditRing`. Respeta «reducir movimiento».
- **Sección Nube**: héroe «Tu equipo primero», saldo con canje de vales, paquetes, APIs con tu
  clave (con el aviso de términos de NVIDIA) y servidores vLLM de tu red.
- **Chat**: selector «Dónde», modelos del proveedor, chip de ubicación en la línea del medidor y
  el ahorro en ámbar.

### Prueba en vivo en el Jetson [Verificado]

El gateway corrió en un contenedor temporal (imagen `magnus-nim_magnus`, sin construir nada),
con `nim_ollama` en `/v1` como servidor y `qwen3:0.6b`. El aforo no tenía videos en cola y no se
tocó.

| Prueba | Resultado |
|---|---|
| Sin clave | 401 |
| Cuenta nueva | 100 créditos del bono mensual |
| Chat sin streaming | 21 tokens de entrada y 120 de salida, 4.4 s, cobrados 0.026 créditos |
| Chat con streaming | `usage` capturado del último fragmento, cobrados 0.025 créditos |
| Modelo inexistente | 404 con la lista de disponibles |
| Vale Chispa en minúsculas y con espacios | +5,000 créditos |
| Mismo vale otra vez | «Ese código ya se canjeó.» |
| Memoria del gateway | 43 MiB |

**Hallazgo:** con modelos que razonan (qwen3), un `max_tokens` bajo se gasta completo en
razonamiento y la respuesta llega vacía, pero los tokens se cobran. Cobrar razonamiento es
estándar, pero la app debe avisarlo y ofrecer apagar «Razonar». `chat_template_kwargs` apaga
el razonamiento en vLLM; por la API `/v1` de Ollama no se probó.

### Pendiente

- **Pasarela de pago**: hoy los paquetes se venden como vales. Hay que decidir entre Mercado
  Pago y Stripe para el webhook que emite el vale al pagar.
- **Revisión visual de la app**: no se compiló para Windows porque la PC iba lenta; hay que
  mirar la sección Nube compilada.
- **Agentes con proveedores remotos**: `AgentRunner` sigue usando solo Ollama. Falta traducir
  `tool_calls` al formato de OpenAI.
- **Daemon del Jetson**: no se reconstruyó `nim_magnus` con estos cambios.
- **Magnus Cloud en producción**: medir el coste real por millón de tokens con vLLM en el B200
  antes de fijar precios, y ponerlo detrás de TLS.

---

## 14. Conocimiento (RAG): es de pago

**Decisión de Hugo (2026-09-18):** el RAG no es gratis; no entra en Community.

### Lo que existe hoy [Verificado en el código]

- **Motor:** `core/rag.py` indexa PDF, texto y HTML en fragmentos de 1,000 caracteres
  (150 de traslape), con embeddings de `nomic-embed-text` vía Ollama, guardados en SQLite.
- **Búsqueda:** **solo por coseno**, sin búsqueda léxica ni reranker.
- **Memoria:** hechos cortos del usuario.
- **Dónde se usa:** `/rag/*` y `/memory`, la sección Documentos de la app y la herramienta
  `buscar_documentos` de los agentes.
- **Hoy todo es gratis y está en el repo.**

### Consecuencia 1: la licencia decide si se puede cobrar [Propuesta]

El repo **no tiene archivo LICENSE**. Sin licencia el código es «todos los derechos
reservados», pero el plan dice «núcleo abierto». Si el RAG queda en código abierto, cualquiera
lo usa sin pagar. Opciones:

| Opción | Cómo | A favor | En contra |
|---|---|---|---|
| **A. Núcleo abierto** (recomendada) | Núcleo (daemon, chat, catálogo, medidor, proveedores) con Apache-2.0 en repo público. **Magnus Conocimiento** en repo privado, distribuido como paquete que el daemon carga con licencia válida | Mantiene la comunidad y protege lo que se cobra | Dos repos y una interfaz de plugins estable |
| B. Todo cerrado, con edición gratuita | Un solo binario; las funciones de pago se desbloquean con licencia | Simple | Se pierde la comunidad y la confianza de «código abierto» |
| C. Código visible con licencia de fuente disponible (BUSL o FSL) | Se ve todo; el uso comercial del RAG exige pagar; pasa a Apache a los 2 años | Transparencia | Espanta a parte de la comunidad; exige vigilar el cumplimiento |

**Hay que decidir antes de publicar el repo o de sacar la beta.** Lo que ya está publicado bajo
una licencia abierta no se puede cerrar hacia atrás.

### Consecuencia 2: activar Pro sin cuenta obligatoria y sin internet [Propuesta]

- **Licencia firmada:** un archivo de licencia firmado con Ed25519 (la clave pública va
  dentro del daemon) que dice plan, vigencia y número de equipos. Se valida sin conexión, con
  14 días de gracia si no puede renovarse.
- **Se compra como los créditos:** un vale `MAG-…` o la pasarela, cuando exista.
- **Sin licencia:** `/rag/*` responde **402** «Conocimiento es parte de Magnus Pro». La app
  muestra qué gana el usuario y ofrece la prueba.
- **Prueba de 14 días de Pro** para que el usuario vea la diferencia con sus propios
  documentos (sugerencia; decide Hugo).
- **Pregunta abierta:** ¿adjuntar UN archivo a una conversación, que se lee entero en el
  contexto, sin índice y sin guardarse, cuenta como RAG? Si Hugo dice que no, eso puede
  quedar gratis como gancho.

### Qué tiene que ser el RAG para que valga pagarlo [Propuesta]

Los competidores lo dan gratis (AnythingLLM, Open WebUI con búsqueda híbrida y reranker, Msty)
[Publicado]. Para cobrar hay que ser claramente mejor en lo que duele:

1. **Ingesta de verdad:** PDF escaneados con OCR, tablas, Word, Excel, PowerPoint y correos.
   En equipos grandes, NVIDIA NeMo Retriever extrae PDF multimodales hasta 15 veces más rápido
   [Publicado].
2. **Búsqueda híbrida con reranker:** léxica (SQLite FTS5 / BM25) + vectores, fusionadas por
   rangos (RRF), y un reranker sobre los 20–50 mejores para quedarse con 5–10 [Publicado].
   El proyecto de aforo ya usa denso + léxico + RRF: hay experiencia en casa.
3. **Carpetas vivas:** Magnus vigila las carpetas y reindexa lo que cambia; no hay que volver
   a subir nada.
4. **Citas verificables:** archivo, página y fragmento resaltado. Si no hay evidencia, la
   respuesta es «no está en tus documentos». Se comprueba que cada cita sea de un fragmento que
   de verdad se recuperó.
5. **Buenos resultados en español:** embeddings multilingües elegidos según el equipo.
6. **El medidor aplicado al RAG:** el usuario pone 20 preguntas con su respuesta esperada y
   Magnus mide qué tan bien encuentra. Es coherente con la marca («el número antes que el
   adjetivo») y ningún competidor lo muestra.
7. **Conectores** (Team y Enterprise): OneDrive/SharePoint, Google Drive, Outlook y CFDI del
   SAT, **con permisos por documento** (quién puede ver qué).

### Cómo se reparte entre planes [Propuesta]

| Plan | Conocimiento |
|---|---|
| Community | Sin RAG (quizá adjuntar un solo archivo, ver la pregunta abierta) |
| **Pro** | Colecciones locales ilimitadas, carpetas vivas, híbrido + reranker, OCR, citas por página, evaluación |
| **Team** | Colecciones compartidas con permisos, conectores de nube de oficina |
| **Enterprise** | Conectores empresariales, auditoría, permisos por documento, NeMo Retriever en su servidor |
| Magnus Cloud | Ingesta pesada (OCR, tablas) con créditos cuando el equipo es chico, siempre opcional y avisando que el documento sale del equipo |

**Precio:** con el RAG y Magnus Code, $9 al mes se queda corto frente a lo que cobra el
mercado por funciones de poder (Msty Aurum $149 al año [Publicado]). Hay que revisarlo:
por ejemplo $12–15 al mes, o dejar $9 y crear Pro+.

---

## 15. Magnus Code: el agente que trabaja en tu código y tu terminal

**Objetivo (Hugo):** que Magnus trabaje con código como Claude Code: que lea y edite el
proyecto y ejecute comandos en PowerShell o en la terminal, **pidiendo permiso**. Con modelos
locales, de la red o de Magnus Cloud.

### Lo que existe hoy [Verificado en el código]

- Los agentes (`core/agent.py`) solo tienen herramientas seguras: `calcular`, `fecha_hora`,
  `buscar_documentos`, `recordar` y `buscar_memoria`.
- **A propósito, ninguna ejecuta comandos ni lee archivos.**
- Magnus Code necesita una capa nueva de permisos y ejecución. No es un agente YAML más.

### Dos caminos que se suman [Propuesta]

- **A. Ser el motor de los agentes que ya existen** (rápido, Community): endpoints compatibles
  con Anthropic (`/v1/messages`) y con OpenAI, con una clave por cliente. Así Claude Code,
  Codex CLI, OpenCode o Aider corren con los modelos de Magnus. Ya estaba en §9, punto 5.
- **B. Agente propio, Magnus Code** (el diferenciador, parte en Pro): una CLI de terminal
  (`magnus code`) y un panel en la app con terminal integrada, vista de cambios y tarjetas de
  aprobación.

### Herramientas del agente

- Leer archivos, listar y buscar (glob y ripgrep).
- **Editar con reemplazo exacto y vista del cambio**, y escribir archivos.
- **Ejecutar comandos.**
- Git: estado, diferencias y commit con permiso.
- Web, apagada por defecto.
- Servidores MCP del usuario.

### La terminal

- **Qué shell usa:** en Windows detecta PowerShell 7 (`pwsh`) y si no, Windows PowerShell 5.1;
  en Linux, macOS y Jetson, bash o zsh; WSL como opción.
- **Cómo corre cada comando:** con carpeta de trabajo fija en el proyecto, tiempo límite,
  salida en vivo con tope y botón de cancelar que mata también los procesos hijos (Job Object
  en Windows).
- **Variables de entorno:** sin claves ni secretos.

### Permisos: el corazón de la función

Se hace igual que Claude Code: se evalúa en orden **denegar → preguntar → permitir**, y una
denegación de la empresa no se puede anular [Publicado].

- **Modos:**
  - **Preguntar** (por defecto): leer dentro del proyecto es libre; editar y ejecutar piden
    permiso.
  - **Aceptar ediciones:** edita libre dentro del proyecto; los comandos piden permiso.
  - **Plan:** solo lee y propone.
  - **Autónomo:** solo si hay sandbox activo.
- **Reglas por herramienta y patrón**, por ejemplo: `Shell(git status)` permitir,
  `Shell(npm test*)` permitir, `Edit(src/**)` preguntar, `Read(.env)` denegar.
- **Nivel de riesgo de cada comando antes de pedir permiso:** lectura, escritura en el
  proyecto, red, fuera del proyecto o destructivo (`Remove-Item -Recurse`, `rm -rf`,
  `git push --force`, formatear discos, tocar el registro). **Lo destructivo siempre pregunta,
  incluso en modo autónomo**, y algunas cosas quedan bloqueadas.
- **Tarjeta de aprobación** (§8.5):
  - Muestra el comando exacto, qué dice el modelo que hará, la carpeta y el riesgo.
  - Opciones: permitir una vez, permitir siempre este comando en este proyecto, o rechazar.
    Si rechaza, el motivo vuelve al modelo.
- **Confianza por carpeta:** la primera vez que se abre un proyecto, Magnus pregunta «¿confías
  en esta carpeta?», porque los archivos del repo pueden traer instrucciones escondidas.

### Sandbox: la segunda puerta

Los permisos deciden si algo corre; el sandbox decide qué puede tocar [Publicado].

- **Linux y Jetson:** bubblewrap o Landlock.
- **macOS:** Seatbelt.
- **Windows** es lo más difícil. Codex CLI lo resolvió en marzo de 2026 con tokens
  restringidos y permisos de archivos (ACL): sin escribir fuera de la carpeta del proyecto y
  sin red sin aprobación [Publicado].
- **Plan para Magnus:** en Windows no hay modo autónomo hasta tener sandbox. Mientras tanto,
  comandos con permiso uno por uno, u opción de correrlos en WSL2 o en un contenedor con el
  proyecto montado.

### Deshacer

Antes de cada edición se guarda un punto de control (copia o commit temporal). Hay un botón de
«deshacer los cambios del agente», y la bitácora dice qué tocó cada paso.

### Inyección de instrucciones

- **Todo es dato, no orden:** el contenido de archivos, la salida de comandos y la web.
  Nunca se ejecuta algo porque un archivo lo pida.
- **Secretos:** `.env`, llaves SSH y credenciales de nube se deniegan por defecto. Se ocultan
  en las salidas antes de enviarlas a un modelo remoto.
- **Aviso claro** cuando el turno va a la nube: **tu código sale del equipo**.

### Modelos [Publicado]

Programar con agentes exige buen uso de herramientas:

| Modelo | Tamaño en q4 | Dato |
|---|---|---|
| Devstral Small 24B | 14 GB | 46.8 % en SWE-bench Verified |
| Qwen3-Coder 30B-A3B | 19 GB | 256K de contexto |
| gpt-oss-20b | cabe en 16 GB | |
| Qwen3.6 27B | | |

Por debajo de ~14B fallan. En el Jetson medimos que los modelos de menos de 3B ni siquiera usan
las herramientas [Verificado]. Magnus recomienda el modelo según el equipo; si no alcanza,
sugiere el servidor de la red o Magnus Cloud, avisando que el código sale.

### Contexto del proyecto

- **`MAGNUS.md`** en la raíz: instrucciones del proyecto, el equivalente de CLAUDE.md.
  También lee `AGENTS.md` por compatibilidad.
- **Memoria por proyecto.**
- **Índice semántico del repositorio**, que es la unión con el RAG de pago (§14).

### El medidor también aquí

Por tarea: tokens, tiempo y costo. Por ejemplo: «esta tarea costó $0.00 en tu GPU; en la nube
habría costado $X».

### Cobro [Propuesta, decide Hugo]

| Plan | Incluye |
|---|---|
| Community | Camino A (Magnus como motor de Claude Code y otros) y `magnus code` en modo Preguntar con modelos locales. Atrae desarrolladores; OpenCode y Aider son gratis |
| **Pro** | Modo autónomo con sandbox, puntos de control ilimitados, índice semántico del repo (RAG), tareas en segundo plano o programadas y subagentes |
| **Team** | Reglas de permisos compartidas por la empresa (denegaciones que nadie anula) y bitácora de auditoría |

### Riesgos y etapas

- **Riesgos:** la seguridad es el mayor riesgo del producto; el sandbox de Windows; los modelos
  locales chicos que fallan en tareas largas; el costo de soporte.
- **Etapas:**
  1. **Beta:** camino A.
  2. **v1 (ene 2027):** Magnus Code alfa con modos Preguntar y Plan, en todas las plataformas.
     Modo autónomo solo en Linux y Jetson con sandbox.
  3. **v2:** sandbox en Windows y extensión para VS Code.

---

## 16. Monetizar sin servidores propios, y qué hacer con los anuncios

**Dato de Hugo (2026-09-21):** no tiene servidores propios. El B200 al que tiene acceso no se
puede dar por disponible para vender capacidad; primero hay que confirmar que ese uso esté
autorizado.

### Casi todo Magnus funciona sin un servidor de Hugo [Verificado / Publicado]

| Pieza | Dónde corre | ¿Necesita servidor de Hugo? |
|---|---|---|
| App, daemon, modelos (Ollama) | PC del usuario | No |
| RAG de pago | PC del usuario; la licencia firmada se valida sin internet | No |
| Magnus Code | PC del usuario | No |
| **Magnus como motor de Claude Code** | PC del usuario: Claude Code apunta `ANTHROPIC_BASE_URL` al daemon local | **No** |
| APIs con la clave del usuario | Cuenta del usuario (NVIDIA, Groq, OpenRouter) | No |
| Vender licencias Pro | Pasarela de pago + función sin servidor que firma y envía la licencia | Casi nada (capa gratuita) |
| **Magnus Cloud** | GPUs | **Sí: es lo único** |

**Cómo funciona «Magnus como motor de Claude Code» [Publicado]:**

- Claude Code lee `ANTHROPIC_BASE_URL` al arrancar y manda todo a esa dirección, añadiendo
  `/v1/messages`. Anthropic lo documenta en su página de «LLM gateways».
- Desde Ollama 0.14 (16-ene-2026), Ollama responde ese formato de forma nativa en
  `localhost:11434/v1/messages`.
- **Lo que añade Magnus en medio:**
  - el modelo recomendado para programar según el equipo;
  - el medidor por tarea;
  - la guarda de memoria;
  - claves por cliente;
  - el aviso si el turno sale a la nube.
- El usuario escribe `claude` en su PowerShell y todo corre en su GPU. Hugo no paga nada por
  cada uso.

### Magnus Cloud sin tener servidores: opciones en orden [Propuesta]

1. **No lanzarlo al principio.** La beta sale con equipo local, tu red y tu propia clave.
   Magnus Cloud espera a que haya demanda.
2. **El cliente pone la GPU y Hugo vende el software.** Team y Enterprise corren el mismo
   gateway (`cloud/`) en su propio servidor, con cuotas por persona. Se cobra licencia, no
   cómputo. Es el modelo más sano sin infraestructura propia.
3. **GPUs rentadas por hora, financiadas por lo prepagado.** Primero se venden paquetes (entra
   el dinero) y después se renta la capacidad (RunPod, Lambda o proveedores de DGX Cloud
   Lepton). El gateway corre en cualquier lado; solo cambia la dirección del servidor de modelos.
4. **El B200 al que Hugo tiene acceso**, solo si su dueño autoriza el uso comercial.
5. **Red de GPUs de la comunidad** (idea de v2, riesgosa): usuarios con RTX ociosas venden
   capacidad a través de Magnus y Magnus se queda una comisión, como Salad o Vast.ai. Una
   RTX 5090 gana $0.30–0.60 por hora [Publicado].
   - **Choca con la promesa de privacidad:** los datos del cliente corren en la PC de un
     extraño.
   - **La rentabilidad de estas redes no está probada** [Publicado].
   - Solo tendría sentido para trabajos no sensibles, o dentro de la flota de una misma empresa.

### Anuncios: recomendación, no ponerlos dentro de la app [Propuesta]

**Por qué no:**

- **Rompen la promesa central.** Las redes de anuncios necesitan rastreo y telemetría, y las
  convenciones del proyecto prohíben la telemetría saliente por defecto
  (`docs/CONVENTIONS.md`).
- **Espantan al cliente que paga.** Un despacho o una clínica no instala una app con anuncios
  para leer sus contratos o expedientes.
- **Dejan poco dinero.** Una app de escritorio con anuncios deja muy poco por usuario.
- **Dañan la confianza donde más importa:** en las respuestas del RAG y en el código.

**Lo que sí monetiza la atención sin traicionar la marca:**

| Vía | Cómo | Cuidado | Potencial |
|---|---|---|---|
| **Preinstalación con fabricantes e integradores** | Magnus preinstalado en PCs y laptops con RTX o RTX Spark de integradores mexicanos, cobrando por equipo vendido | Negociación comercial | Alto |
| **Afiliados en el momento justo** | Cuando «no cabe», sugerir la mejora concreta (RAM, GPU o un equipo compatible) con enlace de afiliado. Mercado Libre paga hasta 24 % en algunas categorías y pide redes sociales para ciertos beneficios; Amazon México no acepta afiliados nuevos por ahora; la electrónica paga 1–3 % [Publicado] | Etiqueta «Enlace de afiliado», sin rastreo, solo donde ayuda y con opción de apagarlo | Bajo a medio |
| **Catálogo con «Destacado»** | Un creador de modelos o un proveedor paga por aparecer destacado | Marcado «Patrocinado»; **nunca** cambia el veredicto de si cabe | Medio |
| **Marketplace** | Comisión de 20–30 % por skills y agentes de terceros | Revisión de seguridad de cada paquete | Medio |
| **Academia Magnus** | Cursos, certificación y talleres para empresas, en español | Tiempo de Hugo | Medio |

### Orden sugerido para ganar dinero sin servidores

1. Licencias Pro (RAG + Magnus Code).
2. Servicios y Enterprise (su GPU, tu software).
3. Preinstalación con integradores.
4. Afiliados en el momento justo.
5. Magnus Cloud cuando haya demanda, con GPUs rentadas y pagadas por lo prepagado.

---

## 12. Fuentes

Mercado y competencia:
- LM Studio 0.4.0 — https://lmstudio.ai/blog/0.4.0
- Precios de LM Studio 2026 — https://versustool.com/tool/lm-studio/pricing
- Precios de Msty — https://msty.ai/pricing/
- Precios de AnythingLLM — https://useanything.com/pricing
- Precios de Ollama — https://ollama.com/pricing
- Nueva app de Ollama — https://ollama.com/blog/new-app
- Open WebUI — https://www.glukhov.org/llm-hosting/llm-frontends/open-webui-overview-quickstart-and-alternatives/
- Msty, Ollama y LM Studio — https://localaimaster.com/blog/msty-vs-ollama-vs-lm-studio
- Cherry Studio — https://docs.cherryai.com.cn/docs/en-us
- Jan — https://dev.to/jovan_chan_9500711396d4e6/jan-ai-review-2026-13ei
- Ollama desde Android — https://dev.to/alichherawalla/how-to-use-ollama-from-your-android-phone-in-2026-auto-discovery-zero-setup-35li

NVIDIA y Microsoft:
- NVIDIA PAIR, blog técnico — https://developer.nvidia.com/blog/nvidia-pair-virtual-inference-router-expands-available-compute-on-your-local-network/
- NVIDIA en IFA 2026 — https://blogs.nvidia.com/blog/local-ai-ifa-next-gen-agents-nv-pair-rtx-spark/
- ChatRTX descontinuado — https://forums.developer.nvidia.com/t/chatrtx-has-been-deprecated-this-forum-is-locked/365743
- RTX Spark (CNBC) — https://www.cnbc.com/2026/05/31/nvidias-new-chip-to-power-fresh-line-of-windows-laptops-by-dell-hp.html
- RTX Spark, octubre y 128 GB — https://tech-insider.org/nvidia-rtx-spark-n1x-october-launch-2026/
- CUDA en Windows on Arm — https://blog.conan.io/cuda/gpu/armv8/arm64/windows/conan/nvidia/jetson/jetpack/2026/07/30/CUDA-Meets-Windows-On-Arm64-NVIDIA-RTX-Spark.html
- Microsoft Foundry en Windows — https://learn.microsoft.com/en-us/windows/ai/overview

Rendimiento y técnica:
- NVFP4 en llama.cpp — https://insiderllm.com/guides/fp4-inference-llamacpp-nvfp4-mxfp4/
- Speculative decoding y MTP — https://runaihome.com/blog/speculative-decoding-llama-cpp-local-llm-setup-2026/
- RTX 5080 — https://modelfit.io/gpu/rtx-5080/
- RTX 5090 — https://www.hardware-corner.net/rtx-5090-llm-benchmarks/
- RTX 5070 Ti contra 5060 Ti — https://computingforgeeks.com/rtx-5070-ti-vs-5060-ti-local-ai/
- Derrame a RAM — https://medium.com/@paulhoke/the-complete-guide-to-running-large-language-models-locally-in-2026-hardware-tools-and-da9efb3170be
- Indicador de ajuste de LM Studio — https://houtini.com/articles/how-to-set-up-lm-studio/
- Gemma 4 contra Qwen 3.6 — https://www.layer3labs.io/comparisons/gemma-4-vs-qwen-3-6
- Costo local contra API — https://www.sitepoint.com/local-llms-vs-cloud-api-cost-analysis-2026/

Respaldo en la nube:
- NVIDIA API Trial Terms of Service (PDF) — https://assets.ngc.nvidia.com/products/api-catalog/legal/NVIDIA%20API%20Trial%20Terms%20of%20Service.pdf
- NIM para desarrolladores (16 GPUs, solo desarrollo) — https://developer.nvidia.com/nim
- Límites de la capa gratuita de NVIDIA — https://decodethefuture.org/en/nvidia-nim-api-pricing-limits-guide/
- Precios de NVIDIA NIM — https://costbench.com/software/llm-api-providers/nvidia-nim/
- Groq, capa gratuita — https://tokenmix.ai/blog/groq-free-tier-limits-2026
- OpenRouter, modelos gratuitos — https://klymentiev.com/blog/openrouter-free-tier
- NVIDIA Inception — https://www.thundercompute.com/blog/nvidia-inception-program-guide

RAG y agentes de código:
- Permisos y sandbox de Claude Code — https://www.claudedirectory.org/blog/claude-code-permissions-guide
- Guía de sandbox de Claude Code — https://claudefa.st/blog/guide/sandboxing-guide
- Aprobaciones y seguridad de Codex — https://developers.openai.com/codex/agent-approvals-security
- Sandbox de Codex en Windows — https://developers.openai.com/codex/windows
- Modelos locales para programar — https://www.morphllm.com/best-ollama-models
- Modelos de código por VRAM — https://insiderllm.com/guides/best-local-coding-models-2026/
- RAG híbrido y reranking 2026 — https://aboullaite.me/rag-revisited-2026/
- Reranking — https://redis.io/blog/top-reranking-models-rag-accuracy/
- NeMo Retriever — https://developer.nvidia.com/blog/nvidia-nemo-retriever-delivers-accurate-multimodal-pdf-data-extraction-15x-faster/
- Open WebUI frente a AnythingLLM — https://wz-it.com/en/blog/open-webui-vs-anythingllm-comparison/

Monetizar sin servidores:
- Claude Code con otros backends (documentación oficial) — https://code.claude.com/docs/en/llm-gateway
- Compatibilidad de Ollama con la API de Anthropic — https://docs.ollama.com/api/anthropic-compatibility
- Ollama y Claude Code — https://ollama.com/blog/claude
- Comisiones de Amazon Afiliados México — https://afiliados.amazon.com.mx/help/node/topic/GRXPHT8U84RAYDXZ
- Afiliados de Mercado Libre en 2026 — https://www.xataka.com.mx/seleccion/mercado-libre-quiere-que-ganes-dinero-hot-sale-2026-asi-funciona-su-programa-afiliados-al-que-puede-unirse
- Redes de GPUs de consumo — https://www.tomshardware.com/pc-components/gpus/startups-pitch-an-airbnb-for-ai-inference-that-pays-gamers-for-their-idle-pcs
- Ganancias de rentar una GPU en Vast.ai — https://vast.ai/article/how-much-money-can-you-earn-renting-out-your-gpu-on-vast-ai

Seguridad y diseño:
- CrowdStrike sobre OpenClaw — https://www.crowdstrike.com/en-us/blog/what-security-teams-need-to-know-about-openclaw-ai-super-agent/
- Riesgos de OpenClaw — https://www.sangfor.com/blog/cybersecurity/openclaw-ai-agent-security-risks-2026
- Patrones de UX para agentes — https://hatchworks.com/blog/ai-agents/agent-ux-patterns/
- Material 3 Expressive — https://supercharge.design/blog/material-3-expressive
- Fluent 2 para Windows — https://fluent2.microsoft.design/components/windows
