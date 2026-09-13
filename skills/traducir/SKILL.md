---
name: traducir
description: Traduce entre español e inglés conservando el tono y el formato.
triggers:
- traduce
- traducir
- traducción
- translate
tools: []
---

Traduce el texto del usuario.

- Si está en español, tradúcelo al inglés; si está en otro idioma, al español,
  salvo que el usuario pida otro idioma.
- Conserva el tono (formal o coloquial) y el formato: listas, Markdown, saltos de línea.
- No traduzcas código, nombres de archivos, comandos ni nombres propios.
- Devuelve solo la traducción, sin explicaciones, salvo que haya una ambigüedad
  real; en ese caso añade una nota breve al final.
