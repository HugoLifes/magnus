# Magnus Code — especificación técnica

**Fecha:** 2026-09-21.
**Base:** [`INFORME_PRODUCTO.md`](INFORME_PRODUCTO.md) §15 (idea de producto) y
[`PLAN_MONETIZACION.md`](PLAN_MONETIZACION.md) (cuándo y en qué plan entra cada cosa).
**Qué añade este documento:** cómo se construye, con lo que se comprobó en la red y en el
equipo en septiembre de 2026.

Etiquetas: **[Verificado]** medido aquí · **[Publicado]** dato de una fuente citada en §15 ·
**[Propuesta]** decisión de diseño de este documento.

---

## 0. Lo que cambia respecto al informe §15

1. **El camino A ya no hay que construirlo entero.** Ollama habla la API de Anthropic
   (`/v1/messages`) desde la versión 0.14 [Publicado]. En esta PC, con Ollama 0.34.1, el
   endpoint responde con el formato de error de Anthropic (`not_found_error` con
   `request_id`) al pedirle un modelo que no está descargado [Verificado]. O sea: Claude Code
   contra la GPU local funciona hoy; lo que falta es que **Magnus se ponga en medio** para
   aportar lo suyo (medidor, guarda de memoria, elección de modelo, licencia).
2. **Apuntar Claude Code a otro endpoint está permitido.** Anthropic documenta
   `ANTHROPIC_BASE_URL` para proveedores externos [Publicado]. Lo que sancionó en enero de
   2026 fue otra cosa: herramientas que extraían el token OAuth de una suscripción de Claude
   Code para usarlo en sus propios clientes [Publicado]. Magnus no debe tocar credenciales de
   suscripción ni redistribuir el binario de Claude Code: solo configura variables de entorno
   en la máquina del usuario.
3. **La tabla de modelos del informe está vieja.** El 46.8 % de Devstral era la referencia de
   2025. Hoy hay modelos abiertos de 27–30 B muy por encima (§8).
4. **El índice semántico del repositorio no es el camino principal.** Los agentes que mejor
   funcionan en 2026 buscan con grep, no con vectores; en consultas cortas («auth flow»,
   «user service») la búsqueda semántica se desploma, y lo híbrido suma poco (+12.5 % según
   datos internos de Cursor) [Publicado]. Magnus Code usa **ripgrep primero**; el índice
   semántico queda como extra de Pro, no como requisito.
5. **El sandbox de Windows ya tiene receta pública.** Codex lo resolvió con tokens
   restringidos, SIDs sintéticos, ACL, cuentas de sandbox dedicadas y reglas de firewall, más
   un clasificador que lee el AST de PowerShell [Publicado] (§5).

---

## 1. Los dos caminos

| | A. Magnus como motor | B. Magnus Code |
|---|---|---|
| Qué es | El daemon expone `/v1/messages` (y `/v1/chat/completions` más adelante); el usuario corre Claude Code, Codex CLI, OpenCode, Cline o Aider contra su propia GPU | CLI `magnus code` y panel en la app, con permisos, sandbox, deshacer y medidor propios |
| Estado | **Hecho** (2026-09-21): `core/messages.py` + `POST /v1/messages` + `magnus claude`, con elección de modelo, guarda de memoria y medidor | **Empezado**: motor de permisos y clasificación de riesgo en `core/code/permissions.py`; faltan herramientas, terminal y sandbox |
| Esfuerzo | Bajo | Alto |
| Valor | Gancho: «tu GPU, sin pagar tokens» | El diferenciador |
| Plan | Community | Preguntar/Plan en Community; autónomo y extras en Pro |

El camino A es el que trae gente; el B es el que se cobra. Se hacen en ese orden.

### Lo que el proxy de Magnus aporta sobre Ollama pelado

- **Guarda de memoria**: rechaza cargar un modelo que no cabe, en vez de reventar a medio
  turno (`core/compatibility.py`, ya existe).
- **Medidor**: tokens, energía medida y ahorro frente a la nube, por tarea (`core/metering.py`).
- **Elección del modelo según el equipo** (`core/platform.py`, `core/catalog.py`): si el
  usuario pide un modelo que no cabe, Magnus propone el que sí.
