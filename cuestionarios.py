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
        JSON_SORT_KEYS=False,
    )
    if test_config:
        app.config.update(test_config)
    if not app.config["ADMIN_API_KEY"]:
        app.config["ADMIN_API_KEY"] = secrets.token_urlsafe(32)
        app.logger.warning("ADMIN_API_KEY temporal generado: %s", app.config["ADMIN_API_KEY"])

    init_db(app.config["DB_PATH"])

    @app.route("/api/<path:subpath>", methods=["OPTIONS"])
    def handle_options(subpath):
        response = Response(status=204)
        response.headers["Access-Control-Allow-Origin"] = "*" if app.config["CORS_ORIGINS"] == "*" else request.headers.get("Origin", "*")
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Key"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
        return response

    @app.after_request
    def add_cors_headers(response):
        origins = app.config["CORS_ORIGINS"]
        origin = request.headers.get("Origin")
        if origins == "*":
            response.headers["Access-Control-Allow-Origin"] = "*"
        elif origin and origin in [o.strip() for o in origins.split(",") if o.strip()]:
            response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Key"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
        return response

    @app.get("/api/cuestionarios")
    def list_questionnaires():
        payload = []
        for codigo in ["DIR", "DOC", "EST", "EGR"]:
            q = get_questionario(codigo)
            payload.append({
                "codigo": q["codigo"],
                "nombre": q["nombre"],
                "descripcion": q["descripcion"],
                "dimensiones": [d["codigo"] for d in q["dimensiones"]],
            })
        return jsonify({"cuestionarios": payload})

    @app.get("/api/cuestionarios/<codigo>")
    def questionnaire_detail(codigo):
        q = get_questionario(codigo)
        if not q:
            return jsonify({"error": "Cuestionario no encontrado."}), 404
        return jsonify(q)

    @app.get("/api/cuestionarios/<codigo>/plantilla")
    def questionnaire_template(codigo):
        q = get_questionario(codigo)
        if not q:
            return jsonify({"error": "Cuestionario no encontrado."}), 404

        identification = {key: "" for key in COMMON_IDENTIFICATION}
        if codigo.upper() == "DOC":
            identification["anios_servicio"] = 0
        if codigo.upper() == "DIR":
            identification["edad"] = 0

        respuestas = {}
        for dim in q["dimensiones"]:
            for item in dim["items"]:
                respuestas[item["id"]] = None

        return jsonify({
            "cuestionario": codigo.upper(),
            "identificacion": identification,
            "respuestas": respuestas,
        })

    @app.post("/api/respuestas/<codigo>")
    def submit_response(codigo):
        code = codigo.upper()
        q = get_questionario(code)
        if not q:
            return jsonify({"error": "Cuestionario no encontrado."}), 404

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "El cuerpo debe ser un JSON válido."}), 400

        identification = payload.get("identificacion", {})
        answers = payload.get("respuestas", {})
        partial = request.args.get("parcial", "false").lower() in {"1", "true", "yes"}

        errors = validate_identification(code, identification)
        errors.extend(validate_answers(q, answers, partial))
        if errors:
            return jsonify({"detalles": errors}), 422

        codigo_aplicacion = str(identification["codigo_aplicacion"]).strip()
        clean_identificacion = dict(identification)
        clean_respuestas = normalize_answer_map(q, answers)

        conn = get_db_connection(app.config["DB_PATH"])
        try:
            try:
                cur = conn.execute(
                    "INSERT INTO respuestas (cuestionario, codigo_aplicacion, identificacion, respuestas) VALUES (?, ?, ?, ?)",
                    (code, codigo_aplicacion, json.dumps(clean_identificacion, ensure_ascii=False), json.dumps(clean_respuestas, ensure_ascii=False)),
                )
                conn.commit()
                response_id = cur.lastrowid
            except sqlite3.IntegrityError:
                conn.rollback()
                return jsonify({"error": "El codigo_aplicacion ya existe para este cuestionario.", "codigo_aplicacion": codigo_aplicacion}), 409
        finally:
            conn.close()

        return jsonify({"id": response_id, "mensaje": "Respuesta guardada.", "codigo_aplicacion": codigo_aplicacion}), 201

    @app.get("/api/respuestas")
    @admin_required
    def list_responses():
        filters = build_filters_from_args(request.args)
        try:
            limit = min(max(int(request.args.get("limit", 100)), 1), 500)
            offset = max(int(request.args.get("offset", 0)), 0)
        except ValueError:
            return jsonify({"error": "Los parámetros limit y offset deben ser enteros."}), 400

        query, params = select_respuestas_query(filters)
        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params += [limit, offset]

        conn = get_db_connection(app.config["DB_PATH"])
        try:
            rows = conn.execute(query, params).fetchall()
            total = conn.execute("SELECT COUNT(*) FROM respuestas" + build_where_clause(filters), build_where_params(filters)).fetchone()[0]
        finally:
            conn.close()

        return jsonify({
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [serialize_response_row(r) for r in rows],
        })

    @app.route("/api/respuestas/<int:id>", methods=["GET", "DELETE"])
    @admin_required
    def response_detail(id):
        conn = get_db_connection(app.config["DB_PATH"])
        try:
            row = conn.execute("SELECT * FROM respuestas WHERE id = ?", (id,)).fetchone()
            if row is None:
                return jsonify({"error": "Respuesta no encontrada."}), 404
            if request.method == "DELETE":
                conn.execute("DELETE FROM respuestas WHERE id = ?", (id,))
                conn.commit()
                return jsonify({"mensaje": "Respuesta eliminada.", "id": id})
            return jsonify(serialize_response_row(row))
        finally:
            conn.close()

    @app.get("/api/estadisticas/<codigo>")
    @admin_required
    def statistics(codigo):
        code = codigo.upper()
        q = get_questionario(code)
        if not q:
            return jsonify({"error": "Cuestionario no encontrado."}), 404

        filters = build_filters_from_args(request.args)
        query, params = select_respuestas_query(filters, code)
        conn = get_db_connection(app.config["DB_PATH"])
        try:
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()

        items = {}
        for dim in q["dimensiones"]:
            for item in dim["items"]:
                if item["tipo"] != "escala":
                    continue
                values = []
                for row in rows:
                    payload = json.loads(row["respuestas"])
                    value = payload.get(item["id"])
                    if isinstance(value, dict):
                        value = value.get("valor")
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        value_num = int(value)
                        if 1 <= value_num <= 5:
                            values.append(value_num)

                dist = {str(v): 0 for v in range(1, 6)}
                for v in values:
                    dist[str(v)] += 1
                items[item["id"]] = {
                    "n": len(values),
                    "media": round(sum(values) / len(values), 2) if values else None,
                    "distribucion": dist,
                }

        return jsonify({"cuestionario": code, "total": len(rows), "items": items})

    @app.get("/api/exportar/<codigo>.csv")
    @admin_required
    def export_csv(codigo):
        code = codigo.upper()
        q = get_questionario(code)
        if not q:
            return jsonify({"error": "Cuestionario no encontrado."}), 404

        filters = build_filters_from_args(request.args)
        query, params = select_respuestas_query(filters, code)
        query += " ORDER BY id ASC"
        conn = get_db_connection(app.config["DB_PATH"])
        try:
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()

        item_ids = [item["id"] for dim in q["dimensiones"] for item in dim["items"]]
        output = io.StringIO(newline="")
        writer = csv.writer(output, dialect="excel")
        writer.writerow(["id", "cuestionario", "codigo_aplicacion", "esfm_ua", "especialidad", "ambito", "sexo", "fecha"] + item_ids)

        for row in rows:
            record = serialize_response_row(row)
            ident = record["identificacion"]
            answers = record["respuestas"]
            vals = []
            for item_id in item_ids:
                val = answers.get(item_id)
                if isinstance(val, (dict, list)):
                    vals.append(json.dumps(val, ensure_ascii=False))
                elif val is None:
                    vals.append("")
                else:
                    vals.append(val)
            writer.writerow([
                record["id"],
                record["cuestionario"],
                ident.get("codigo_aplicacion", ""),
                ident.get("esfm_ua", ""),
                ident.get("especialidad", ""),
                ident.get("ambito", ""),
                ident.get("sexo", ""),
                ident.get("fecha", ""),
                *vals,
            ])

        csv_bytes = output.getvalue().encode("utf-8-sig")
        return Response(csv_bytes, mimetype="text/csv; charset=utf-8", headers={
            "Content-Disposition": f'attachment; filename="{code}.csv"'
        })

    return app


