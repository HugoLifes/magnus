# Ramas, versiones y qué se prueba antes de publicar

**Para:** Hugo y quien toque este repo (personas o IA).
**Resumen:** tres ramas con un papel claro, una versión en un solo archivo y una
lista corta de comprobaciones antes de que algo llegue a un equipo ajeno.

---

## 1. Las tres ramas

| Rama | Qué es | Quién la instala | Quién escribe en ella |
|---|---|---|---|
| `main` | **Producción.** Lo que se descarga un cliente | Clientes, integradores | Nadie directamente: solo fusiones desde `pre-prod`, y cada una lleva etiqueta |
| `pre-prod` | **Candidata.** Lo que se prueba en el Jetson y en la PC antes de publicar | Hugo y las pruebas | Fusiones desde ramas de trabajo |
| `feature/<nombre>` | **Pruebas.** El trabajo del día | Nadie | Quien esté con esa tarea |

El flujo, siempre en el mismo sentido:

```
feature/lo-que-sea  →  pre-prod  →  main (+ etiqueta)
```

De `main` nunca sale código hacia atrás salvo un arreglo urgente, y ese arreglo
se fusiona también a `pre-prod` el mismo día para que no se pierda.

**Por qué así y no GitFlow entero:** aquí trabaja una persona con ayuda de IA, no
seis equipos. Tres ramas se sostienen; seis se abandonan en dos semanas y acaban
mintiendo sobre lo que hay publicado.

---

## 2. La versión vive en un solo archivo

`core/version.py` manda. De ahí salen el daemon (`/health` y la documentación de
la API) y la CLI. `pyproject.toml` y el `pubspec.yaml` de la app la repiten
porque no pueden importar Python, y `tests/test_version.py` falla si alguna se
queda atrás.

Dos formatos del mismo número, porque cada ecosistema usa el suyo:

| Sitio | Formato | Ejemplo |
|---|---|---|
| `core/version.py`, `pyproject.toml` | PEP 440 | `0.9.0b1` |
| `pubspec.yaml`, etiquetas de git | SemVer | `0.9.0-beta.1` |

`core.version.semver()` y `core.version.tag()` hacen la traducción; no se escribe
a mano.

### Cuándo sube cada número

- **Parche** (`0.9.1`): arreglos que no cambian el contrato de la API.
- **Menor** (`0.10.0`): funciones nuevas; el contrato solo **añade**.
- **Mayor** (`1.0.0`): algo del contrato cambia o desaparece, o se quita una
  función. Con la licencia vendida por ahí, esto se avisa antes.
- **Prelanzamiento**: `a` alpha (se rompe), `b` beta (se usa, con fallos), `rc`
  candidata (va a producción salvo sorpresa).

---

## 3. Antes de subir a `pre-prod`

```bash
.venv/Scripts/python -m pytest -q          # 475 pruebas del núcleo y el daemon
.venv/Scripts/python -m ruff check .       # estilo
cd clients/desktop && flutter analyze      # app
cd clients/desktop && flutter test         # widgets
```

Los cuatro en verde. Si uno falla, no se fusiona: se arregla en la rama de
trabajo.

## 4. Antes de fusionar a `main` (publicar)

1. Las cuatro comprobaciones de arriba, en `pre-prod`.
2. **Prueba en vivo en los dos equipos**, que es donde aparecen los fallos de
   verdad:
   ```bash
   python scripts/e2e.py --modelo qwen2.5-coder:7b --rapido        # PC
   docker exec nim_magnus python scripts/e2e.py --modelo qwen3:0.6b # Jetson
   ```
3. La app **compila y abre** en Windows: `flutter build windows --release`.
4. `CHANGELOG.md` actualizado con lo que cambia para quien lo usa (no la lista de
   commits).
5. Subir la versión en `core/version.py`, `pyproject.toml` y `pubspec.yaml`.
6. Fusionar y etiquetar:
   ```bash
   git checkout main && git merge --no-ff pre-prod
   git tag -a v0.9.0-beta.1 -m "Beta 0.9.0-beta.1"
   ```

La etiqueta es lo que permite responder «¿qué versión tienes?» meses después,
cuando alguien reporte un fallo.

---

## 5. Mensajes de commit

En español, y contando **qué cambia para quien usa Magnus**, no qué archivos se
tocaron. Primera línea corta; debajo, el porqué y lo que se midió. Si un cambio
salió de un fallo real, se dice cuál: dentro de seis meses eso es lo único que
explica por qué el código es así.

---

## 6. Lo que nunca entra al repo

- Claves privadas de licencias (`emisor-*.key`), `.env`, credenciales.
- Modelos y datos de usuario: `/data/` y `/models/` están en `.gitignore`
  **anclados a la raíz**, porque sin la barra también ignoraban el código de
  `clients/desktop/lib/features/models/`, que estuvo sin subir por eso.
- Binarios de compilación (`build/`, `.dart_tool/`).