- **Una clave por cliente** y las reglas de acceso del daemon (`core/security.py`).
- **Desvío** al servidor de la red o a la nube cuando el equipo no da, avisando que el código
  sale del equipo (`core/providers.py`).

---

## 2. Arquitectura en este repo

Respeta las convenciones: la lógica vive en `core/`, el daemon y la CLI solo exponen.

```
core/code/
  session.py      # el bucle del agente: plan → herramienta → resultado → repetir
  tools/          # una herramienta por archivo, con esquema JSON y límites
  permissions.py  # reglas denegar → preguntar → permitir y clasificación de riesgo
  shell.py        # ejecutar comandos: PTY, árbol de procesos, tiempos y topes
  sandbox/        # linux.py (bubblewrap/Landlock), macos.py (Seatbelt), windows.py
  context.py      # MAGNUS.md, mapa del repo, búsqueda con ripgrep
  checkpoints.py  # puntos de control y deshacer
  redact.py       # tapar secretos antes de mandar nada a un modelo
  journal.py      # bitácora append-only de todo lo que hizo el agente
daemon/app.py     # /code/session (WS), /code/approve, /code/undo, /v1/messages (proxy)
cli/main.py       # magnus code [--modo] [--modelo]
clients/desktop   # panel con terminal, vista de cambios y tarjeta de aprobación
```

Reglas que no se rompen: `core/` no importa de `daemon/` ni de `cli/`, y todo `core/code/` se
puede probar sin GPU (el modelo se inyecta como dependencia, igual que en `core/chat.py`).

---

## 3. Herramientas del agente

Pocas y bien hechas: los modelos locales se pierden con catálogos grandes (§9).

| Herramienta | Qué hace | Límites duros |
|---|---|---|
| `leer` | Lee un archivo o un rango de líneas | Solo dentro del proyecto; máx. 400 KiB; binarios no |
| `listar` | Lista por patrón (glob) | No sigue enlaces simbólicos fuera del proyecto |
| `buscar` | ripgrep, con filtro por tipo de archivo | Máx. 200 resultados, con recorte por línea |
| `editar` | Reemplazo exacto de un bloque | Falla si el bloque no aparece una sola vez |
| `escribir` | Crea o reemplaza un archivo | Pide permiso siempre fuera de `src/` y equivalentes |
| `comando` | Ejecuta en la terminal | §4 y §6 |
| `git` | Estado, diferencias, rama, commit | `push`, `reset --hard` y `--force` son destructivos |
| `web` | Consulta una URL | **Apagada por defecto**; su salida es dato, nunca orden |
| MCP | Herramientas del usuario | §10 |

### Formato de edición [Propuesta]

Bloques de **búsqueda y reemplazo exactos**, no diff unificado. El benchmark Diff-XYZ de 2026
encuentra que buscar-y-reemplazar es la representación más efectiva, y que el diff unificado
queda consistentemente por debajo; reescribir el archivo entero es lo más estable en
conversaciones largas pero gasta muchos más tokens [Publicado].

La regla práctica: **buscar-y-reemplazar** de base; si el archivo tiene menos de ~200 líneas y
el modelo falla dos veces seguidas, se pide el archivo completo. Cada edición se aplica sobre
el texto exacto del disco; si no coincide, el error vuelve al modelo con las líneas reales.

---

## 4. Permisos

El orden es **denegar → preguntar → permitir**, y una denegación puesta por la empresa no se
puede anular [Publicado, igual que Claude Code]. Los permisos deciden *si* algo corre; el
sandbox decide *qué puede tocar* (§5). Son dos puertas distintas y se necesitan las dos.

**Modos**

| Modo | Leer | Editar | Comandos |
|---|---|---|---|
| Plan | Sí | No | No |
| Preguntar (por defecto) | Sí, dentro del proyecto | Pide permiso | Pide permiso |
| Aceptar ediciones | Sí | Libre dentro del proyecto | Pide permiso |
| Autónomo | Sí | Libre | Libre dentro del sandbox, salvo lo destructivo |

