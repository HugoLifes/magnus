# Plan de monetización sin servidores propios

**Fecha:** 2026-09-21.
**Para:** Hugo (decisiones y ventas) y la IA principal (implementación).
**Base:** [`INFORME_PRODUCTO.md`](INFORME_PRODUCTO.md), §11, §14, §15 y §16.
**Principio:** todo lo que se cobra corre en la PC del cliente o en su servidor. Magnus Cloud es
lo único que necesita GPUs, y espera a que haya demanda pagada por adelantado.

Etiquetas: **[Decide Hugo]**, **[IA principal]** (código), **[Negocio]** (sin código).

---

## 1. Qué se vende y en qué orden

| # | Qué | Quién paga | ¿Necesita servidor de Hugo? | Cuándo |
|---|---|---|---|---|
| 1 | **Magnus Pro**: RAG de pago + Magnus Code avanzado | Profesionales con RTX o RTX Spark | No: licencia firmada que se valida sin internet | Nov 2026 |
| 2 | **Servicios y Enterprise**: instalación, agentes a medida y su GPU con licencia | Empresas | No | Nov 2026 (primer piloto) |
| 3 | **Preinstalación con integradores**: licencia por equipo vendido | Ensambladores mexicanos | No | Dic 2026 (piloto) |
| 4 | **Afiliados en el momento justo** | Mercado Libre (comisión) | No | Ene 2027 |
| 5 | **Team**: el gateway de créditos en el servidor del cliente | Oficinas | No | Ene–mar 2027 |
| 6 | **Magnus Cloud** con GPUs rentadas | Quien compre paquetes | Solo al lanzarlo | Cuando se cumpla la regla de §7 |

**No se hace:** anuncios dentro de la app (informe §16) ni publicar el RAG bajo licencia
abierta.

---

## 2. Decisiones antes de empezar [Decide Hugo]

| Decisión | Recomendación | Fecha límite | Por qué urge |
|---|---|---|---|
| Licencia del repo | Núcleo Apache-2.0 en repo público; «Magnus Conocimiento» y Magnus Code avanzado en repo privado | 3 oct | Lo que se publica abierto no se cierra hacia atrás |
| Precio de Pro | $12 USD/mes o $119/año, con 14 días de prueba | 3 oct | $9 se queda corto con RAG + Code (informe §14) |
| Pasarela de pago | **Stripe** para suscripciones (renovaciones, facturas, webhooks). Mercado Pago después, para OXXO y transferencias | 10 oct | Sin pasarela solo se vende con vales |
| ¿Adjuntar un archivo cuenta como RAG? | No: dejarlo gratis como gancho, sin índice ni guardado | 10 oct | Define qué ve gratis el usuario |
| Reparto de Magnus Code | Modo Preguntar gratis; autónomo con sandbox, subagentes e índice del repo en Pro | 10 oct | Define qué se construye primero |
| Entidad para facturar | Persona física con actividad empresarial para empezar, o persona moral si entran socios. Validarlo con un contador | 31 oct | Para emitir CFDI a empresas y cobrar legalmente |

---

## 3. Fase 0 — Cimientos (22 sep – 3 oct 2026)

**[Negocio]**
- Registrar el dominio y buscar «Magnus» en el IMPI (clases 9 y 42). Si hay conflicto, cambiar
  el nombre ahora y no después de imprimir material.
- Aviso de privacidad (LFPDPPP) y términos de uso, revisados por un abogado antes de cobrar.
- Abrir la cuenta de la pasarela elegida y la de Mercado Libre Afiliados.

**[IA principal]**
- Agregar el archivo `LICENSE` según la decisión.
- Diseñar la **interfaz de plugins** del daemon. Un módulo privado se registra, agrega rutas y
  herramientas, y declara que exige la licencia `pro`. El RAG todavía no se mueve.

**Listo cuando:** las decisiones de §2 están tomadas, `LICENSE` está en el repo y la interfaz
de plugins está aprobada.

---

## 4. Fase 1 — Beta gratuita + motor de Claude Code (6 – 31 oct 2026)

Coincide con la salida de las laptops RTX Spark.

**[IA principal]**
1. **Endpoint compatible con Anthropic** (`/v1/messages`) en el daemon. Reenvía a Ollama (que
   lo habla desde la versión 0.14) y agrega el medidor, la guarda de memoria, la clave por
   cliente y el modelo recomendado para programar según el equipo.
2. **Comando `magnus claude`**: configura `ANTHROPIC_BASE_URL` y abre Claude Code contra la GPU
   local. Con una guía de una página: «Usa Claude Code con tu GPU».
