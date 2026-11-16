import sqlite3
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
EXAMPLES = BASE / "data" / "examples"
DB_PATH = BASE / "data" / "seed.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS curso (id TEXT PRIMARY KEY, nombre TEXT, carrera TEXT);
CREATE TABLE IF NOT EXISTS competencia (curso_id TEXT, codigo TEXT, descripcion TEXT, tipo TEXT, nivel TEXT, PRIMARY KEY (curso_id, codigo));
CREATE TABLE IF NOT EXISTS logro (curso_id TEXT, codigo TEXT, descripcion TEXT, codigo_competencia TEXT, PRIMARY KEY (curso_id, codigo));
CREATE TABLE IF NOT EXISTS capacidad (curso_id TEXT, codigo TEXT, descripcion TEXT, unidad_aprendizaje TEXT, PRIMARY KEY (curso_id, codigo));
CREATE TABLE IF NOT EXISTS logro_capacidad (curso_id TEXT, codigo_logro TEXT, codigo_capacidad TEXT, PRIMARY KEY (curso_id, codigo_logro, codigo_capacidad));
"""


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Crea tablas y carga la semilla desde data/examples/*.json si está vacía."""
    conn = connect()
    conn.executescript(SCHEMA)
    if conn.execute("SELECT COUNT(*) FROM curso").fetchone()[0] == 0:
        for f in sorted(EXAMPLES.glob("*.json")):
            if f.name.endswith(".schema.json"):
                continue
            _seed(conn, json.loads(f.read_text(encoding="utf-8")))
        conn.commit()
    conn.close()


def _seed(conn, data):
    c = data["curso"]
    conn.execute("INSERT OR IGNORE INTO curso VALUES (?,?,?)", (c["id"], c["nombre"], c["carrera"]))
    for x in data["competencias"]:
        conn.execute("INSERT OR IGNORE INTO competencia VALUES (?,?,?,?,?)",
                     (c["id"], x["codigo"], x["descripcion"], x["tipo"], x["nivel"]))
    for x in data["logros"]:
        conn.execute("INSERT OR IGNORE INTO logro VALUES (?,?,?,?)",
                     (c["id"], x["codigo"], x["descripcion"], x["codigo_competencia"]))
    for x in data["capacidades"]:
        conn.execute("INSERT OR IGNORE INTO capacidad VALUES (?,?,?,?)",
                     (c["id"], x["codigo"], x["descripcion"], x["unidad_aprendizaje"]))
    for x in data["logro_capacidades"]:
        conn.execute("INSERT OR IGNORE INTO logro_capacidad VALUES (?,?,?)",
                     (c["id"], x["codigo_logro"], x["codigo_capacidad"]))


def list_cursos():
    conn = connect()
    rows = conn.execute("SELECT * FROM curso ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_rows(curso_id):
    """Filas planas del curso (o None si no existe)."""
    conn = connect()
    curso = conn.execute("SELECT * FROM curso WHERE id=?", (curso_id,)).fetchone()
    if curso is None:
        conn.close()
        return None
    rows = {
        "curso": dict(curso),
        "competencias": [dict(r) for r in conn.execute(
            "SELECT * FROM competencia WHERE curso_id=? ORDER BY codigo", (curso_id,))],
        "logros": [dict(r) for r in conn.execute(
            "SELECT * FROM logro WHERE curso_id=? ORDER BY codigo", (curso_id,))],
        "capacidades": [dict(r) for r in conn.execute(
            "SELECT * FROM capacidad WHERE curso_id=? ORDER BY unidad_aprendizaje, codigo", (curso_id,))],
        "logro_capacidades": [dict(r) for r in conn.execute(
            "SELECT * FROM logro_capacidad WHERE curso_id=?", (curso_id,))],
    }
    conn.close()
    return rows


def assemble(rows):
    """Anida filas planas en curso -> competencias -> logros -> capacidades."""
    caps = {c["codigo"]: c for c in rows["capacidades"]}
    links = {}
    for l in rows["logro_capacidades"]:
        links.setdefault(l["codigo_logro"], []).append(caps.get(l["codigo_capacidad"]))
    by_comp = {}
    for lg in rows["logros"]:
        item = {k: lg[k] for k in ("codigo", "descripcion", "codigo_competencia")}
        item["capacidades"] = [c for c in links.get(lg["codigo"], []) if c]
        by_comp.setdefault(lg["codigo_competencia"], []).append(item)
    comps = []
    for comp in rows["competencias"]:
        item = {k: comp[k] for k in ("codigo", "descripcion", "tipo", "nivel")}
        item["logros"] = by_comp.get(comp["codigo"], [])
        comps.append(item)
    return {**rows["curso"], "competencias": comps}
