# Rúbricas FISI — PoC

Generador de rúbricas de evaluación con **LLM local** (Qwen 3.5 2B vía Ollama, CPU-only).

## Requisitos
- Python 3.11+
- Ollama corriendo con el modelo `qwen3.5:2b`

## Instalación
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecutar
```powershell
ollama serve                 # si no está corriendo
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```
Abrir http://127.0.0.1:8000

## Uso
- **Registro** (`/`): ver la jerarquía `curso → competencias → logros → capacidades`; agregar (solo sesión).
- **Generar** (`/generar.html`): elegir curso, seleccionar insumos, indicar actividad/tipo/nº de criterios → rúbrica.
- Exportación: Markdown (`.md`) y Excel (`.xlsx`).

## Logs y configuración
- `POST /api/v1/rubricas` devuelve headers `X-Request-ID`, `X-Elapsed-Ms`, `X-Tokens`, `X-Attempts`.
- **Servidor:** logs del `logger rubricas` (intento, tokens, `done_reason`, duración, `rid`).
- **Navegador:** panel "Logs" visible en cada página + `console`.
- Variables: `OLLAMA_MODEL`, `OLLAMA_URL`, `OLLAMA_TIMEOUT` (300 s), `LOG_LEVEL` (INFO).

## Notas
- La semilla SQLite (`data/seed.sqlite`) se genera al iniciar desde `data/examples/*.json`.
- Los registros agregados por UI **no** se persisten.
- Una rúbrica 4×4 tarda **~100–160 s** en CPU (warm-up del modelo al arrancar).
