# Qué falta para el alpha

**Fecha:** 2026-09-23. **Rama:** `pre-prod`.
**Base:** [`BETA.md`](BETA.md) (estado del producto), [`MAGNUS_CODE.md`](MAGNUS_CODE.md)
(el agente de código) y [`PLAN_MONETIZACION.md`](PLAN_MONETIZACION.md) (cuándo se cobra).

---

## Qué llamamos alpha

**Entre 10 y 20 personas ajenas al proyecto instalando Magnus en su propio equipo
y usándolo una semana sin que nadie les lleve de la mano.** No es una demo
enseñada por Hugo: es alguien que descarga, instala y se queda solo con la app.

Esa definición manda en la lista de abajo. Todo lo que rompe esa frase es
bloqueante; lo demás espera.

---

## 1. Bloqueantes

| # | Qué falta | Por qué rompe el alpha | Dónde va | Trabajo |
|---|---|---|---|---|
| 1 | **El daemon no arranca solo** | La app abre y dice «Sin conexión». Hoy hay que saber abrir una terminal y escribir `magnus serve`: la mitad de la gente se cae aquí | La app lo lanza si el puerto no responde (`Process.start`), y el instalador lo deja al iniciar sesión (ya lo contempla `deploy/windows/install.ps1`) | 1–2 días |
| 2 | **Primer arranque guiado** | Quien abre por primera vez ve una app vacía. No sabe que necesita un modelo, ni cuál | Pantalla de 3 pasos: qué detectó del equipo → modelo recomendado con su descarga → primera pregunta. Ya existen las piezas (`/code/capability`, catálogo, descarga con progreso) | 2–3 días |
| 3 | **Instalador firmado** | Windows SmartScreen asusta con un aviso rojo; en un alpha eso se traduce en «me pidió permisos raros, lo borré» | Azure Trusted Signing, $9.99/mes (ver `PLAN_MONETIZACION.md` §11.2). Requiere que Hugo abra la cuenta | Medio día + trámite |
| 4 | **Cómo llega la siguiente versión** | En un alpha se publican correcciones cada pocos días; si cada una hay que pedirla por WhatsApp, el alpha se muere solo | Comprobación de versión contra una URL fija y aviso en la app, **opt-in y sin telemetría**: solo pregunta «¿hay algo más nuevo?» | 1 día |
| 5 | **Registro de errores local** | Cuando algo falla, el reporte es «no me anduvo». Sin un archivo que pegar, no hay forma de arreglarlo | `data/logs/magnus.log` con rotación, y un botón «copiar diagnóstico» que junte versión, hardware, últimas líneas y nada personal | 1 día |
| 6 | **Magnus Code en modo Preguntar** | Es la función que justifica probar Magnus y el diferencial frente a LM Studio o Jan. Sin ella, el alpha es «otro chat local» | Falta el bucle del agente (`core/code/session.py`), los puntos de control y la bitácora, la CLI interactiva y la tarjeta de aprobación en la app. Permisos, herramientas y terminal ya están | 5–8 días |

## 2. Importantes, pero no bloquean

| Qué | Por qué | Trabajo |
|---|---|---|
| Sandbox en Linux y Jetson (bubblewrap) | Habilita el modo autónomo donde sí hay memoria; en el alpha basta el modo Preguntar | 2–3 días |
| Guía de una página para el tester y cómo reportar | Reduce a la mitad los mensajes de «¿y esto cómo se usa?» | Medio día |
| Desinstalación limpia y documentada | En un alpha la gente entra y sale; dejar basura quema la confianza | Medio día |
| `e2e.py` en verde completo en la PC | Hoy 16 ok y 3 fallos, todos por no tener descargado `nomic-embed-text` | Una descarga |
| Qué pasa si el modelo se queda sin memoria a mitad | La guarda lo evita al cargar, pero no si otro programa se come la VRAM después | 1 día |

## 3. Puede esperar al beta público

- Sandbox de Windows (tokens restringidos): sin él, en Windows no hay modo autónomo, y está bien dicho en la app.
- Extensión de VS Code, subagentes, tareas programadas.
- Magnus Cloud: la regla de `PLAN_MONETIZACION.md` §7 sigue en pie.
- RAG de pago detrás de la licencia: en el alpha conviene que todo esté abierto para que lo usen.

---

## 4. Lo que **sí** está listo para el alpha [Verificado]

- Detección de hardware y catálogo según la memoria real, en toda la familia NVIDIA.
- Guarda de memoria al cargar (lo que evita colgar un Jetson).
- Chat con streaming, personalidad, skills, documentos y memoria.
- Medidor de coste y ahorro, con energía medida.
- Agentes con herramientas seguras, incluso con modelos cuya plantilla no emite `tool_calls`.
- API de mensajes de Anthropic: Claude Code contra la GPU local.
- Licencias firmadas que se validan sin internet.
- App en tres sistemas de diseño, con barra lateral plegable y estados de carga.
- 475 pruebas de Python, 8 de widgets, `ruff` y `flutter analyze` limpios, y
  `scripts/e2e.py` corriendo contra un equipo real.

---

## 5. Orden sugerido

1. **Semana 1:** bloqueantes 1, 2 y 5 (arranque, primer uso y diagnóstico). Con
   eso ya se puede dar a alguien sin explicarle nada.
2. **Semana 2:** bloqueante 6 (Magnus Code en modo Preguntar), que es lo que hace
   que valga la pena probarlo.
3. **En paralelo:** 3 y 4 (firma y actualizaciones), que dependen de trámites más
   que de código.
4. **Cierre:** etiquetar `v0.9.0-alpha.1` en `main` siguiendo `GIT.md` §4 y
   mandar el instalador con la guía de una página.
