# API de cuestionarios curriculares (ESFM/UA)

API REST en Flask + SQLite para aplicar y registrar cuatro cuestionarios:
- `DIR` directivos
- `DOC` docentes formadores
- `EST` estudiantes
- `EGR` egresados/titulados

## Ejecutar

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
ADMIN_API_KEY='una-clave-larga' python app.py
python -m unittest test_api -v
```

Variables:
- `ADMIN_API_KEY` (si falta se genera una clave temporal y se imprime en el log)
- `DB_PATH` (por defecto `cuestionarios.db`)
- `PORT` (por defecto `5000`)
- `HOST` (por defecto `127.0.0.1`)
- `CORS_ORIGINS` (por defecto `*`)

## Endpoints

| Método | Ruta | Acceso | Uso |
|---|---|---|---|
| GET | `/api/cuestionarios` | público | Lista los 4 cuestionarios |
| GET | `/api/cuestionarios/{COD}` | público | Estructura completa |
| GET | `/api/cuestionarios/{COD}/plantilla` | público | Plantilla vacía |
| POST | `/api/respuestas/{COD}[?parcial=true]` | público | Envía un cuestionario llenado |
| GET | `/api/respuestas` | `X-API-Key` | Lista respuestas con filtros |
| GET/DELETE | `/api/respuestas/{id}` | `X-API-Key` | Ver o borrar una respuesta |
| GET | `/api/estadisticas/{COD}` | `X-API-Key` | Media y distribución por ítem |
| GET | `/api/exportar/{COD}.csv` | `X-API-Key` | CSV ancho UTF-8 con BOM |

## Formato de envío

```json
{
  "identificacion": {
    "esfm_ua": "ESFM Ejemplo",
    "especialidad": "Matemática",
    "ambito": "rural",
    "sexo": "F",
    "fecha": "2026-11-11",
    "codigo_aplicacion": "DOC-001",
    "anios_servicio": 12
  },
  "respuestas": {
    "1.1": 4,
    "1.2": {"valor": 5, "justificacion": "Aplico los principios del MESCP..."},
    "1.3": "Sí, porque ...",
    "PA1": "Texto libre ..."
  }
}
```

- Ítem de escala: número `1..5` o `{"valor": n, "justificacion": "..."}`.
- Ítem abierto: texto.
- Selección múltiple: `{"opciones": [...], "otros": "", "justificacion": ""}`.
- Campos extra de identificación: `DIR` admite `edad`; `DOC` admite `anios_servicio` y `evaluador` (opcional).
- Sin `?parcial=true` todas las preguntas escala son obligatorias; las abiertas son opcionales.
- Errores: `422` con `detalles`; `409` si `codigo_aplicacion` ya existe en ese cuestionario.

## Ajustes aplicados del documento original

- Escalas no indicadas se heredaron con la etiqueta correcta (`frecuencia`, `acuerdo`, etc.).
- `DIR 5.4` aparece dos veces; la segunda quedó como `5.4b`.
- `DIR 3.2a` se considera como seguimiento de `3.2`.
- Encabezados faltantes completados: `DIR D8`, `DOC D5`, `EST D4`, `EGR D8`.
- `DIR` no tiene `2.1`; la numeración se mantiene desde `2.2`.
- `8.1ª` corrigido a `8.1a`.
- `EST 5.4/5.5` y `DIR 5.5` usan escala de acuerdo por su redacción.