def init_db(path):
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS respuestas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cuestionario TEXT NOT NULL,
            codigo_aplicacion TEXT NOT NULL,
            identificacion TEXT NOT NULL,
            respuestas TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (cuestionario, codigo_aplicacion)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_respuestas_cuestionario ON respuestas(cuestionario)")
    conn.commit()
    conn.close()


def get_db_connection(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if request.headers.get("X-API-Key") != current_app.config["ADMIN_API_KEY"]:
            return jsonify({"error": "X-API-Key inválida o faltante."}), 401
        return fn(*args, **kwargs)
    return wrapper


def build_filters_from_args(args):
    filters = {}
    for key in ["cuestionario", "esfm_ua", "ambito", "sexo", "especialidad", "desde", "hasta"]:
        value = args.get(key)
        if value not in (None, ""):
            filters[key] = value
    return filters


def build_where_clause(filters):
    clauses = []
    params = []
    if "cuestionario" in filters:
        clauses.append("cuestionario = ?")
        params.append(filters["cuestionario"].upper())
    for key in ["esfm_ua", "ambito", "sexo", "especialidad"]:
        if key in filters:
            clauses.append("json_extract(identificacion, ?) = ?")
            params.extend([f"$.{key}", filters[key]])
    if "desde" in filters:
        clauses.append("created_at >= ?")
        params.append(filters["desde"])
    if "hasta" in filters:
        clauses.append("created_at <= ?")
        params.append(filters["hasta"])
    return (" WHERE " + " AND ".join(clauses)) if clauses else ""


def build_where_params(filters):
    params = []
    if "cuestionario" in filters:
        params.append(filters["cuestionario"].upper())
    for key in ["esfm_ua", "ambito", "sexo", "especialidad"]:
        if key in filters:
            params.extend([f"$.{key}", filters[key]])
    if "desde" in filters:
        params.append(filters["desde"])
    if "hasta" in filters:
        params.append(filters["hasta"])
    return params


def select_respuestas_query(filters, code=None):
    where_clause = build_where_clause(filters)
    params = build_where_params(filters)
    if code:
        if "cuestionario" not in filters:
            where_clause = " WHERE cuestionario = ?" if not where_clause else where_clause + " AND cuestionario = ?"
            params = params + [code.upper()]
    return "SELECT * FROM respuestas" + where_clause, params


def serialize_response_row(row):
    result = dict(row)
    result["identificacion"] = json.loads(result["identificacion"])
    result["respuestas"] = json.loads(result["respuestas"])
    return result


def validate_identification(codigo, identificacion):
    errors = []
    if not isinstance(identificacion, dict):
        return [{"campo": "identificacion", "motivo": "Debe ser un objeto JSON."}]

    for field in REQUIRED_IDENTIFICATION.get(codigo.upper(), COMMON_IDENTIFICATION):
        value = identificacion.get(field)
        if value is None or value == "" or (isinstance(value, str) and not value.strip()):
            errors.append({"campo": f"identificacion.{field}", "motivo": "Es obligatorio."})

    if codigo.upper() == "DOC" and "anios_servicio" in identificacion and not valid_number(identificacion["anios_servicio"]):
        errors.append({"campo": "identificacion.anios_servicio", "motivo": "Debe ser un número."})
    if codigo.upper() == "DIR" and "edad" in identificacion and not valid_number(identificacion["edad"]):
        errors.append({"campo": "identificacion.edad", "motivo": "Debe ser un número."})

    if "fecha" in identificacion and identificacion["fecha"] not in (None, ""):
        try:
            date.fromisoformat(str(identificacion["fecha"]))
        except ValueError:
            errors.append({"campo": "identificacion.fecha", "motivo": "Debe usar el formato AAAA-MM-DD."})

    return errors


def valid_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_answers(q, answers, partial):
    if not isinstance(answers, dict):
        return [{"campo": "respuestas", "motivo": "Debe ser un objeto JSON."}]

    item_map = {}
    for dim in q["dimensiones"]:
        for item in dim["items"]:
            item_map[item["id"]] = item

    errors = []
    for item_id, item in item_map.items():
        if item_id not in answers:
            if item.get("tipo") == "escala" and not partial:
                errors.append({"campo": item_id, "motivo": "Es obligatorio."})
            continue

        value = answers[item_id]
        if item.get("tipo") == "escala":
            if value is None:
                if not partial:
                    errors.append({"campo": item_id, "motivo": "Es obligatorio."})
                continue
            if isinstance(value, dict):
                if "valor" not in value:
                    errors.append({"campo": item_id, "motivo": "Debe incluir 'valor' entre 1 y 5."})
                    continue
                value = value["valor"]
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not 1 <= int(value) <= 5:
                errors.append({"campo": item_id, "motivo": "Debe ser un número entero entre 1 y 5."})
        elif item.get("tipo") == "abierta":
            if value is not None and not isinstance(value, str):
                errors.append({"campo": item_id, "motivo": "Debe ser texto."})
        elif item.get("tipo") == "multiple_choice":
            if not isinstance(value, dict):
                errors.append({"campo": item_id, "motivo": "Debe tener el formato {'opciones': [...], 'otros': '', 'justificacion': ''}."})
                continue
            if "opciones" not in value:
                errors.append({"campo": item_id, "motivo": "Debe incluir 'opciones'."})
                continue
            if not isinstance(value["opciones"], list):
                errors.append({"campo": item_id, "motivo": "'opciones' debe ser una lista."})

    unknown = sorted(set(answers) - set(item_map))
    for item_id in unknown:
        errors.append({"campo": item_id, "motivo": "No existe en este cuestionario."})
    return errors


def normalize_answer_map(q, answers):
    item_map = {}
    for dim in q["dimensiones"]:
        for item in dim["items"]:
            item_map[item["id"]] = item

    normalized = {}
    for item_id, value in answers.items():
        item = item_map.get(item_id)
        if item is None:
            normalized[item_id] = value
            continue
        if item.get("tipo") == "escala" and isinstance(value, dict):
            normalized[item_id] = {"valor": int(value.get("valor", 0)), "justificacion": value.get("justificacion", "")}
        else:
            normalized[item_id] = value
    return normalized


app = create_app()

if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5000")))

