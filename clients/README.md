# clients/

Reservado para los clientes que consumen la **API local del daemon**.

- **Fase 2:** cliente Flutter de escritorio (`clients/desktop/`).
- **Fase 3:** app móvil Flutter (`clients/mobile/`), reutilizando el mismo código.

Los clientes Flutter no contienen lógica de IA: solo consumen la API local
(`http://<host>:8420`).

- **`desktop/`** — iniciado. Flutter con clean architecture + BLoC y 3 diseños nativos
  (Windows/Material/macOS). Consume `/hardware`, `/models`, `/compatibility`. Ver
  [`desktop/README.md`](desktop/README.md). `flutter analyze` limpio.

Esta parte (frontend) se desarrolla aquí; el backend (Fase 1) lo ejecuta otra IA.
