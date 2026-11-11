"""Definición de los cuatro cuestionarios curriculares ESFM/UA.

Se aplican los ajustes señalados en el documento original:
- escalas no indicadas se heredan con etiqueta estándar y se marcan como `escala_supuesta`;
- DIR 5.4 aparece dos veces: la segunda queda como 5.4b;
- DIR 3.2a se considera seguimiento de 3.2;
- los encabezados ausentes se completan con los nombres usuales;
- DIR no tiene 2.1 (empieza en 2.2);
- 8.1ª quedó corregido a 8.1a;
- EST y DIR usan escala de acuerdo en 5.4/5.5.
"""

ESCALAS = {
    "frecuencia": {"1": "Nunca", "2": "Pocas veces", "3": "A veces", "4": "Frecuentemente", "5": "Siempre"},
    "acuerdo": {"1": "Totalmente en desacuerdo", "2": "En desacuerdo", "3": "Ni de acuerdo ni en desacuerdo", "4": "De acuerdo", "5": "Totalmente de acuerdo"},
    "valoracion": {"1": "Muy deficiente", "2": "Deficiente", "3": "Regular", "4": "Buena", "5": "Excelente"},
    "satisfaccion": {"1": "Muy insatisfecho", "2": "Insatisfecho", "3": "Indiferente", "4": "Satisfecho", "5": "Muy satisfecho"},
}


def item(tipo, item_id, nombre, escala=None, opciones=None, **extra):
    data = {"id": item_id, "tipo": tipo, "nombre": nombre}
    if tipo == "escala":
        data["escala"] = escala or "acuerdo"
        data["escala_supuesta"] = extra.pop("escala_supuesta", False)
    if tipo == "multiple_choice":
        data["opciones"] = opciones or []
    data.update(extra)
    return data


def dimension(codigo, nombre, items):
    return {"codigo": codigo, "nombre": nombre, "items": items}


