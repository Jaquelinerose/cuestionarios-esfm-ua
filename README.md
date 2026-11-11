# API de cuestionarios curriculares ESFM/UA

API REST implementada con Flask y SQLite para recibir y consultar cuestionarios DIR, DOC, EST y EGR.

> **Importante sobre el contenido:** la especificación recibida no incluye el documento ni el listado completo de preguntas. `cuestionarios.py` contiene ítems de ejemplo marcados como provisionales; no es una transcripción fiable del instrumento. Antes de usar la API para recolección real, reemplaza estos metadatos/ítems por el esquema oficial. El motor de validación y los endpoints ya están implementados.

## Ejecutar

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
ADMIN_API_KEY='una-clave-larga' python app.py
python -m unittest test_api -v
```

Variables de entorno: `ADMIN_API_KEY` (si falta, se genera e imprime una clave temporal), `DB_PATH` (por defecto `cuestionarios.db`), `PORT` (5000), `HOST` (127.0.0.1) y `CORS_ORIGINS` (por defecto `*`; lista de orígenes separada por comas también aceptada).

## Endpoints

| Método | Ruta | Acceso | Uso |
|---|---|---|---|
| GET | `/api/cuestionarios` | Público | Lista cuestionarios |
| GET | `/api/cuestionarios/{COD}` | Público | Esquema completo |
| GET | `/api/cuestionarios/{COD}/plantilla` | Público | Plantilla vacía |
| POST | `/api/respuestas/{COD}[?parcial=true]` | Público | Envía una respuesta |
| GET | `/api/respuestas` | `X-API-Key` | Lista y filtra respuestas |
| GET/DELETE | `/api/respuestas/{id}` | `X-API-Key` | Consulta o elimina una respuesta |
| GET | `/api/estadisticas/{COD}` | `X-API-Key` | Media y distribución de escalas 1–5 |
| GET | `/api/exportar/{COD}.csv` | `X-API-Key` | Exportación CSV UTF-8 con BOM |

Filtros de lista/estadísticas/exportación: `cuestionario`, `esfm_ua`, `ambito`, `sexo`, `especialidad`, `desde`, `hasta`; lista además acepta `limit` y `offset`.

El POST recibe `{ "identificacion": {...}, "respuestas": {...} }`. Las escalas admiten entero 1–5 o `{ "valor": n, "justificacion": "..." }`; las abiertas admiten texto y selección múltiple recibe `{ "opciones": [], "otros": "", "justificacion": "" }`. Los ítems de escala son obligatorios salvo `?parcial=true`; las preguntas abiertas son opcionales. Errores de validación: 422 con `detalles`; código de aplicación repetido por cuestionario: 409.

La tabla SQLite crea un índice para el código del cuestionario y aplica unicidad a `(cuestionario, codigo_aplicacion)`. Las operaciones administrativas requieren cabecera `X-API-Key`.