**Reglas por patrón**, en un archivo del proyecto y otro del usuario:
`Comando(git status)` permitir · `Comando(npm test*)` permitir · `Editar(src/**)` preguntar ·
`Leer(.env)` **denegar**.

**Clasificación de riesgo antes de preguntar.** Cada comando se analiza y se etiqueta:
lectura, escritura en el proyecto, red, fuera del proyecto o destructivo. Lo destructivo
(`rm -rf`, `Remove-Item -Recurse`, `git push --force`, formatear, tocar el registro, `dd`)
**siempre pregunta, incluso en modo autónomo**, y algunas cosas se bloquean sin opción.

Para clasificar de verdad hay que **parsear**, no buscar cadenas:

- En Unix, se parte la línea respetando comillas y se resuelven encadenados (`&&`, `|`, `;`),
  sustituciones (`$(...)`) y redirecciones. Si aparece algo que no se puede inspeccionar
  (`eval`, `bash -c` con variable, `curl | sh`), **se pregunta**.
- En Windows se hace lo mismo con el AST de PowerShell, que es la solución de Codex: cualquier
  región ejecutable que el clasificador no pueda inspeccionar —`Invoke-Expression`,
  `-EncodedCommand`, scripts con punto— exige aprobación explícita [Publicado]. Se obtiene
  llamando a `[System.Management.Automation.Language.Parser]::ParseInput` desde un
  `pwsh -NoProfile` auxiliar.

**Tarjeta de aprobación** (diseño en el informe §8.5): el comando exacto, lo que el modelo dice
que hará, la carpeta, el riesgo y tres opciones: permitir una vez, permitir siempre **este
comando en este proyecto**, o rechazar. Si rechaza, el motivo vuelve al modelo.

**Confianza por carpeta.** La primera vez que se abre un proyecto, Magnus pregunta si se
confía en esa carpeta, porque sus archivos pueden traer instrucciones escondidas (§10). Sin
confianza: modo Plan y nada más.

---

## 5. Sandbox por sistema

Lo que hacen los demás en 2026 [Publicado]:

| Agente | Linux | macOS | Windows |
|---|---|---|---|
| Codex CLI | Landlock + seccomp (bubblewrap de reserva) | Seatbelt | Tokens restringidos + AppContainer |
| Claude Code | Seatbelt o bubblewrap con proxy de red | Seatbelt | — |
| Gemini CLI | Docker/Podman | Seatbelt | Docker/Podman |

Casi todos van con **red denegada por defecto** y lista de permitidos para gestores de
paquetes.

**Plan de Magnus** [Propuesta]:

1. **Linux y Jetson (primero):** `bubblewrap` si está instalado; carpeta del proyecto como
   único punto de escritura, `/tmp` privado, red apagada salvo que la tarea la pida. Landlock
   después, para no depender de un binario externo.
2. **macOS:** `sandbox-exec` con un perfil de Seatbelt propio.
3. **Windows (lo caro):** copiar el diseño de Codex —token con `WRITE_RESTRICTED`, SID
   sintético con ACL de escritura solo en la carpeta del proyecto y, cuando hay permisos de
   administrador, dos cuentas locales dedicadas (una con firewall que corta la red)
   [Publicado]. Mientras eso no exista: **sin modo autónomo en Windows**, comandos de uno en
   uno, y la opción de correrlos en WSL2 o en un contenedor con el proyecto montado.

Aviso honesto en la documentación: el modo sin privilegios de administrador **no** puede
impedir escrituras en carpetas que ya dan permiso a «Todos» [Publicado]. Se dice, no se
esconde.

---

## 6. La terminal

- **Shell:** en Windows, PowerShell 7 (`pwsh`) y si no está, Windows PowerShell 5.1; en Linux,
  macOS y Jetson, `bash` o `zsh`. WSL2 como opción.
- **Cómo corre:** pseudo-terminal (ConPTY en Windows, `pty` en Unix) para que los programas se
  comporten como con una persona delante; carpeta de trabajo fija en el proyecto; tiempo
  límite por comando (120 s por defecto, ampliable con permiso); salida en vivo con tope
  (200 KiB, recortando por el medio y avisando).
