import json
import logging
import os
import time
import httpx

log = logging.getLogger("rubricas.llm")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:2b")
TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "300"))


class LLMUnavailable(Exception):
    pass


class LLMTimeout(Exception):
    pass


def warm_up():
    """Carga el modelo en memoria y fija keep_alive (best-effort)."""
    try:
        with httpx.Client(timeout=120) as client:
            client.post(f"{OLLAMA_URL}/api/generate", json={
                "model": MODEL, "prompt": "hola", "stream": False,
                "options": {"num_predict": 1, "num_ctx": 4096, "num_gpu": 0},
                "keep_alive": "30m",
            })
    except Exception:
        pass


def generate(messages, schema, num_predict: int = 1600, timeout: int = TIMEOUT):
    """Llama a Ollama /api/chat con structured output. Devuelve (json_dict, meta)."""
    body = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "think": False,
        "format": schema,
        "options": {"temperature": 0.1, "num_predict": num_predict,
                    "num_ctx": 4096, "seed": 42, "num_gpu": 0},
        "keep_alive": "30m",
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            t0 = time.perf_counter()
            log.info("generate model=%s num_predict=%s", MODEL, num_predict)
            r = client.post(f"{OLLAMA_URL}/api/chat", json=body)
    except httpx.ConnectError as e:
        log.error("generate: Ollama no accesible (%s)", e)
        raise LLMUnavailable(f"No se pudo conectar a Ollama: {e}")
    except httpx.TimeoutException as e:
        log.error("generate: timeout tras %.1fs", time.perf_counter() - t0)
        raise LLMTimeout(f"Timeout de generación: {e}")

    if r.status_code != 200:
        log.error("generate: status %s (%s)", r.status_code, r.text[:200])
        raise LLMUnavailable(f"Ollama status {r.status_code}: {r.text[:200]}")

    j = r.json()
    log.info("generate ok eval_count=%s prompt_eval=%s done_reason=%s %.1fs",
             j.get("eval_count"), j.get("prompt_eval_count"), j.get("done_reason"),
             time.perf_counter() - t0)
    try:
        data = json.loads(j["message"]["content"])
    except (KeyError, json.JSONDecodeError) as e:
        log.warning("generate: respuesta no-JSON (%s)", e)
        raise ValueError(f"Respuesta del modelo no es JSON válido: {e}")
    return data, j
