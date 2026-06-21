# Convenciones

## Idioma
- **Código** (identificadores, nombres de funciones, módulos): inglés.
- **Docs, comentarios y mensajes al usuario** (CLI, errores): español.

## Python
- `from __future__ import annotations` en todos los módulos.
- Tipado en firmas públicas. `dataclass(frozen=True)` para datos inmutables.
- Sin lógica de negocio en `daemon/` ni en `cli/`: todo en `core/`.
- `core/` no importa de `daemon/` ni de `cli/` (dependencia en un solo sentido).
- `core/` debe poder ejecutarse y testearse **sin GPU**.
- Estilo: `ruff`. Tests: `pytest`. Sin dependencias nuevas pesadas sin justificarlo en el PR.

## API (daemon)
- Versionar el contrato. Añadir campos/endpoints: libre. Cambiar/quitar: solo con nota explícita.
- Respuestas JSON con `snake_case`. Errores con `HTTPException` y mensaje en español accionable.
- Streaming de tokens por WebSocket en `/chat`; cada turno cierra con resumen de medición.

## Unidades
- VRAM y memoria siempre en **GiB** (1024³). Documentar si en algún punto se usa GB decimal.
- Tokens: contar in/out por separado. Coste en USD, con la tabla de precios versionada.

## Datos y privacidad
- Persistencia local en `data/` (ignorado por git). Nada de datos de usuario en el repo.
- Cero telemetría saliente por defecto. Cualquier salida a red es **opt-in explícito**.

## Nombres y despliegue
- Convención de la organización: contenedores/servicios con prefijo **`nim_`** + nombre
  del proyecto (este: `nim_magnus`).
- Desplegar solo en servidores con autorización para correr cargas de trabajo.

## Git
- Commits pequeños y descriptivos. Una feature = `core` + `daemon` + `cli` + tests juntos.
- Rama por feature; `main` siempre desplegable.