3. **Sistema de licencias** (`core/license.py`):
   - Licencia firmada con Ed25519 (la clave pública va dentro del daemon) que dice plan,
     vigencia y número de equipos. Se valida sin internet, con 14 días de gracia.
   - `magnus license activate <archivo|vale>` y `GET /license`.
   - Las rutas marcadas `pro` responden **402** con un mensaje que explica qué incluye Pro.
4. **Pantalla de Pro en la app**: qué gana el usuario con sus propios documentos, el botón
   «Probar 14 días» y el campo para canjear un vale.
5. **Mover el RAG al módulo privado** con la interfaz de la fase 0. Community se queda con
   «adjuntar un archivo».
6. **Instalador de Windows con certificado de firma real.** El `.msix` actual usa uno de prueba.

**[Negocio]**
- Publicar la página para clientes (ya hay borrador), con lista de espera para Pro.
- Grabar un video de 2 minutos: instalar Magnus y tener Claude Code corriendo en una RTX sin
  pagar tokens.

**Listo cuando:** Claude Code funciona contra la GPU local en Windows y Linux, la licencia se
valida sin internet y el RAG sin licencia responde 402.

---

## 5. Fase 2 — Pro a la venta + primer piloto de empresa (nov 2026)

**[IA principal] — el RAG que justifica el pago (informe §14):**
1. Búsqueda híbrida: SQLite FTS5 + vectores, fusionados con RRF (el aforo ya lo usa).
2. Reranker local sobre los 20–50 mejores resultados.
3. OCR y tablas en PDF, además de Word y Excel.
4. Carpetas vivas que se reindexan solas.
5. Citas con archivo y página; responde «no está en tus documentos» cuando no hay evidencia.
6. Evaluación: el usuario pone 20 preguntas y ve un puntaje de qué tan bien encuentra.

**[IA principal] — cobrar sin servidor:**
- El webhook de la pasarela llama a una **función sin servidor** (capa gratuita, por ejemplo
  Cloudflare Workers) que firma la licencia con la clave privada y la envía por correo.
- La clave privada de firma nunca va en el repo ni dentro de la app.
- Los vales `MAG-…` se mantienen para ventas en persona y por integradores.

**[Negocio]**
- **Primer piloto Enterprise o de Servicios:** una empresa con GPU propia, con instalación y un
  agente a medida, cobrado como proyecto. La empresa de aforos es el caso de referencia natural.
- Kit de ventas: una hoja con precios, el video y el caso del aforo.

**Listo cuando:** un pago real genera una licencia sin intervención humana y hay un piloto
firmado.

---

## 6. Fase 3 — Magnus Code, integradores y afiliados (dic 2026 – ene 2027)

**[IA principal]**
1. **Magnus Code alfa** (informe §15):
   - Modos Preguntar y Plan en todas las plataformas.
   - Modo autónomo con sandbox solo en Linux y Jetson (bubblewrap o Landlock).
   - Reglas en orden denegar → preguntar → permitir, confianza por carpeta, puntos de control y
     tarjeta de aprobación.
2. **Licencias por equipo para integradores**: lotes de licencias, instalador silencioso y
   activación sin internet.
3. **Afiliados en el momento justo**: cuando un modelo no cabe, Magnus sugiere la mejora con un
   enlace marcado «Enlace de afiliado». Sin rastreo y con opción de apagarlo en Ajustes.

**[Negocio]**
- **Piloto con 2 o 3 integradores mexicanos** que ensamblan PCs con RTX: Magnus preinstalado
  con 3 meses de Pro incluidos, y comisión o precio por equipo.
- Evaluar el plan **Team**: el gateway de créditos en el servidor del cliente, con cuotas por
  persona.

**Listo cuando:** un integrador vende equipos con Magnus y 10 personas externas usan Magnus
Code alfa.

---

## 7. Fase 4 — Windows seguro y Magnus Cloud solo si se gana (feb – mar 2027)

**[IA principal]**
- Sandbox de Windows con tokens restringidos y ACL, como hizo Codex en marzo de 2026. Con eso
  se habilita el modo autónomo de Magnus Code en Windows.
- Conectores de Team y Enterprise (OneDrive/SharePoint, Drive) con permisos por documento.

**Regla para lanzar Magnus Cloud:** solo cuando lo **ya prepagado** cubra al menos un mes de GPU
rentada y al menos 30 clientes lo hayan pedido. Entonces:
- El gateway (`cloud/`, ya construido y probado en el Jetson) corre en cualquier lado.
- Se rentan GPUs por hora, y el precio de los paquetes se fija con el costo **medido** (costo
  por hora ÷ millones de tokens por hora), no con el estimado.

Si no se cumple la regla, Magnus Cloud se pospone. La promesa de «nunca te quedas sin IA» la
cubren la red del usuario y su propia clave.