- **Cancelar de verdad:** Job Object en Windows y grupo de procesos en Unix, para matar
  también a los hijos.
- **Entorno saneado:** se quitan claves y tokens del entorno (`*_API_KEY`, `*_TOKEN`,
  `AWS_*`, `ANTHROPIC_*`) antes de lanzar nada. Lo que el comando imprima pasa por `redact.py`
  antes de volver al modelo.
- **Nada de shells interactivos:** si el comando espera entrada, se corta con un mensaje claro.

---

## 7. Contexto del proyecto

- **`MAGNUS.md`** en la raíz (y `AGENTS.md` por compatibilidad): instrucciones del proyecto.
- **Búsqueda antes que índice:** el agente encuentra con `buscar` (ripgrep) y `listar`, que
  siempre ven el código de ahora mismo, sin índice que mantener [Publicado].
- **Mapa del repo:** un resumen con las firmas de cada archivo (tree-sitter), al estilo de
  Aider, que se manda una vez por sesión y se recorta al presupuesto de contexto.
- **Índice semántico (Pro):** reutiliza el RAG del informe §14 para preguntas de tipo «dónde
  se decide el precio», donde las palabras exactas no aparecen. Es un extra, no la base.
- **Compactación:** cuando el contexto se llena, se resume lo viejo y se conserva la lista de
  archivos tocados y las decisiones. Sin esto, los modelos locales de 32 K se ahogan.

---

## 8. Modelos, por equipo

Datos de septiembre de 2026 [Publicado]:

| Modelo | Tamaño q4 | Dato | Dónde corre |
|---|---|---|---|
| `qwen2.5-coder:7b` | 4.4 GiB | Tiene herramientas en la plantilla | RTX 8 GiB, Jetson justito |
| `devstral:24b` | ~14 GiB | 46.8 % SWE-bench Verified; pensado para agentes | RTX 16 GiB |
| `gpt-oss:20b` | ~16 GiB | 128 K de contexto | RTX 16 GiB |
| `qwen3.6:27b` | ~17 GiB | **77.2 % SWE-bench Verified**, 59.3 % Terminal-Bench 2.0, Apache-2.0 | RTX 24 GiB, Spark |
| `qwen3-coder:30b-a3b` | ~19 GiB | 256 K de contexto, 3.3 B activos: rápido | RTX 24–32 GiB, Spark |
| `qwen3-coder-next` | 52 GiB | 80 B con 3 B activos, 256 K | Solo servidor de la red o DGX Spark |

Tres avisos que salen de la investigación:

- **Las herramientas son cosa de la plantilla, no del tamaño** [Publicado]: hay etiquetas del
  mismo modelo que no traen `tools`. El catálogo de Magnus debe marcar la etiqueta exacta que
  sí las trae y probarlo, no suponerlo.
- **Contexto mínimo 32 K** para agentes, según la propia documentación de Ollama [Publicado].
  Con 4 096 (lo que Magnus fija hoy en el Jetson) no hay Magnus Code.
- **Cuidado con las variantes**: algunos GGUF de Qwen3.6 con archivos de visión no cargan en
  Ollama [Publicado]. Verificar cada etiqueta antes de meterla al catálogo.

**Por equipo** [Propuesta]: Jetson Orin Nano de 8 GiB → solo Plan y Preguntar con 7 B, o
desviar al servidor de la red. RTX de 4–8 GiB (como la GTX 1650 de esta PC) → Plan y Preguntar
con 7 B, y el aviso de que para tareas largas conviene otro equipo. 16 GiB → Devstral o
gpt-oss. 24 GiB o más y DGX Spark → Qwen3.6-27B o Qwen3-Coder-30B, que es donde Magnus Code
compite de verdad.

---

## 9. Harness para modelos locales

Lo que hace que un modelo de 7–27 B rinda como agente [Propuesta, apoyado en lo publicado]:

