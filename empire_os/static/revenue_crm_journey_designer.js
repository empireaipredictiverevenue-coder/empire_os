"use strict";
/* First-party, fully client-local *design-only* graph editor.
   No contact data, send API, localStorage, background timer or mutation endpoint. */
(() => {
  const DESIGN_SCHEMA = "empire.revenue_crm_visual_draft.v1";
  const GRAPH_SCHEMA = "empire.revenue_crm_omnichannel_graph.v1";
  const NS = "http://www.w3.org/2000/svg";
  const MAX_NODES = 28, MAX_EDGES = 60;
  const byId = id => document.getElementById(id);
  const ui = {
    status: byId("status"), board: byId("board"), nodes: byId("nodes"),
    edges: byId("edges"), name: byId("design-name"),
    nodeLabel: byId("node-label"), help: byId("selected-help"),
    from: byId("edge-from"), to: byId("edge-to"),
    feedback: byId("edge-feedback"), segments: byId("segments"),
    segmentStatus: byId("segment-status"), file: byId("file")
  };
  let base = null, model = null, selectedId = null, customCounter = 0;

  function status(message, kind) {
    ui.status.textContent = message;
    ui.status.className = "status" + (kind ? " " + kind : "");
  }
  function feedback(message) { ui.feedback.textContent = message; }
  function limit(v, min, max) { return Math.max(min, Math.min(max, v)); }
  function safeLabel(s) {
    return typeof s === "string" && s.length > 0 && s.length <= 64 &&
      !/[\u0000-\u001f\u007f]/.test(s) &&
      !s.includes("@") && !s.includes("://") && !!s.trim();
  }
  function isPlain(o) {
    return !!o && typeof o === "object" && !Array.isArray(o);
  }
  function defaultModel(graph) {
    return {
      schema_version: DESIGN_SCHEMA,
      state: "DESIGN_ONLY", execution_authority: "none",
      tenant_data_included: false, server_persistence: false,
      parent_blueprint_schema: GRAPH_SCHEMA, revision: 1,
      name: "Customer lifecycle review",
      nodes: graph.nodes.map((n, i) => ({
        id: n.id, type: n.type, label: n.label,
        x: 50 + (i % 4) * 236, y: 80 + Math.floor(i / 4) * 220,
        locked: true
      })),
      edges: graph.edges.map(e => ({
        from: e.from, to: e.to, condition: "evidence_review_only", locked: true
      }))
    };
  }
  function mandatoryStagesPreserved(edges) {
    // A custom branch must not offer a route from start to outcome that
    // skips even one canonical consent, identity, buyer or revenue gate.
    const required = base.nodes.map(n => n.id);
    const first = required[0], last = required[required.length - 1];
    for (const gate of required.slice(1, -1)) {
      const seen = new Set([first]), queue = [first];
      while (queue.length) {
        const current = queue.shift();
        for (const edge of edges) {
          if (edge.from !== current || edge.to === gate || seen.has(edge.to)) continue;
          seen.add(edge.to); queue.push(edge.to);
        }
      }
      if (seen.has(last)) return false;
    }
    return true;
  }
  function dag(nodes, edges) {
    const adj = new Map(nodes.map(n => [n.id, []]));
    for (const e of edges) adj.get(e.from).push(e.to);
    const visiting = new Set(), done = new Set();
    function dfs(id) {
      if (visiting.has(id)) return false;
      if (done.has(id)) return true;
      visiting.add(id);
      for (const target of adj.get(id)) if (!dfs(target)) return false;
      visiting.delete(id); done.add(id);
      return true;
    }
    return nodes.every(n => dfs(n.id));
  }
  function validate(candidate) {
    if (!base || !isPlain(candidate) ||
        candidate.schema_version !== DESIGN_SCHEMA ||
        candidate.state !== "DESIGN_ONLY" ||
        candidate.execution_authority !== "none" ||
        candidate.tenant_data_included !== false ||
        candidate.server_persistence !== false ||
        candidate.parent_blueprint_schema !== GRAPH_SCHEMA ||
        !safeLabel(candidate.name) ||
        !Number.isSafeInteger(candidate.revision) ||
        candidate.revision < 1 || candidate.revision > 1000000 ||
        !Array.isArray(candidate.nodes) || !Array.isArray(candidate.edges) ||
        candidate.nodes.length < base.nodes.length ||
        candidate.nodes.length > MAX_NODES || candidate.edges.length > MAX_EDGES)
      throw new Error("Invalid design schema or limits");

    const ids = new Set(), originals = new Map(base.nodes.map(n => [n.id, n]));
    const nodes = candidate.nodes.map(n => {
      if (!isPlain(n) || typeof n.id !== "string" ||
          !/^[a-z][a-z0-9_-]{1,48}$/.test(n.id) || ids.has(n.id) ||
          !safeLabel(n.label) || !Number.isInteger(n.x) || !Number.isInteger(n.y) ||
          n.x < 0 || n.x > 1400 || n.y < 0 || n.y > 1100 ||
          typeof n.locked !== "boolean")
        throw new Error("Invalid, repeated or out-of-bounds step");
      ids.add(n.id);
      const canonical = originals.get(n.id);
      if (canonical) {
        if (n.type !== canonical.type || n.label !== canonical.label || !n.locked)
          throw new Error("Canonical security gate cannot be modified");
      } else if (!n.id.startsWith("custom_") || n.locked ||
                 !["review", "decision"].includes(n.type)) {
        throw new Error("Only manual review or decision steps may be added");
      }
      return {
        id: n.id, type: n.type, label: n.label, x: n.x, y: n.y,
        locked: n.locked
      };
    });
    if (![...originals.keys()].every(id => ids.has(id)))
      throw new Error("A mandatory lifecycle step was removed");

    const unique = new Set();
    const edges = candidate.edges.map(e => {
      if (!isPlain(e) || !ids.has(e.from) || !ids.has(e.to) ||
          e.from === e.to || e.condition !== "evidence_review_only" ||
          typeof e.locked !== "boolean")
        throw new Error("Invalid review-only connection");
      const key = e.from + "|" + e.to;
      if (unique.has(key)) throw new Error("Duplicate review connection");
      unique.add(key);
      return { from: e.from, to: e.to, condition: e.condition, locked: e.locked };
    });
    const basePairs = new Set(base.edges.map(e => e.from + "|" + e.to));
    if (!base.edges.every(b => edges.some(e =>
          e.from === b.from && e.to === b.to && e.locked)) ||
        edges.some(e => e.locked && !basePairs.has(e.from + "|" + e.to)))
      throw new Error("Canonical lifecycle links cannot be removed or forged");
    if (!dag(nodes, edges)) throw new Error("Journey cannot contain a cycle");
    if (!mandatoryStagesPreserved(edges))
      throw new Error("Journey cannot bypass consent or other mandatory gates");
    return {
      schema_version: DESIGN_SCHEMA, state: "DESIGN_ONLY",
      execution_authority: "none", tenant_data_included: false,
      server_persistence: false, parent_blueprint_schema: GRAPH_SCHEMA,
      revision: candidate.revision, name: candidate.name, nodes, edges
    };
  }
  function commit(candidate) {
    model = validate(candidate);
    ui.name.value = model.name;
    selectedId = model.nodes.some(n => n.id === selectedId) ? selectedId : null;
    render();
  }
  function mutate(fn) {
    if (!model) return;
    const draft = structuredClone(model);
    try {
      fn(draft);
      draft.revision += 1;
      commit(draft);
      feedback("Design updated locally · not saved to EmpireDB or activated.");
    } catch (err) { feedback(err.message); }
  }
  function nodeBy(id) { return model?.nodes.find(n => n.id === id); }
  function makeOption(value, text) {
    const o = document.createElement("option"); o.value = value;
    o.textContent = text; return o;
  }
  function renderControls() {
    const selected = nodeBy(selectedId);
    ui.help.textContent = selected ?
      selected.locked ? "Required canonical step · position only" : "Custom review step · design only" :
      "Choose a step on the canvas.";
    ui.nodeLabel.value = selected?.label || "";
    ui.nodeLabel.disabled = !selected || selected.locked;
    byId("delete-node").disabled = !selected || selected.locked;
    const oldFrom = ui.from.value, oldTo = ui.to.value;
    ui.from.replaceChildren(); ui.to.replaceChildren();
    for (const n of model.nodes) {
      ui.from.append(makeOption(n.id, n.label));
      ui.to.append(makeOption(n.id, n.label));
    }
    ui.from.value = model.nodes.some(n => n.id === oldFrom) ? oldFrom :
      (selected?.id || model.nodes[0].id);
    ui.to.value = model.nodes.some(n => n.id === oldTo) ? oldTo :
      model.nodes[model.nodes.length - 1].id;
  }
  function drawEdges() {
    ui.edges.replaceChildren();
    ui.edges.setAttribute("viewBox", "0 0 1600 1250");
    ui.board.style.width = "1600px"; ui.board.style.height = "1250px";
    for (const edge of model.edges) {
      const from = nodeBy(edge.from), to = nodeBy(edge.to);
      const x1 = from.x + 170, y1 = from.y + 41;
      const x2 = to.x, y2 = to.y + 41;
      const p = document.createElementNS(NS, "path");
      p.setAttribute("d", "M " + x1 + " " + y1 + " C " + (x1 + 50) +
        " " + y1 + ", " + (x2 - 50) + " " + y2 + ", " + x2 + " " + y2);
      p.setAttribute("fill", "none");
      p.setAttribute("stroke", edge.locked ? "#58b7e5" : "#ffcf80");
      p.setAttribute("stroke-width", edge.locked ? "2.4" : "2");
      if (!edge.locked) p.setAttribute("stroke-dasharray", "7 5");
      ui.edges.append(p);
    }
  }
  function select(id) {
    selectedId = id;
    for (const el of ui.nodes.children)
      el.classList.toggle("selected", el.dataset.id === id);
    renderControls();
  }
  function renderNodes() {
    ui.nodes.replaceChildren();
    for (const n of model.nodes) {
      const el = document.createElement("button");
      el.type = "button"; el.className = "node" + (n.locked ? " locked" : "");
      el.dataset.id = n.id; el.style.left = n.x + "px"; el.style.top = n.y + "px";
      el.setAttribute("aria-label", "Move " + n.label + " using arrow keys");
      for (const [cls, content] of [
        ["type", n.locked ? "Mandatory " + n.type : "Custom " + n.type],
        ["name", n.label], ["foot", "Operator review · no actions"]
      ]) {
        const div = document.createElement("span");
        div.className = cls; div.textContent = content; el.append(div);
      }
      el.addEventListener("click", () => select(n.id));
      el.addEventListener("keydown", event => {
        const steps = { ArrowLeft: [-20, 0], ArrowRight: [20, 0],
          ArrowUp: [0, -20], ArrowDown: [0, 20] };
        if (!steps[event.key]) return;
        event.preventDefault();
        const [dx, dy] = steps[event.key];
        mutate(m => {
          const row = m.nodes.find(v => v.id === n.id);
          row.x = limit(row.x + dx, 0, 1400);
          row.y = limit(row.y + dy, 0, 1100);
        });
        ui.nodes.querySelector('[data-id="' + n.id + '"]')?.focus();
      });
      el.addEventListener("pointerdown", event => {
        if (event.button !== 0 || !event.isPrimary) return;
        select(n.id);
        const startX = event.clientX, startY = event.clientY;
        const x = n.x, y = n.y;
        let moved = false;
        el.setPointerCapture(event.pointerId);
        const onMove = ev => {
          if (!el.hasPointerCapture(ev.pointerId)) return;
          const dx = ev.clientX - startX, dy = ev.clientY - startY;
          if (Math.abs(dx) + Math.abs(dy) > 4) moved = true;
          if (!moved) return;
          const row = nodeBy(n.id);
          row.x = limit(Math.round(x + dx), 0, 1400);
          row.y = limit(Math.round(y + dy), 0, 1100);
          el.style.left = row.x + "px"; el.style.top = row.y + "px";
          drawEdges();
        };
        const onEnd = () => {
          el.removeEventListener("pointermove", onMove);
          el.removeEventListener("pointerup", onEnd);
          el.removeEventListener("pointercancel", onEnd);
          if (moved) {
            const cloned = structuredClone(model);
            cloned.revision++;
            commit(cloned);
          }
        };
        el.addEventListener("pointermove", onMove);
        el.addEventListener("pointerup", onEnd);
        el.addEventListener("pointercancel", onEnd);
      });
      ui.nodes.append(el);
    }
    if (selectedId) select(selectedId);
  }
  function render() {
    renderNodes(); drawEdges(); renderControls();
    byId("add-review").disabled = model.nodes.length >= MAX_NODES;
    byId("add-decision").disabled = model.nodes.length >= MAX_NODES;
    byId("connect").disabled = model.edges.length >= MAX_EDGES;
  }
  function addNode(type) {
    mutate(draft => {
      if (draft.nodes.length >= MAX_NODES) throw new Error("Step limit reached");
      let id;
      do { customCounter++; id = "custom_" + customCounter; }
      while (draft.nodes.some(n => n.id === id));
      draft.nodes.push({
        id, label: type === "review" ? "Human qualification review" : "Evidence decision",
        type, x: 1030, y: limit(70 + customCounter * 115, 0, 1100),
        locked: false
      });
      selectedId = id;
    });
  }
  function connect(remove) {
    const from = ui.from.value, to = ui.to.value;
    mutate(draft => {
      const index = draft.edges.findIndex(e => e.from === from && e.to === to);
      if (remove) {
        if (index < 0) throw new Error("Connection does not exist");
        if (draft.edges[index].locked) throw new Error("Mandatory connection cannot be removed");
        draft.edges.splice(index, 1);
      } else {
        if (index >= 0) throw new Error("Connection already exists");
        if (from === to) throw new Error("Cannot connect a step to itself");
        if (draft.edges.length >= MAX_EDGES) throw new Error("Connection limit reached");
        draft.edges.push({
          from, to, condition: "evidence_review_only", locked: false
        });
      }
    });
  }
  async function refreshSegments() {
    ui.segmentStatus.textContent = "Checking authenticated tenant page…";
    ui.segments.replaceChildren();
    try {
      const res = await fetch("/v1/revenue-crm/journeys/segments/preview?limit=100", {
        cache: "no-store", credentials: "same-origin"
      });
      if (!res.ok) throw new Error("CRM segment reader unavailable (HTTP " + res.status + ")");
      const data = await res.json();
      if (data.read_only !== true || data.mode !== "OBSERVE" ||
          data.execution_authority !== "none" || !Array.isArray(data.segments))
        throw new Error("Segment authority contract mismatch");
      ui.segmentStatus.textContent = "Observed records: " + data.observed_prospect_count +
        (data.page_may_be_partial ? " · page may be partial" : " · page only");
      for (const segment of data.segments.slice(0, 30)) {
        const row = document.createElement("div"); row.className = "segment-count";
        const name = document.createElement("span"), count = document.createElement("strong");
        name.textContent = String(segment.name).slice(0, 64);
        count.textContent = String(segment.count);
        row.append(name, count); ui.segments.append(row);
      }
    } catch (err) {
      ui.segmentStatus.textContent = err.message + ". No sample audience has been substituted.";
    }
  }
  async function initialize() {
    try {
      const result = await fetch("/v1/revenue-crm/journeys/blueprint", {
        cache: "no-store", credentials: "same-origin"
      });
      if (!result.ok) throw new Error("CRM blueprint unavailable (HTTP " + result.status + ")");
      const graph = await result.json();
      if (graph.schema_version !== GRAPH_SCHEMA || graph.execution_authority !== "none" ||
          graph.outbound_enabled !== false || !Array.isArray(graph.nodes) ||
          !Array.isArray(graph.edges) || graph.nodes.length < 1)
        throw new Error("Trusted review-only blueprint required");
      base = graph;
      commit(defaultModel(graph));
      for (const id of ["add-review", "add-decision", "import", "export",
        "reset", "connect", "remove-edge", "edge-from", "edge-to", "refresh-segments"])
        byId(id).disabled = false;
      status("Authenticated CRM graph loaded. Editor is local and DESIGN ONLY. No sends, saves or activations are possible.", "good");
      await refreshSegments();
    } catch (err) {
      status(err.message + " · Editor unavailable until CRM tenant authentication is configured.", "bad");
    }
  }

  byId("add-review").addEventListener("click", () => addNode("review"));
  byId("add-decision").addEventListener("click", () => addNode("decision"));
  byId("delete-node").addEventListener("click", () => mutate(draft => {
    const row = draft.nodes.find(n => n.id === selectedId);
    if (!row || row.locked) throw new Error("Mandatory stage cannot be deleted");
    draft.nodes = draft.nodes.filter(n => n.id !== selectedId);
    draft.edges = draft.edges.filter(e => e.from !== selectedId && e.to !== selectedId);
    selectedId = null;
  }));
  ui.nodeLabel.addEventListener("change", event => mutate(draft => {
    const node = draft.nodes.find(n => n.id === selectedId);
    if (!node || node.locked) throw new Error("Mandatory label cannot be edited");
    node.label = event.target.value.trim();
  }));
  ui.name.addEventListener("change", event => mutate(draft => {
    draft.name = event.target.value.trim();
  }));
  byId("connect").addEventListener("click", () => connect(false));
  byId("remove-edge").addEventListener("click", () => connect(true));
  byId("refresh-segments").addEventListener("click", refreshSegments);
  byId("reset").addEventListener("click", () => {
    selectedId = null; customCounter = 0; commit(defaultModel(base));
    feedback("Local layout reset. No server changes.");
  });
  byId("export").addEventListener("click", () => {
    if (!model) return;
    const blob = new Blob([JSON.stringify(validate(model), null, 2) + "\n"],
      { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url;
    a.download = "empire-revenue-crm-journey-design-v1.json";
    document.body.append(a); a.click(); a.remove(); URL.revokeObjectURL(url);
    feedback("Exported local design metadata only; it cannot execute or contact users.");
  });
  byId("import").addEventListener("click", () => ui.file.click());
  ui.file.addEventListener("change", async event => {
    const file = event.target.files?.[0];
    ui.file.value = "";
    if (!file) return;
    if (file.size > 65536) { feedback("Design file exceeds 64 KB"); return; }
    try {
      const candidate = JSON.parse(await file.text());
      const verified = validate(candidate);
      selectedId = null; commit(verified);
      customCounter = model.nodes.length;
      feedback("Reviewed design imported locally. Not activated or written to the server.");
    } catch (err) { feedback("Import blocked: " + err.message); }
  });
  initialize();
})();
