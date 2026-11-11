import csv
import io
import json
import os
import secrets
import sqlite3
from datetime import date
from functools import wraps

from flask import Flask, Response, current_app, jsonify, request

from cuestionarios import QUESTIONARIOS, get_questionario


COMMON_IDENTIFICATION = ("esfm_ua", "especialidad", "ambito", "sexo", "fecha", "codigo_aplicacion")
REQUIRED_IDENTIFICATION = {
    "DIR": COMMON_IDENTIFICATION,
    "DOC": COMMON_IDENTIFICATION + ("anios_servicio",),
    "EST": COMMON_IDENTIFICATION,
    "EGR": COMMON_IDENTIFICATION,
}


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DB_PATH=os.environ.get("DB_PATH", os.path.join(os.getcwd(), "cuestionarios.db")),
        ADMIN_API_KEY=os.environ.get("ADMIN_API_KEY"),
        CORS_ORIGINS=os.environ.get("CORS_ORIGINS", "*"),
        MAX_CONTENT_LENGTH=1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    if not app.config["ADMIN_API_KEY"]:
        app.config["ADMIN_API_KEY"] = secrets.token_urlsafe(32)
        app.logger.warning("ADMIN_API_KEY temporal generada: %s", app.config["ADMIN_API_KEY"])

    init_db(app.config["DB_PATH"])

    @app.after_request
    def add_cors_headers(response):
        origins = current_app.config["CORS_ORIGINS"]
        origin = request.headers.get("Origin")
        allowed = "*" if origins == "*" else origin if origin and origin in [x.strip() for x in origins.split(",")] else None
        if allowed:
            response.headers["Access-Control-Allow-Origin"] = allowed
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Key"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
        return response

    @app.get("/api/cuestionarios")
    def list_questionnaires():
        return jsonify({"cuestionarios": [
            {"codigo": q["codigo"], "nombre": q["nombre"], "descripcion": q["descripcion"], "provisional": q.get("provisional", False)}
            for q in QUESTIONARIOS.values()
        ]})

    @app.get("/api/cuestionarios/<codigo>")
    def questionnaire_detail(codigo):
        questionnaire = get_questionario(codigo)
        if not questionnaire:
            return not_found("Cuestionario")
        return jsonify(questionnaire)

    @app.get("/api/cuestionarios/<codigo>/plantilla")
    def questionnaire_template(codigo):
        questionnaire = get_questionario(codigo)
        if not questionnaire:
            return not_found("Cuestionario")
        identification = {field: "" for field in COMMON_IDENTIFICATION}
        if codigo.upper() == "DOC":
            identification["anios_servicio"] = None
        if codigo.upper() == "DIR":
            identification["edad"] = None
        answers = {item["id"]: None for dimension in questionnaire["dimensiones"] for item in dimension["items"]}
        return jsonify({"cuestionario": codigo.upper(), "identificacion": identification, "respuestas": answers})

    @app.post("/api/respuestas/<codigo>")
    def submit_response(codigo):
        code = codigo.upper()
        questionnaire = get_questionario(code)
        if not questionnaire:
            return not_found("Cuestionario")
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "El cuerpo debe ser un objeto JSON válido."}), 400
        identification = payload.get("identificacion")
        answers = payload.get("respuestas")
        partial = request.args.get("parcial", "false").lower() in ("true", "1", "yes")
        errors = validate_identification(code, identification)
        items = {item["id"]: item for dimension in questionnaire["dimensiones"] for item in dimension["items"]}
        errors.extend(validate_answers(items, answers, partial))
        if errors:
            return jsonify({"detalles": errors}), 422

        clean_identification = dict(identification)
        clean_answers = {item_id: normalize_answer(items[item_id], value) for item_id, value in answers.items()}
        try:
            with connect() as db:
                cursor = db.execute(
                    "INSERT INTO respuestas (cuestionario, codigo_aplicacion, identificacion, respuestas) VALUES (?, ?, ?, ?)",
                    (code, clean_identification["codigo_aplicacion"].strip(), json.dumps(clean_identification, ensure_ascii=False), json.dumps(clean_answers, ensure_ascii=False)),
                )
                response_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            return jsonify({"error": "El codigo_aplicacion ya existe para este cuestionario."}), 409
        return jsonify({"id": response_id, "mensaje": "Respuesta guardada.", "codigo_aplicacion": clean_identification["codigo_aplicacion"].strip()}), 201

    @app.get("/api/respuestas")
    @admin_required
    def list_responses():
        filters, clauses, params = read_filters(request.args)
        try:
            limit = max(1, min(int(request.args.get("limit", 100)), 500))
            offset = max(0, int(request.args.get("offset", 0)))
        except ValueError:
            return jsonify({"error": "limit y offset deben ser enteros."}), 400
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with connect() as db:
            total = db.execute("SELECT COUNT(*) FROM respuestas" + where, params).fetchone()[0]
            rows = db.execute("SELECT * FROM respuestas" + where + " ORDER BY id DESC LIMIT ? OFFSET ?", params + [limit, offset]).fetchall()
        return jsonify({"total": total, "limit": limit, "offset": offset, "items": [serialize_row(row) for row in rows]})

    @app.route("/api/respuestas/<int:response_id>", methods=["GET", "DELETE"])
    @admin_required
    def response_by_id(response_id):
        with connect() as db:
            row = db.execute("SELECT * FROM respuestas WHERE id = ?", (response_id,)).fetchone()
            if row is None:
                return not_found("Respuesta")
            if request.method == "DELETE":
                db.execute("DELETE FROM respuestas WHERE id = ?", (response_id,))
                return jsonify({"mensaje": "Respuesta eliminada.", "id": response_id})
            return jsonify(serialize_row(row))

    @app.get("/api/estadisticas/<codigo>")
    @admin_required
    def statistics(codigo):
        code = codigo.upper()
        questionnaire = get_questionario(code)
        if not questionnaire:
            return not_found("Cuestionario")
        _, clauses, params = read_filters(request.args, default_code=code)
        where = " WHERE " + " AND ".join(clauses)
        with connect() as db:
            rows = db.execute("SELECT respuestas FROM respuestas" + where, params).fetchall()
        result = {}
        for dimension in questionnaire["dimensiones"]:
            for item in dimension["items"]:
                if item.get("tipo") != "escala":
                    continue
                values = []
                for row in rows:
                    value = json.loads(row["respuestas"]).get(item["id"])
                    if isinstance(value, dict):
                        value = value.get("valor")
                    if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 5:
                        values.append(value)
                distribution = {str(n): values.count(n) for n in range(1, 6)}
                result[item["id"]] = {"n": len(values), "media": round(sum(values) / len(values), 2) if values else None, "distribucion": distribution}
        return jsonify({"cuestionario": code, "total": len(rows), "items": result})

    @app.get("/api/exportar/<codigo>.csv")
    @admin_required
    def export_csv(codigo):
        code = codigo.upper()
        if not get_questionario(code):
            return not_found("Cuestionario")
        _, clauses, params = read_filters(request.args, default_code=code)
        where = " WHERE " + " AND ".join(clauses)
        with connect() as db:
            rows = db.execute("SELECT * FROM respuestas" + where + " ORDER BY id", params).fetchall()
        item_ids = [item["id"] for dim in get_questionario(code)["dimensiones"] for item in dim["items"]]
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(["id", "cuestionario", "codigo_aplicacion", "esfm_ua", "especialidad", "ambito", "sexo", "fecha"] + item_ids)
        for row in rows:
            record = serialize_row(row)
            ident, answers = record["identificacion"], record["respuestas"]
            values = [answers.get(item_id, "") for item_id in item_ids]
            values = [json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for v in values]
            writer.writerow([record["id"], code, ident.get("codigo_aplicacion", ""), ident.get("esfm_ua", ""), ident.get("especialidad", ""), ident.get("ambito", ""), ident.get("sexo", ""), ident.get("fecha", "")] + values)
        return Response(stream.getvalue().encode("utf-8-sig"), mimetype="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{code}.csv"'})

    return app


def init_db(path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS respuestas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cuestionario TEXT NOT NULL,
            codigo_aplicacion TEXT NOT NULL,
            identificacion TEXT NOT NULL,
            respuestas TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (cuestionario, codigo_aplicacion)
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_respuestas_cuestionario ON respuestas(cuestionario)")


def connect():
    db = sqlite3.connect(current_app.config["DB_PATH"])
    db.row_factory = sqlite3.Row
    return db


def admin_required(function):
    @wraps(function)
    def decorated(*args, **kwargs):
        if request.headers.get("X-API-Key") != current_app.config["ADMIN_API_KEY"]:
            return jsonify({"error": "X-API-Key inválida o faltante."}), 401
        return function(*args, **kwargs)
    return decorated


def not_found(resource):
    return jsonify({"error": f"{resource} no encontrado."}), 404


def validate_identification(code, identification):
    errors = []
    if not isinstance(identification, dict):
        return [{"campo": "identificacion", "motivo": "Debe ser un objeto JSON."}]
    for key in REQUIRED_IDENTIFICATION[code]:
        value = identification.get(key)
        if value is None or value == "" or (isinstance(value, str) and not value.strip()):
            errors.append({"campo": f"identificacion.{key}", "motivo": "Es obligatorio."})
    if code == "DIR" and "edad" in identification and not valid_nonnegative_number(identification["edad"]):
        errors.append({"campo": "identificacion.edad", "motivo": "Debe ser un número no negativo."})
    if code == "DOC" and "anios_servicio" in identification and not valid_nonnegative_number(identification["anios_servicio"]):
        errors.append({"campo": "identificacion.anios_servicio", "motivo": "Debe ser un número no negativo."})
    if identification.get("fecha"):
        try:
            date.fromisoformat(identification["fecha"])
        except (TypeError, ValueError):
            errors.append({"campo": "identificacion.fecha", "motivo": "Use el formato AAAA-MM-DD."})
    return errors


def valid_nonnegative_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def validate_answers(items, answers, partial):
    if not isinstance(answers, dict):
        return [{"campo": "respuestas", "motivo": "Debe ser un objeto JSON."}]
    errors = []
    for item_id, item in items.items():
        if item_id not in answers:
            if item.get("tipo") == "escala" and not partial:
                errors.append({"campo": item_id, "motivo": "Es obligatorio."})
            continue
        value = answers[item_id]
        if value is None:
            if item.get("tipo") == "escala" and not partial:
                errors.append({"campo": item_id, "motivo": "Es obligatorio."})
        elif item.get("tipo") == "escala":
            if isinstance(value, dict):
                value = value.get("valor")
            if not isinstance(value, int) or isinstance(value, bool) or value not in range(1, 6):
                errors.append({"campo": item_id, "motivo": "Debe ser un número entero entre 1 y 5 (o un objeto con valor)."})
        elif item.get("tipo") == "abierta" and not isinstance(value, str):
            errors.append({"campo": item_id, "motivo": "Debe ser texto."})
        elif item.get("tipo") == "multiple_choice":
            options = item.get("opciones", [])
            if not isinstance(value, dict) or not isinstance(value.get("opciones"), list):
                errors.append({"campo": item_id, "motivo": "Debe incluir opciones como una lista."})
            elif options and any(option not in options for option in value["opciones"]):
                errors.append({"campo": item_id, "motivo": "Contiene una opción no permitida."})
    for item_id in sorted(set(answers) - set(items)):
        errors.append({"campo": item_id, "motivo": "No existe en este cuestionario."})
    return errors


def normalize_answer(item, value):
    if item.get("tipo") == "escala" and isinstance(value, dict):
        result = dict(value)
        result["valor"] = value["valor"]
        return result
    return value


def read_filters(args, default_code=None):
    clauses, params = [], []
    code = args.get("cuestionario", default_code)
    if code:
        clauses.append("cuestionario = ?")
        params.append(code.upper())
    for field in ("esfm_ua", "ambito", "sexo", "especialidad"):
        value = args.get(field)
        if value:
            clauses.append("json_extract(identificacion, ?) = ?")
            params.extend([f"$.{field}", value])
    for field, operator in (("desde", ">="), ("hasta", "<=")):
        value = args.get(field)
        if value:
            clauses.append(f"created_at {operator} ?")
            params.append(value)
    return {}, clauses, params


def serialize_row(row):
    result = dict(row)
    result["identificacion"] = json.loads(result["identificacion"])
    result["respuestas"] = json.loads(result["respuestas"])
    return result


app = create_app()

if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5000")))
