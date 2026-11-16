async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

const $ = (s) => document.querySelector(s);

async function fillCursos(select) {
  const cursos = await api("/api/v1/cursos");
  select.innerHTML = cursos
    .map((c) => `<option value="${c.id}">${c.id} — ${c.nombre}</option>`)
    .join("");
}
