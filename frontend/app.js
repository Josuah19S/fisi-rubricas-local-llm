const $ = (s) => document.querySelector(s);

// Log en consola del navegador + panel visible.
function logLine(msg, level = "info") {
  const text = `[${new Date().toLocaleTimeString()}] ${msg}`;
  (level === "error" ? console.error : level === "warn" ? console.warn : console.info)(text);
  const box = document.getElementById("log");
  if (box) {
    const d = document.createElement("div");
    d.className = "log-" + level;
    d.textContent = text;
    box.appendChild(d);
    box.scrollTop = box.scrollHeight;
  }
}

window.addEventListener("error", (e) => logLine("window.error: " + e.message, "error"));
window.addEventListener("unhandledrejection", (e) => logLine("promesa rechazada: " + (e.reason?.message || e.reason), "error"));

async function api(path, opts = {}) {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const e = new Error(`${res.status} — ${err.detail || res.statusText}`);
    e.status = res.status;
    e.requestId = res.headers.get("X-Request-ID") || "-";
    throw e;
  }
  return res.json();
}

async function fillCursos(select) {
  logLine("cargando cursos…");
  const cursos = await api("/api/v1/cursos");
  select.innerHTML = cursos.map((c) => `<option value="${c.id}">${c.id} — ${c.nombre}</option>`).join("");
  logLine(`cursos cargados: ${cursos.length}`);
}

async function loadHealth() {
  const el = document.getElementById("health");
  if (!el) return;
  try {
    const h = await api("/api/v1/health");
    el.textContent = `${h.ollama ? "●" : "○"} Ollama ${h.ollama ? "ok" : "sin conexión"} · ${h.modelo}`;
    el.classList.toggle("bad", !h.ollama);
  } catch (e) {
    el.textContent = "○ Ollama sin conexión";
    el.classList.add("bad");
  }
}

document.addEventListener("DOMContentLoaded", loadHealth);
