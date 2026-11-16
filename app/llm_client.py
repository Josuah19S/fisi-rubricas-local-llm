import json
import os
import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:2b")


class LLMUnavailable(Exception):
    pass


class LLMTimeout(Exception):
    pass


def generate(messages, schema, num_predict: int = 1600, timeout: int = 180):
    """Llama a Ollama /api/chat con structured output. Devuelve (json_dict, meta)."""
    body = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "think": False,
        "format": schema,
        "options": {"temperature": 0.1, "num_predict": num_predict,
                    "num_ctx": 4096, "seed": 42},
        "keep_alive": "30m",
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(f"{OLLAMA_URL}/api/chat", json=body)
    except httpx.ConnectError as e:
        raise LLMUnavailable(f"No se pudo conectar a Ollama: {e}")
    except httpx.TimeoutException as e:
        raise LLMTimeout(f"Timeout de generación: {e}")

    if r.status_code != 200:
        raise LLMUnavailable(f"Ollama status {r.status_code}: {r.text[:200]}")

    j = r.json()
    try:
        data = json.loads(j["message"]["content"])
    except (KeyError, json.JSONDecodeError) as e:
        raise ValueError(f"Respuesta del modelo no es JSON válido: {e}")
    return data, j