1. **Pocas herramientas a la vista.** Cinco o seis; el resto se activan por fase.
2. **Una acción por turno**, con el resultado antes de pedir la siguiente.
3. **Llamada a herramientas nativa, no JSON forzado.** Forzar formatos rígidos reduce las
   llamadas a herramientas: hay trabajo de 2026 que lo mide y lo llama «impuesto de
   restricción» [Publicado]. Se valida el esquema y, si falla, se devuelve el error concreto.
4. **Presupuesto de pasos** por tarea (20 por defecto) y de tiempo, con resumen al llegar.
5. **Errores útiles**: cuando una edición no aplica, se devuelven las líneas reales del archivo.
6. **Plan explícito primero** en tareas de más de un archivo: el plan se muestra y se aprueba.

---

## 10. Inyección de instrucciones y MCP

El patrón de todos los incidentes es el mismo: un agente con acceso a datos privados, expuesto
a contenido no confiable y con manera de comunicarse hacia fuera [Publicado]. Magnus Code
tiene las tres cosas, así que:

- **Todo lo que el agente lee es dato, no orden**: archivos, salida de comandos, páginas web y
  descripciones de herramientas. Si un archivo dice «ejecuta esto», se le enseña al usuario, no
  se ejecuta.
- **Modelo privilegiado / modelo en cuarentena** para lo más expuesto (web y salidas largas):
  el que tiene herramientas no lee el contenido crudo, recibe un resumen estructurado
  [Publicado]. Con modelos locales esto cuesta una segunda pasada; se aplica al contenido de
  red, que es el más peligroso.
- **Permitir, bloquear o tapar** en tiempo de ejecución: los secretos se tapan antes de salir
  (`redact.py`) y `.env`, llaves SSH y credenciales de nube están denegados de fábrica.
- **Salida a la red = permiso aparte.** Que el agente pueda leer un archivo no significa que
  pueda mandarlo a ningún lado.
- **MCP con correa corta.** El envenenamiento de herramientas —instrucciones escondidas en la
  descripción de una herramienta— es un problema real y documentado, con casos de robo de
  claves SSH [Publicado]. Magnus: MCP apagado por defecto; alta por servidor con aprobación;
  se guarda el hash de cada descripción y, si cambia, se vuelve a preguntar; y un servidor no
  ve las credenciales de otro.

---

## 11. Deshacer, bitácora y medidor

- **Punto de control antes de cada edición**: un commit en una rama oculta de git si el
  proyecto usa git; copia de los archivos si no. `magnus code undo` vuelve atrás.
- **Bitácora append-only** (JSONL en `data/`): cada herramienta, argumentos, resultado
  recortado, permiso concedido y por quién. Es lo que hace auditable el plan Team.
- **Medidor por tarea**: tokens, tiempo, energía medida y la comparación honesta: «esta tarea
  costó $0.00 en tu GPU; en la nube habría costado $X».

---

## 12. Cómo se prueba

- **Tareas propias, verificables**: 20 tareas pequeñas sobre este mismo repo (arreglar un test
  que falla, añadir un endpoint, renombrar en tres archivos), cada una con su comprobación
  automática. Es un Terminal-Bench casero y basta para comparar modelos y cambios del harness.
- **Métricas que importan**: tareas completadas, ediciones aplicadas sin reintento, pasos por
  tarea, aprobaciones pedidas y cuántas se aceptaron, y tiempo hasta el primer cambio útil.
- **Regresión de seguridad**: un repositorio de prueba con archivos que traen instrucciones
  escondidas; ninguna debe ejecutarse. Esto se corre en cada versión.
- Todo se suma a `scripts/e2e.py`, que ya corre contra el Jetson.

---

## 13. Etapas y qué entra en cada plan

| Etapa | Contenido | Plan |
|---|---|---|
| 1 ✅ (2026-09-21) | Camino A: `/v1/messages` con medidor, guarda y licencia; `magnus claude` | Community |
| 2 (nov–dic) | `magnus code` en modos Plan y Preguntar: leer, buscar, editar, comandos con permiso, deshacer, bitácora y medidor | Community |
| 3 (ene 2027) | Sandbox en Linux y Jetson → modo autónomo ahí; panel en la app con terminal y vista de cambios; MAGNUS.md y mapa del repo | Autónomo e índice del repo en **Pro** |
| 4 (feb–mar) | Sandbox de Windows (tokens restringidos); subagentes; tareas en segundo plano | **Pro** |
| 5 | Extensión de VS Code; reglas de permisos de empresa y auditoría | **Team** |