---

## 8. Costos sin servidores (aproximados; verificar tarifas vigentes)

| Concepto | Costo |
|---|---|
| Dominio | Decenas de USD al año |
| Función sin servidor para las licencias | Capa gratuita |
| Pasarela de pago | Comisión por cobro, sin renta fija |
| Certificado de firma para Windows | Cientos de USD al año |
| Abogado y contador para empezar | Pago único |
| GPUs | **$0 hasta que se cumpla la regla de §7** |

---

## 9. Cómo saber si va bien (metas ilustrativas, no proyecciones)

| Momento | Meta |
|---|---|
| Fin de la fase 1 | 1,000 instalaciones; el 70 % llega a su primera respuesta en menos de 3 minutos |
| Fin de la fase 2 | El 5 % de los usuarios activos prueba Pro, el 25 % de las pruebas paga y hay 1 piloto de empresa |
| Fin de la fase 3 | 1 integrador vendiendo; 10 usuarios externos en Magnus Code alfa |
| Fin de la fase 4 | Ingreso mensual que cubra el certificado, las herramientas y el tiempo de soporte |

Todo se mide **sin telemetría**: descargas del instalador, licencias emitidas y pagos. Solo con
permiso explícito, una encuesta dentro de la app.

---

## 10. Riesgos y qué hacer

| Riesgo | Mitigación |
|---|---|
| El RAG de pago no se nota mejor que los gratuitos | Prueba de 14 días con los documentos del propio usuario y el puntaje de evaluación visible |
| Se filtra la clave de firma de licencias | Vive solo en la función sin servidor, con los secretos del proveedor; rotación y lista de revocación |
| Magnus Code causa daños en la PC de un usuario | Modo autónomo solo con sandbox; lo destructivo siempre pregunta; puntos de control |
| Los integradores no quieren software extra | Presentarlo como argumento de venta («esta PC trae IA lista»), con licencia incluida |
| Claude Code deja de aceptar otros endpoints | Magnus Code propio como alternativa; Codex CLI y OpenCode también se conectan |

---

## 11. Revisión del 2026-09-21 (con datos de mercado y de la red)

Esta sección no reemplaza el plan: ajusta lo que la investigación de septiembre deja distinto.
Los detalles técnicos de Magnus Code pasan a [`MAGNUS_CODE.md`](MAGNUS_CODE.md).

### 11.1 Dónde queda el precio de Pro [Publicado]

| Herramienta | Precio 2026 | Nota |
|---|---|---|
| GitHub Copilot | $10 Pro · $39 Pro+ · $19 por persona Business · $60 Enterprise | Desde junio 2026 cobra además créditos de IA (1 crédito = $0.01) |
| Cursor | $20 Pro · $60 Pro+ · $200 Ultra · $40 y $120 por asiento en equipos | El asiento de $120 es para uso intenso de agentes |
| Claude Code | $17 al mes en plan anual, $20 mensual | Quien lo usa fuerte acaba en $100–200 al mes |
| Cline, Aider, OpenCode, Goose, OpenHands | Gratis | Se paga el modelo: $20–150 al mes por persona, o $0 con Ollama |
| LM Studio | Gratis local; de pago para uso comercial en equipo | Su API en la nube cobra por millón de tokens |
| AnythingLLM | Gratis autohospedado; planes de pago en su nube | Competidor directo del RAG de Pro |

**Conclusión: los $12 al mes siguen bien puestos**, pero el argumento no es «más barato que
Copilot». Es **«no pagas tokens»**: frente a alguien que hoy gasta $20–150 al mes en API con
Cline o Claude Code, Pro se paga solo el primer mes. Ese es el mensaje de la página y del
video.

### 11.2 Seis cambios al plan

1. **Licencia perpetua como opción** [Decide Hugo]. Además de $12/mes y $119/año, ofrecer
   **$149 una vez, con 12 meses de actualizaciones** y $59/año si quiere seguir
   actualizando. Encaja con un producto que corre en la máquina del cliente, evita la
   fricción de la suscripción en México y es lo que los integradores saben vender.
2. **Pasarela: repartir por mercado** [Decide Hugo]. Con Stripe, el vendedor eres tú: tú
   emites CFDI y tú respondes por los impuestos digitales de cada país donde vendas. Un
   *merchant of record* (Paddle o Lemon Squeezy, 5 % + $0.50; Stripe Managed Payments, en
   vista previa desde febrero de 2026) asume esa parte. Recomendación: **MoR para ventas
   fuera de México** y **Mercado Pago o transferencia con CFDI para México**, que es donde
   están los primeros clientes.
