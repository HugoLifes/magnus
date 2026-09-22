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
