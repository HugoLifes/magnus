"""Daemon de Magnus (FastAPI). Expone `core` por HTTP/WebSocket. Es el ÚNICO
contrato que consumen todos los clientes: CLI, app de escritorio Flutter y app
móvil Flutter. Si algo se añade aquí de forma estable, los tres lo heredan."""
