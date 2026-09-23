"""Magnus Code: el agente que trabaja en el código y la terminal del usuario.

Aquí vive lo que el agente de chat (`core/agent.py`) no tiene a propósito: leer y
editar archivos y ejecutar comandos. Por eso la primera pieza que existe es la de
permisos, no la de ejecutar: nada se ejecuta sin pasar por `permissions`.

Diseño completo en `docs/MAGNUS_CODE.md`.
"""

from __future__ import annotations
