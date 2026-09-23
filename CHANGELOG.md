# Cambios

Lo que cambia **para quien usa Magnus**, no la lista de commits. Formato de
versiones en [`docs/GIT.md`](docs/GIT.md).

## Sin publicar (`pre-prod`)

### Nuevo

- **Magnus como motor de Claude Code**: el daemon habla la API de mensajes de
  Anthropic (`/v1/messages`), así que Claude Code, Codex CLI, OpenCode o Aider
  corren contra la GPU de tu equipo. `magnus claude` lo deja listo. Magnus elige
  el mejor modelo de código que tengas, comprueba que quepa en memoria y mide el
  turno.
- **Licencias firmadas que se validan sin internet**, con 14 días de gracia:
  `magnus license show|activate|deactivate` y, para vender, `keygen` e `issue`.
  En la app, Ajustes → Magnus Pro.
- **Personalidad del chat**: cinco formas de hablar (Magnus, Directo, Mentor,
  Compa, Técnico). En modelos pequeños el prompt se acorta solo para no gastar
  contexto. Se cambia en Ajustes o por turno con `magnus chat --persona`.
- **Qué puede hacer cada equipo** (`magnus code`, Inicio en la app): nivel del
  equipo, modos disponibles de Magnus Code y modelo recomendado con su descarga,
  con botón para bajarlo. Si no alcanza, dice qué hacer en su lugar.
- **Magnus Code, primeras piezas**: permisos con clasificación de riesgo,
  herramientas de leer/listar/buscar/editar/escribir y terminal con tiempo
  límite y cancelación real.
- El chat responde con **formato**: títulos, listas, negritas y bloques de
  código con botón de copiar.
- La **barra lateral se pliega en los tres temas** (antes solo en Windows), y el
  historial del chat también.

### Arreglado

- `/health` tardaba 18.7 s cuando Ollama estaba apagado en Windows; ahora
  responde en 0.2 s.
- Los agentes no usaban sus herramientas con modelos cuya plantilla no emite
  `tool_calls` (medido con qwen2.5-coder:7b): ahora se rescatan las llamadas que
  el modelo escribe como texto, solo si son herramientas permitidas.
- En PowerShell, un comando entre comillas no se ejecutaba y el código de salida
  no se propagaba: un `npm test` que fallaba parecía haber pasado.
- El `.gitignore` excluía por error el código de `features/models` de la app.
- El ahorro acumulado se enseñaba en negativo como si fuera un error; ahora dice
  «todavía no compensa» y explica por qué.

### Cambiado

- El acento por defecto es el violeta de la marca; el del sistema pasa a ser una
  opción en Ajustes.
- Los iconos son los nativos de cada plataforma: Fluent, Material y SF.
- En el chat, los ajustes del turno (modelo, dónde corre, documentos y
  razonamiento) viven en la caja de escribir; ya no hay barra superior.
- Catálogo con los modelos de código de 2026: Devstral 24B, Qwen3-Coder 30B y
  gpt-oss 20B.

## 0.9.0b1 — beta inicial

Detección de hardware de toda la familia NVIDIA, catálogo según la memoria real,
guarda de memoria al cargar, chat con medidor de coste y ahorro, skills, RAG y
memoria locales, agentes con herramientas seguras, token de acceso, instaladores
y app de escritorio con tres sistemas de diseño.