3. **Certificado de firma: $9.99 al mes, no cientos al año.** Azure Trusted Signing (hoy
   Azure Artifact Signing) cuesta $9.99 al mes en su nivel básico, hasta 5 000 firmas, y
   emite certificados de corta vida desde una CA que Windows ya confía. Y desde 2024 un
   certificado EV **ya no salta SmartScreen**, así que pagar EV no compra nada. Actualizar la
   tabla de costos de §8.
4. **La fase 1 cuesta menos de lo planeado.** Ollama habla la API de Anthropic desde la
   versión 0.14, y en la PC de desarrollo (Ollama 0.34.1) el endpoint `/v1/messages` ya
   responde [Verificado]. El endpoint de Magnus es un **proxy con medidor, guarda de memoria y
   licencia**, no una implementación del protocolo. El tiempo que se ahorra ahí se va a
   permisos y sandbox, que es lo que de verdad diferencia.
5. **El riesgo legal del camino A queda aclarado.** Anthropic documenta `ANTHROPIC_BASE_URL`
   para proveedores externos; lo que sancionó en enero de 2026 fue que ciertas herramientas
   extrajeran el token OAuth de suscripciones de Claude Code. Regla interna: **Magnus nunca
   toca credenciales de suscripción ni redistribuye el binario de Claude Code**; solo
   configura variables de entorno en el equipo del usuario.
6. **Magnus Cloud, todavía más atrás en la fila.** Ollama y LM Studio ya venden tokens de
   modelos abiertos por su cuenta. La regla de §7 se mantiene y se endurece: no se lanza
   **hasta que Pro esté vendiéndose** y se cumpla lo prepagado.

### 11.3 Lo que no se puede vender como diferencia

Un CLI de agente más. Gratis y con comunidad grande ya existen OpenCode, Cline, Aider, Goose
(en la Linux Foundation desde abril de 2026) y OpenHands. La diferencia de Magnus, y lo que
debe decir cada texto de venta, es:

- **entiende el equipo** (no te deja cargar un modelo que no cabe, elige el que sí),
- **mide** (energía real, ahorro frente a la nube, por tarea),
- **pide permiso de verdad** y va a tener sandbox donde los demás no lo tienen bien (Windows),
- **está en español y con app de escritorio**, no solo terminal.

### 11.4 Riesgos añadidos

| Riesgo | Mitigación |
|---|---|
| El RAG de pago compite con gratuitos (AnythingLLM, LM Studio) | Lo que ya dice §10: prueba de 14 días con los documentos del propio usuario y puntaje de evaluación visible |
| Se depende de la compatibilidad de Ollama con Anthropic | El proxy de Magnus habla el protocolo por su cuenta si hace falta; el contrato ya está congelado en `docs/api/openapi-v1.json` |
| Las fechas del plan asumen que la beta 0.9 ya salió | Si la beta se mueve, se mueve todo: revisar fechas al cerrar la beta |

### 11.6 Estado al 2026-09-21

De la fase 1 ya está hecho, probado y en el repo:

- **Endpoint compatible con Anthropic** con medidor, guarda de memoria y elección de modelo
  (`POST /v1/messages`), más `magnus claude` para abrir Claude Code contra la GPU local.
- **Sistema de licencias** firmado con Ed25519 que se valida sin internet, con 14 días de
  gracia: `magnus license show|activate|deactivate|keygen|issue` y `GET/POST/DELETE /license`.
  La clave pública que va en el binario es **de desarrollo**: antes de vender hay que generar
  el par definitivo con `magnus license keygen`, guardar la privada en el emisor y reemplazar
  `DEV_PUBLIC_KEY_HEX`.
- **Catálogo con los modelos de código de 2026** (Devstral 24B, gpt-oss 20B, Qwen3-Coder 30B).

Queda de la fase 1: pantalla de Pro en la app, mover el RAG al módulo privado, el instalador
firmado y la función sin servidor que emite licencias al cobrar.

### 11.5 Fuentes de esta revisión

- Precios de herramientas de IA para programar: <https://getdx.com/blog/ai-coding-assistant-pricing/> y <https://www.cloudzero.com/blog/ai-coding-tools-cost/>
- Merchant of record y pasarelas: <https://fintechspecs.com/blog/stripe-vs-paddle-vs-lemon-squeezy-vs-polar-merchant-of-record-b2b-saas/>
- Firma de código en Windows: <https://azure.microsoft.com/en-us/pricing/details/trusted-signing/> y <https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options>
- Compatibilidad de Ollama con Anthropic: <https://docs.ollama.com/api/anthropic-compatibility>
- Términos de Claude Code: <https://code.claude.com/docs/en/third-party-integrations>
- Panorama de agentes de código abiertos: <https://www.openhands.dev/blog/open-source-ai-coding-agents>