La regla de reparto no cambia respecto al plan de monetización: **lo que pide permiso es
gratis; lo que corre solo con red de seguridad es de pago.**

---

## 14. Riesgos

| Riesgo | Qué se hace |
|---|---|
| Un comando del agente rompe el equipo de alguien | Lo destructivo siempre pregunta; autónomo solo con sandbox; punto de control antes de cada edición |
| Inyección de instrucciones desde el repo o la web | §10, y la suite de regresión de seguridad de §12 |
| El modelo local no alcanza y la experiencia decepciona | Magnus dice desde el principio qué puede hacer este equipo; desvío al servidor de la red con aviso de que el código sale |
| «Otro CLI más» en un mercado lleno (OpenCode, Cline, Goose, OpenHands, todos gratis) | La ventaja no es el CLI: es el hardware entendido (guarda de memoria, modelo por equipo), el medidor, el sandbox en Windows y la app en español |
| Mantener el sandbox de tres sistemas | Por etapas, y no prometer autónomo donde no hay sandbox |

---

## 14b. Lo que ya está construido [Verificado]

| Pieza | Dónde | Probado con |
|---|---|---|
| Proxy de la API de mensajes | `core/messages.py`, `POST /v1/messages` | `tests/test_messages_proxy.py` (10 casos) |
| Elección de modelo y guarda de memoria | `MessagesProxy.resolve_model` / `_prepare` | idem |
| Medidor de los turnos del proxy | `Store.record_turn`, tabla `turns` | idem y `tests/test_store.py` |
| Licencias firmadas y sin internet | `core/license.py`, `/license`, `magnus license` | `tests/test_license.py` (16 casos) |
| Permisos y riesgo de comandos | `core/code/permissions.py` | `tests/test_code_permissions.py` (58 casos) |
| Abrir Claude Code contra la GPU | `magnus claude` | a mano, en Windows |

Lo siguiente, por orden: herramientas del agente (§3), terminal (§6) y sandbox de Linux (§5).

## 15. Fuentes

- Ollama, compatibilidad con la API de Anthropic: <https://docs.ollama.com/api/anthropic-compatibility>
- Claude Code, proveedores externos: <https://code.claude.com/docs/en/third-party-integrations>
- Términos de Claude Code, análisis: <https://autonomee.ai/blog/claude-code-terms-of-service-explained/>
- Sandbox de Codex en Windows: <https://codex.danielvaughan.com/2026/07/18/codex-cli-windows-sandbox-architecture-powershell-ast-safety-elevated-unelevated-appcontainer-restricted-tokens/>
- Lista de sandboxes de agentes: <https://gist.github.com/wincent/2752d8d97727577050c043e4ff9e386e>
- Aprobaciones y seguridad en Codex: <https://developers.openai.com/codex/agent-approvals-security>
- Grep frente a vectores: <https://www.mindstudio.ai/blog/is-rag-dead-what-ai-agents-use-instead> y <https://www.morphllm.com/agentic-search>
- Formatos de edición (Diff-XYZ): <https://arxiv.org/pdf/2510.12487>
- Impuesto de restricción en salidas estructuradas: <https://arxiv.org/pdf/2606.25605>
- Defensa de inyección de prompts: <https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html> y <https://www.fiddler.ai/blog/prompt-injection-prevention-coding-agents>
- Envenenamiento de herramientas MCP: <https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks> y <https://owasp.org/www-community/attacks/MCP_Tool_Poisoning>
- Modelos abiertos para código: <https://www.morphllm.com/best-ollama-models> y <https://www.buildfastwithai.com/blogs/qwen3-6-27b-review-2026>
- Llamada a herramientas en Ollama: <https://docs.ollama.com/capabilities/tool-calling>
