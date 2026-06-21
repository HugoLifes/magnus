# clients/

Reservado para los clientes que consumen la **API local del daemon**.

- **Fase 2:** cliente Flutter de escritorio (`clients/desktop/`).
- **Fase 3:** app móvil Flutter (`clients/mobile/`), reutilizando el mismo código.

Los clientes Flutter no contienen lógica de IA: solo consumen la API local
(`http://<host>:8420`). El cliente se genera a partir del OpenAPI del daemon
(`/openapi.json`) una vez congelado el contrato al final de la Fase 1.

Esta parte se desarrolla en otra sesión; no es tarea de la IA que ejecuta el backend.
