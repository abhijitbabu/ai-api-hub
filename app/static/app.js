(function () {
  const cfg = window.HUB_FORM;
  if (!cfg) return;

  const paramsEl = document.getElementById("params");
  const addBtn = document.getElementById("add-param");
  const form = document.getElementById("connector-form");
  const hidden = document.getElementById("input_params");
  const provider = document.getElementById("provider");
  const model = document.getElementById("model");
  const list = document.getElementById("model-list");
  const refresh = document.getElementById("refresh-models");
  const status = document.getElementById("model-status");

  function paramRow(data) {
    const wrap = document.createElement("div");
    wrap.className = "param-row";
    const name = document.createElement("input");
    name.placeholder = "field name";
    name.value = data.name || "";
    name.dataset.k = "name";
    const type = document.createElement("select");
    cfg.FIELD_TYPES.forEach((t) => {
      const o = document.createElement("option");
      o.value = t;
      o.textContent = t;
      if (t === (data.type || "text")) o.selected = true;
      type.appendChild(o);
    });
    type.dataset.k = "type";
    const req = document.createElement("select");
    req.innerHTML = `<option value="true">required</option><option value="false">optional</option>`;
    req.value = data.required ? "true" : "false";
    req.dataset.k = "required";
    const desc = document.createElement("input");
    desc.placeholder = "description";
    desc.value = data.description || "";
    desc.dataset.k = "description";
    const del = document.createElement("button");
    del.type = "button";
    del.className = "btn";
    del.textContent = "Remove";
    del.addEventListener("click", () => wrap.remove());
    wrap.append(name, type, req, desc, del);
    return wrap;
  }

  function serialize() {
    return [...paramsEl.querySelectorAll(".param-row")].map((row) => {
      const get = (k) => row.querySelector(`[data-k="${k}"]`).value;
      return {
        name: get("name").trim(),
        type: get("type"),
        required: get("required") === "true",
        description: get("description"),
      };
    }).filter((p) => p.name);
  }

  function fillModels(id) {
    const models = cfg.MODELS[id] || [];
    list.innerHTML = "";
    models.forEach((m) => {
      const o = document.createElement("option");
      o.value = m;
      list.appendChild(o);
    });
    if (!model.value && models[0]) model.value = models[0];
  }

  (cfg.INITIAL_PARAMS || []).forEach((p) => paramsEl.appendChild(paramRow(p)));
  if (!paramsEl.children.length) paramsEl.appendChild(paramRow({ name: "", type: "text", required: true, description: "" }));
  addBtn.addEventListener("click", () => paramsEl.appendChild(paramRow({ name: "", type: "text", required: false, description: "" })));
  fillModels(provider.value);
  provider.addEventListener("change", () => fillModels(provider.value));

  form.addEventListener("submit", () => {
    hidden.value = JSON.stringify(serialize());
  });

  refresh.addEventListener("click", async () => {
    status.textContent = "Refreshing…";
    try {
      const res = await fetch("/admin/api/models/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: provider.value }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Refresh failed");
      cfg.MODELS[provider.value] = data.models;
      fillModels(provider.value);
      status.textContent = `${data.models.length} models`;
    } catch (err) {
      status.textContent = err.message || "Could not refresh";
    }
  });
})();
