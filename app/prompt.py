from pathlib import Path
from .schemas import NIVELES

KB_PATH = Path(__file__).resolve().parent.parent / "kb" / "rubricas.md"


def load_kb() -> str:
    return KB_PATH.read_text(encoding="utf-8") if KB_PATH.exists() else ""


def build_messages(req, contexto: str):
    system = (
        "Eres un asistente que genera rúbricas de evaluación analíticas en español para la FISI. "
        "Devuelve EXCLUSIVAMENTE un JSON válido conforme al schema. "
        f"Usa 4 niveles fijos, en este orden: {', '.join(NIVELES)}. "
        "Cada criterio tiene exactamente un descriptor por nivel. "
        "Las descripciones deben ser observables y medibles, de 20 palabras como máximo.\n\n"
        "BASE DE CONOCIMIENTOS:\n" + load_kb()
    )
    user = (
        f"Curso: {req.curso_id}\n"
        f"Actividad: {req.actividad}\n"
        f"Tipo de entregable: {req.tipo_entregable}\n"
        f"Número de criterios: {req.num_criterios}\n\n"
        f"Insumos seleccionados:\n{contexto}\n\n"
        "Genera la rúbrica: 'peso' entero por criterio (será normalizado a 20), "
        "un descriptor por nivel en el orden dado."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
