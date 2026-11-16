from pydantic import BaseModel, Field
from typing import Literal

# Niveles fijos, de mayor a menor logro.
NIVELES = ["Excelente", "Logrado", "En proceso", "Inicio"]


class RubricaRequest(BaseModel):
    curso_id: str
    competencias: list[str] = []
    logros: list[str] = []
    capacidades: list[str] = []
    actividad: str
    tipo_entregable: Literal["informe", "proyecto", "exposicion", "codigo"]
    num_criterios: int = Field(ge=3, le=8)


def build_output_schema(n: int) -> dict:
    """JSON schema dinámico para structured output de Ollama."""
    def descriptor_obj():
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["nivel", "puntaje", "descripcion"],
            "properties": {
                "nivel": {"type": "string", "enum": NIVELES},
                "puntaje": {"type": "number", "minimum": 0},
                "descripcion": {"type": "string", "maxLength": 140},
            },
        }

    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["titulo", "puntaje_total", "niveles", "criterios"],
        "properties": {
            "titulo": {"type": "string", "maxLength": 120},
            "puntaje_total": {"type": "integer", "const": 20},
            "niveles": {"type": "array", "minItems": 4, "maxItems": 4,
                        "items": {"type": "string", "enum": NIVELES}},
            "criterios": {
                "type": "array", "minItems": n, "maxItems": n,
                "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["nombre", "peso", "descriptores"],
                    "properties": {
                        "nombre": {"type": "string", "maxLength": 60},
                        "peso": {"type": "number", "minimum": 1},
                        "descriptores": {"type": "array", "minItems": 4, "maxItems": 4,
                                         "items": descriptor_obj()},
                    },
                },
            },
        },
    }


def _normalize_pesos(pesos, total=20):
    """Escala los pesos sugeridos por el modelo a enteros que sumen `total`."""
    valores = [max(float(p), 0.0001) for p in pesos]
    s = sum(valores)
    scaled = [v / s * total for v in valores]
    enteros = [int(x) for x in scaled]
    resto = total - sum(enteros)
    orden = sorted(range(len(scaled)), key=lambda i: scaled[i] - enteros[i], reverse=True)
    for i in orden[:resto]:
        enteros[i] += 1
    # garantiza al menos 1 por criterio
    for i in range(len(enteros)):
        if enteros[i] == 0:
            j = max(range(len(enteros)), key=lambda k: enteros[k])
            if enteros[j] > 1:
                enteros[i] = 1
                enteros[j] -= 1
    return enteros


def _puntajes_por_nivel(peso):
    """Deriva puntajes descendentes por nivel (Excelente=peso ... Inicio=0)."""
    n = len(NIVELES)
    return [round(peso * (n - 1 - i) / (n - 1), 1) for i in range(n)]


def validate_and_normalize(data: dict, num_criterios: int) -> dict:
    """Valida invariantes semánticas y normaliza pesos/puntajes. Lanza ValueError si no cumple."""
    crits = data.get("criterios") or []
    if len(crits) != num_criterios:
        raise ValueError(f"criterios={len(crits)} != {num_criterios}")

    pesos = _normalize_pesos([c.get("peso", 1) for c in crits])
    salida = []
    for c, peso in zip(crits, pesos):
        by_nivel = {}
        for d in (c.get("descriptores") or []):
            if d.get("nivel") in NIVELES:
                by_nivel[d["nivel"]] = d
        if len(by_nivel) != len(NIVELES):
            raise ValueError("descriptores incompletos: falta algún nivel")

        puntajes = _puntajes_por_nivel(peso)
        descriptores = []
        for i, nivel in enumerate(NIVELES):
            descriptores.append({
                "nivel": nivel,
                "puntaje": puntajes[i],
                "descripcion": (by_nivel[nivel].get("descripcion") or "").strip(),
            })
        salida.append({
            "nombre": (c.get("nombre") or "").strip(),
            "peso": peso,
            "descriptores": descriptores,
        })

    return {
        "titulo": (data.get("titulo") or "Rúbrica").strip(),
        "puntaje_total": 20,
        "niveles": NIVELES,
        "criterios": salida,
    }
