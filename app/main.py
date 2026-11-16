import hashlib
import io
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from openpyxl import Workbook

from . import db, llm_client, prompt, schemas
from .schemas import RubricaRequest

BASE = Path(__file__).resolve().parent.parent
FRONTEND = BASE / "frontend"

app = FastAPI(title="Rúbricas FISI")
db.init_db()

# Registros agregados por UI: solo viven en memoria (no se persisten).
EXTRA = {"competencias": [], "logros": [], "capacidades": []}


def _arbol(curso_id: str):
    rows = db.get_rows(curso_id)
    if rows is None:
        raise HTTPException(404, "Curso no encontrado")
    for e in EXTRA["competencias"]:
        if e["curso_id"] == curso_id:
            rows["competencias"].append(e["data"])
    for e in EXTRA["logros"]:
        if e["curso_id"] == curso_id:
            rows["logros"].append(e["data"])
    for e in EXTRA["capacidades"]:
        if e["curso_id"] == curso_id:
            rows["capacidades"].append(e["data"])
            if e["data"].get("codigo_logro"):
                rows["logro_capacidades"].append({
                    "codigo_logro": e["data"]["codigo_logro"],
                    "codigo_capacidad": e["data"]["codigo"],
                })
    return db.assemble(rows)


def _contexto(arbol, req):
    lineas = []
    for c in arbol["competencias"]:
        if req.competencias and c["codigo"] not in req.competencias:
            continue
        lineas.append(f"Competencia {c['codigo']}: {c['descripcion']} (tipo {c['tipo']}, nivel {c['nivel']})")
        for lg in c["logros"]:
            if req.logros and lg["codigo"] not in req.logros:
                continue
            lineas.append(f"  Logro {lg['codigo']}: {lg['descripcion']}")
            for cap in lg["capacidades"]:
                if req.capacidades and cap["codigo"] not in req.capacidades:
                    continue
                lineas.append(f"    Capacidad {cap['codigo']} ({cap['unidad_aprendizaje']}): {cap['descripcion']}")
    return "\n".join(lineas) if lineas else "(sin filtro: usar todos los insumos del curso)"


# ---------- API ----------

@app.get("/api/v1/health")
def health():
    try:
        ok = httpx.get(f"{llm_client.OLLAMA_URL}/api/tags", timeout=5).status_code == 200
    except Exception:
        ok = False
    return {"status": "ok" if ok else "degraded", "modelo": llm_client.MODEL, "ollama": ok}


@app.get("/api/v1/kb")
def kb_info():
    if not prompt.KB_PATH.exists():
        return {"version": None, "hash": None, "tokens": 0}
    txt = prompt.KB_PATH.read_text(encoding="utf-8")
    return {"version": "0.1", "hash": hashlib.sha256(txt.encode()).hexdigest()[:12],
            "tokens": len(txt.split())}


@app.get("/api/v1/cursos")
def cursos():
    return db.list_cursos()


@app.get("/api/v1/cursos/{curso_id}/arbol")
def arbol(curso_id: str):
    return _arbol(curso_id)


@app.post("/api/v1/cursos/{curso_id}/{entidad}")
def agregar(curso_id: str, entidad: str, data: dict):
    if entidad not in EXTRA:
        raise HTTPException(400, "entidad inválida")
    if db.get_rows(curso_id) is None:
        raise HTTPException(404, "Curso no encontrado")
    EXTRA[entidad].append({"curso_id": curso_id, "data": data})
    return {"ok": True, "nota": "registro solo en sesión"}


@app.post("/api/v1/rubricas")
def rubricas(req: RubricaRequest):
    arbol = _arbol(req.curso_id)
    messages = prompt.build_messages(req, _contexto(arbol, req))
    schema = schemas.build_output_schema(req.num_criterios)

    ultimo_error = None
    for _ in range(3):  # 1 intento + 2 reintentos
        try:
            data, _meta = llm_client.generate(messages, schema)
            return schemas.validate_and_normalize(data, req.num_criterios)
        except llm_client.LLMUnavailable as e:
            raise HTTPException(503, str(e))
        except llm_client.LLMTimeout as e:
            raise HTTPException(504, str(e))
        except ValueError as e:
            ultimo_error = str(e)
            continue
    raise HTTPException(422, f"Salida inválida tras reintentos: {ultimo_error}")


def _to_markdown(r: dict) -> str:
    niveles = r["niveles"]
    lineas = [f"# {r['titulo']}", "", f"Puntaje total: {r['puntaje_total']}", ""]
    lineas.append("| Criterio | Peso | " + " | ".join(niveles) + " |")
    lineas.append("|" + "---|" * (2 + len(niveles)))
    for c in r["criterios"]:
        por_nivel = {d["nivel"]: d for d in c["descriptores"]}
        celdas = [f"{por_nivel[n]['puntaje']} – {por_nivel[n]['descripcion']}" if n in por_nivel else ""
                  for n in niveles]
        lineas.append(f"| {c['nombre']} | {c['peso']} | " + " | ".join(celdas) + " |")
    return "\n".join(lineas)


@app.post("/api/v1/export/md")
def export_md(rubrica: dict):
    return Response(content=_to_markdown(rubrica), media_type="text/markdown",
                    headers={"Content-Disposition": "attachment; filename=rubrica.md"})


@app.post("/api/v1/export/xlsx")
def export_xlsx(rubrica: dict):
    wb = Workbook()
    ws = wb.active
    ws.title = "Rubrica"
    niveles = rubrica["niveles"]
    ws.append(["Criterio", "Peso"] + niveles)
    for c in rubrica["criterios"]:
        por_nivel = {d["nivel"]: d for d in c["descriptores"]}
        fila = [c["nombre"], c["peso"]]
        for n in niveles:
            d = por_nivel.get(n, {})
            fila.append(f"{d.get('puntaje', '')} - {d.get('descripcion', '')}")
        ws.append(fila)
    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)
    return StreamingResponse(
        bio,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=rubrica.xlsx"},
    )


# ---------- Frontend estático ----------

@app.get("/")
def index():
    return FileResponse(FRONTEND / "registro.html")


@app.get("/generar.html")
def generar_page():
    return FileResponse(FRONTEND / "generar.html")


app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")
