"""Cuestionarios provisionales: sustituir textos/ítems con el documento fuente.

La descripción recibida no incluye el instrumento completo. Las preguntas aquí
son ejemplos operativos, no una transcripción ni una validación del documento.
"""

ESCALAS = {
    "frecuencia": {"1": "Nunca", "2": "Pocas veces", "3": "A veces", "4": "Frecuentemente", "5": "Siempre"},
    "acuerdo": {"1": "Totalmente en desacuerdo", "2": "En desacuerdo", "3": "Ni de acuerdo ni en desacuerdo", "4": "De acuerdo", "5": "Totalmente de acuerdo"},
}


def _item(item_id, tipo="escala", escala="frecuencia", **extra):
    result = {"id": item_id, "tipo": tipo, "nombre": f"Ítem {item_id} (texto pendiente del documento fuente)"}
    if tipo == "escala":
        result.update(escala=escala, escala_supuesta=True)
    result.update(extra)
    return result


def _questionnaire(code, name, ids, extras=None):
    items = [_item(item_id) for item_id in ids]
    items.extend(extras or [])
    return {
        "codigo": code,
        "nombre": name,
        "descripcion": f"Cuestionario {name}; contenido provisional pendiente de cotejo con el documento fuente.",
        "provisional": True,
        "escalas": ESCALAS,
        "dimensiones": [{"codigo": "D1", "nombre": "Dimensión (nombre pendiente del documento fuente)", "items": items}],
    }


QUESTIONARIOS = {
    "DIR": _questionnaire("DIR", "Directivos", ["1.1", "1.2", "2.2", "3.2", "5.4", "5.4b"], [
        _item("6.7", "multiple_choice", opciones=[], escala_supuesta=True),
        _item("PA1", "abierta", escala_supuesta=True),
    ]),
    "DOC": _questionnaire("DOC", "Docentes formadores", ["1.1", "1.2", "2.1", "4.1", "5.1"], [_item("PA1", "abierta")]),
    "EST": _questionnaire("EST", "Estudiantes", ["1.1", "1.2", "4.1", "5.4", "5.5", "6.1", "8.1a"], [_item("PA1", "abierta")]),
    "EGR": _questionnaire("EGR", "Egresados/titulados", ["1.1", "1.2", "4.1", "5.1", "8.1a"], [_item("PA1", "abierta")]),
}


def get_questionario(codigo):
    return QUESTIONARIOS.get(str(codigo).upper())