QUESTIONARIOS = {
    "DIR": {
        "codigo": "DIR",
        "nombre": "Directivos",
        "descripcion": "Cuestionario para directivos",
        "escalas": ESCALAS,
        "dimensiones": [
            dimension("D1", "Gestión institucional", [
                item("escala", "1.1", "Manejo de indicadores y resultados", "acuerdo"),
                item("escala", "1.2", "Clima institucional y mejora continua", "acuerdo"),
                item("escala", "1.3", "Alineación del trabajo con la misión institucional", "acuerdo"),
            ]),
            dimension("D2", "Participación y liderazgo", [
                item("escala", "2.2", "Promoción de la participación de la comunidad", "frecuencia"),
                item("escala", "2.3", "Apoyo al liderazgo docente y estudiantil", "frecuencia", escala_supuesta=True),
                item("escala", "2.4", "Seguimiento a metas institucionales", "frecuencia", escala_supuesta=True),
            ]),
            dimension("D3", "Comunicación y acompañamiento", [
                item("escala", "3.1", "Comunicación con actores de la institución", "frecuencia", escala_supuesta=True),
                item("escala", "3.2", "Acompañamiento a procesos de mejora", "frecuencia", escala_supuesta=True),
                item("abierta", "3.2a", "Por qué:", escala_supuesta=True),
                item("escala", "3.3", "Uso de información para toma de decisiones", "frecuencia", escala_supuesta=True),
            ]),
            dimension("D4", "Desarrollo profesional", [
                item("escala", "4.1", "Disponibilidad de espacios de formación", "frecuencia", escala_supuesta=True),
                item("escala", "4.2", "Apoyo para la actualización del personal", "frecuencia", escala_supuesta=True),
                item("escala", "4.3", "Viabilidad de los procesos formativos", "frecuencia", escala_supuesta=True),
            ]),
            dimension("D5", "Recursos y organización", [
                item("escala", "5.1", "Disponibilidad de recursos materiales", "acuerdo"),
                item("escala", "5.2", "Organización del tiempo y actividades", "acuerdo", escala_supuesta=True),
                item("escala", "5.3", "Uso eficiente de la infraestructura", "acuerdo", escala_supuesta=True),
                item("escala", "5.4", "Capacidad de respuesta ante incidencias", "acuerdo"),
                item("escala", "5.4b", "Seguimiento a la mejora de procesos", "acuerdo", escala_supuesta=True),
                item("escala", "5.5", "Pertinencia de la organización institucional", "acuerdo"),
            ]),
            dimension("D6", "Satisfacción y pertinencia", [
                item("escala", "6.1", "Satisfacción general con el proceso", "satisfaccion", escala_supuesta=True),
                item("escala", "6.2", "Pertinencia del modelo institucional", "valoracion", escala_supuesta=True),
                item("multiple_choice", "6.7", "Selección múltiple de prioridades", opciones=["Infraestructura", "Docentes", "Programas", "Comunidad", "Otros"]),
            ]),
            dimension("D8", "Observaciones finales", [
                item("abierta", "8.1a", "Comentarios finales"),
            ]),
        ],
    },
    "DOC": {
        "codigo": "DOC",
        "nombre": "Docentes formadores",
        "descripcion": "Cuestionario para docentes formadores",
        "escalas": ESCALAS,
        "dimensiones": [
            dimension("D1", "Diseño curricular", [
                item("escala", "1.1", "Claridad del plan curricular", "acuerdo"),
                item("escala", "1.2", "Pertinencia de los contenidos", "acuerdo"),
                item("escala", "1.3", "Coherencia entre objetivos y prácticas", "acuerdo"),
            ]),
            dimension("D2", "Metodología y evaluación", [
                item("escala", "2.1", "Uso de metodologías activas", "frecuencia", escala_supuesta=True),
                item("escala", "2.2", "Diversidad de estrategias de evaluación", "frecuencia", escala_supuesta=True),
                item("escala", "2.3", "Retroalimentación a estudiantes", "frecuencia", escala_supuesta=True),
            ]),
            dimension("D4", "Formación continua", [
                item("escala", "4.1", "Acceso a capacitación", "frecuencia", escala_supuesta=True),
                item("escala", "4.2", "Apoyo para actualización disciplinaria", "frecuencia", escala_supuesta=True),
                item("escala", "4.3", "Uso de la formación en la práctica", "frecuencia", escala_supuesta=True),
            ]),
            dimension("D5", "Gestión institucional", [
                item("escala", "5.1", "Clima de trabajo", "frecuencia", escala_supuesta=True),
                item("escala", "5.2", "Apoyo administrativo", "frecuencia", escala_supuesta=True),
                item("escala", "5.3", "Relación con dirección", "frecuencia", escala_supuesta=True),
            ]),
            dimension("D8", "Comentarios finales", [
                item("abierta", "8.1a", "Comentarios"),
            ]),
        ],
    },
    "EST": {
        "codigo": "EST",
        "nombre": "Estudiantes",
        "descripcion": "Cuestionario para estudiantes",
        "escalas": ESCALAS,
        "dimensiones": [
            dimension("D1", "Experiencia de aprendizaje", [
                item("escala", "1.1", "Transmisión de conocimientos", "acuerdo"),
                item("escala", "1.2", "Uso de ejemplos relevantes", "acuerdo"),
                item("escala", "1.3", "Actividades prácticas", "acuerdo"),
            ]),
            dimension("D4", "Acompañamiento académico", [
                item("escala", "4.1", "Apoyo del docente", "frecuencia", escala_supuesta=True),
                item("escala", "4.2", "Atención oportuna", "frecuencia", escala_supuesta=True),
                item("escala", "4.3", "Retroalimentación útil", "frecuencia", escala_supuesta=True),
            ]),
            dimension("D5", "Satisfacción", [
                item("escala", "5.1", "Satisfacción general con el programa", "satisfaccion", escala_supuesta=True),
                item("escala", "5.2", "Calidad del servicio académico", "valoracion", escala_supuesta=True),
                item("escala", "5.3", "Recomendación del programa", "acuerdo", escala_supuesta=True),
            ]),
            dimension("D6", "Infraestructura y apoyo", [
                item("escala", "6.1", "Calidad de infraestructura", "acuerdo", escala_supuesta=True),
                item("escala", "6.2", "Disponibilidad de recursos", "acuerdo", escala_supuesta=True),
            ]),
            dimension("D8", "Comentarios finales", [
                item("abierta", "8.1a", "Observaciones"),
            ]),
        ],
    },
    "EGR": {
        "codigo": "EGR",
        "nombre": "Egresados y titulados",
        "descripcion": "Cuestionario para egresados y titulados",
        "escalas": ESCALAS,
        "dimensiones": [
            dimension("D1", "Formación académica", [
                item("escala", "1.1", "Pertinencia de la formación académica", "acuerdo"),
                item("escala", "1.2", "Calidad del contenido curricular", "acuerdo"),
                item("escala", "1.3", "Preparación para el ejercicio profesional", "acuerdo"),
            ]),
            dimension("D4", "Inserción laboral", [
                item("escala", "4.1", "Oportunidad de empleo", "frecuencia", escala_supuesta=True),
                item("escala", "4.2", "Alineación de la formación con el trabajo", "frecuencia", escala_supuesta=True),
                item("escala", "4.3", "Relevancia del programa en el desempeño profesional", "frecuencia", escala_supuesta=True),
            ]),
            dimension("D5", "Satisfacción con la institución", [
                item("escala", "5.1", "Satisfacción general con la institución", "satisfaccion", escala_supuesta=True),
                item("escala", "5.2", "Calidad del servicio institucional", "valoracion", escala_supuesta=True),
                item("escala", "5.3", "Recomendación de la institución", "acuerdo", escala_supuesta=True),
            ]),
            dimension("D8", "Comentarios finales", [
                item("abierta", "8.1a", "Observaciones"),
            ]),
        ],
    },
}


def get_questionario(codigo):
    return QUESTIONARIOS.get(str(codigo).upper())

