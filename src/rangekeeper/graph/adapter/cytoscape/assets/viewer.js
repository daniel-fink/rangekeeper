(() => {
  // routing.ts
  var names = ["top", "right", "bottom", "left"];
  var normals = {
    top: { x: 0, y: -1 },
    right: { x: 1, y: 0 },
    bottom: { x: 0, y: 1 },
    left: { x: -1, y: 0 }
  };
  var distance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
  function ports(rect) {
    return {
      top: { x: rect.x, y: rect.y - rect.h / 2 },
      right: { x: rect.x + rect.w / 2, y: rect.y },
      bottom: { x: rect.x, y: rect.y + rect.h / 2 },
      left: { x: rect.x - rect.w / 2, y: rect.y }
    };
  }
  function intersection(rect, other) {
    const dx = other.x - rect.x, dy = other.y - rect.y;
    const scale = Math.max(
      Math.abs(dx) / (rect.w / 2),
      Math.abs(dy) / (rect.h / 2)
    );
    return scale ? { x: rect.x + dx / scale, y: rect.y + dy / scale } : ports(rect).top;
  }
  function choosePort(rect, reference, previous) {
    const points = ports(rect);
    let best = names[0];
    for (const name of names.slice(1))
      if (distance(points[name], reference) < distance(points[best], reference) - 1e-9)
        best = name;
    if (names.includes(previous) && distance(points[previous], reference) - distance(points[best], reference) < 6)
      return previous;
    return best;
  }
  function handleLength(point, other, normal) {
    const span = distance(point, other);
    const forward = (other.x - point.x) * normal.x + (other.y - point.y) * normal.y;
    const desired = forward >= 0 ? forward * 0.5 : 6.25 * Math.sqrt(-forward);
    return Math.min(120, span * 0.75, Math.max(32, desired));
  }
  function route({
    source,
    target,
    sourceId,
    targetId,
    sourceReference,
    targetReference,
    previous,
    lane = 0,
    laneCount = 1
  }) {
    const self = sourceId === targetId;
    const coincident = distance(source, target) < 1e-6;
    let sourcePort, targetPort;
    if (self) {
      sourcePort = "top";
      targetPort = "right";
    } else if (coincident) {
      sourcePort = sourceId < targetId ? "right" : "left";
      targetPort = sourcePort === "right" ? "left" : "right";
    } else {
      sourcePort = choosePort(
        source,
        sourceReference || intersection(source, target),
        previous?.sourcePort
      );
      targetPort = choosePort(
        target,
        targetReference || intersection(target, source),
        previous?.targetPort
      );
    }
    const a = ports(source)[sourcePort];
    let b = ports(target)[targetPort];
    if (distance(a, b) < 1e-6) {
      targetPort = names.find((name) => distance(a, ports(target)[name]) > 1e-6);
      b = ports(target)[targetPort];
    }
    if (self) {
      const handle = Math.min(120, Math.max(20, distance(a, b) * 0.35));
      const centre = source.nodePosition || source;
      const offsetY = source.y - centre.y;
      const radius = Math.max(
        Math.abs(a.y - centre.y) + handle,
        Math.hypot(b.x - centre.x + handle, offsetY)
      ) + lane * 24;
      const rightX = Math.sqrt(Math.max(0, radius * radius - offsetY * offsetY));
      const angleA = -Math.PI / 2, angleB = Math.atan2(offsetY, rightX);
      return {
        sourcePort,
        targetPort,
        source: a,
        target: b,
        controls: [
          { x: centre.x, y: centre.y - radius },
          { x: centre.x + rightX, y: source.y }
        ],
        loop: {
          direction: ((angleA + angleB) / 2 + Math.PI / 2) * 180 / Math.PI,
          sweep: (angleB - angleA) * 180 / Math.PI,
          distance: radius / 1.4
        }
      };
    }
    const offset = (point, other, normal) => {
      const handle = Math.min(
        handleLength(point, other, normal),
        laneCount > 1 ? distance(a, b) * 0.2 : Infinity
      );
      return { x: point.x + normal.x * handle, y: point.y + normal.y * handle };
    };
    const c1 = offset(a, b, normals[sourcePort]), c2 = offset(b, a, normals[targetPort]);
    if (laneCount === 1)
      return { sourcePort, targetPort, source: a, target: b, controls: [c1, c2] };
    const dx = (b.x - a.x) * (sourceId < targetId ? 1 : -1), dy = (b.y - a.y) * (sourceId < targetId ? 1 : -1);
    const length = Math.hypot(dx, dy);
    const spacing = Math.min(28, length * 0.24 / Math.max(1, laneCount - 1));
    const spread = (lane - (laneCount - 1) / 2) * spacing;
    const interior = (t) => ({
      x: c1.x + (c2.x - c1.x) * t - dy / length * spread,
      y: c1.y + (c2.y - c1.y) * t + dx / length * spread
    });
    return {
      sourcePort,
      targetPort,
      source: a,
      target: b,
      controls: [c1, interior(1 / 3), interior(2 / 3), c2]
    };
  }
  function curvePoint(result, fraction) {
    const cs = result.controls;
    if (!cs.length)
      return {
        x: result.source.x + (result.target.x - result.source.x) * fraction,
        y: result.source.y + (result.target.y - result.source.y) * fraction
      };
    const mid = (a2, b2) => ({ x: (a2.x + b2.x) / 2, y: (a2.y + b2.y) / 2 });
    const scaled = fraction * cs.length, i = Math.min(cs.length - 1, Math.floor(scaled)), t = scaled - i;
    const a = i ? mid(cs[i - 1], cs[i]) : result.source;
    const b = i === cs.length - 1 ? result.target : mid(cs[i], cs[i + 1]);
    return {
      x: (1 - t) ** 2 * a.x + 2 * (1 - t) * t * cs[i].x + t * t * b.x,
      y: (1 - t) ** 2 * a.y + 2 * (1 - t) * t * cs[i].y + t * t * b.y
    };
  }
  function sampleCurve(result) {
    const count = Math.max(2, result.controls.length * 32);
    const samples = [{ point: result.source, length: 0 }];
    for (let i = 1; i <= count; i++) {
      const point = curvePoint(result, i / count), previous = samples.at(-1);
      samples.push({
        point,
        length: previous.length + distance(previous.point, point)
      });
    }
    const atLength = (length) => {
      const i = Math.max(
        1,
        samples.findIndex((s) => s.length >= length)
      );
      const a = samples[i - 1], b = samples[i], t = (length - a.length) / (b.length - a.length || 1);
      return {
        x: a.point.x + (b.point.x - a.point.x) * t,
        y: a.point.y + (b.point.y - a.point.y) * t
      };
    };
    return {
      total: samples.at(-1).length,
      centreLength: samples[count / 2].length,
      atLength
    };
  }
  function labelWidth(result, arc = sampleCurve(result)) {
    const { total, atLength } = arc, centre = curvePoint(result, 0.5);
    return Math.max(
      0,
      Math.min(
        distance(atLength(total * 0.25), atLength(total * 0.75)) - 8,
        2 * (distance(centre, result.source) - 12),
        2 * (distance(centre, result.target) - 12)
      )
    );
  }
  function fitLabel(text, maxWidth, measure) {
    if (measure(text) < maxWidth) return { text, width: measure(text) };
    let fitted = "";
    for (let i = 0; i < text.length; i++) {
      if (measure(fitted + text[i] + "\u2026") > maxWidth) break;
      fitted += text[i];
    }
    if (fitted.length < text.length) fitted += "\u2026";
    return { text: fitted, width: measure(fitted) };
  }
  function labelAngle(result, displayedWidth, arc = sampleCurve(result)) {
    const half = Math.min(
      Math.max(1, displayedWidth / 2),
      arc.centreLength,
      arc.total - arc.centreLength
    );
    let a = arc.atLength(arc.centreLength - half), b = arc.atLength(arc.centreLength + half);
    if (distance(a, b) < 1e-6) {
      a = result.source;
      b = result.target;
    }
    let angle = Math.atan2(b.y - a.y, b.x - a.x);
    if (angle > Math.PI / 2) angle -= Math.PI;
    if (angle < -Math.PI / 2) angle += Math.PI;
    return angle;
  }
  function style(result, sourcePosition, targetPosition) {
    const a = result.source, b = result.target;
    const output = {
      "source-endpoint": `${a.x - sourcePosition.x}px ${a.y - sourcePosition.y}px`,
      "target-endpoint": `${b.x - targetPosition.x}px ${b.y - targetPosition.y}px`,
      "curve-style": "unbundled-bezier"
    };
    if (result.loop)
      return {
        ...output,
        "curve-style": "bezier",
        "control-point-step-size": result.loop.distance,
        "loop-direction": `${result.loop.direction}deg`,
        "loop-sweep": `${result.loop.sweep}deg`,
        "control-point-distances": String(result.loop.distance),
        "control-point-weights": ".5",
        "edge-distances": "node-position"
      };
    const dx = b.x - a.x, dy = b.y - a.y, length = Math.hypot(dx, dy);
    return {
      ...output,
      "edge-distances": "endpoints",
      "control-point-weights": result.controls.map((c) => ((c.x - a.x) * dx + (c.y - a.y) * dy) / (length * length)).join(" "),
      "control-point-distances": result.controls.map((c) => ((c.x - a.x) * -dy + (c.y - a.y) * dx) / length).join(" ")
    };
  }

  // membership.ts
  function parents(graph) {
    const result = Object.fromEntries(
      graph.elements.filter((e) => !("source" in e.data)).map((e) => [e.data.id, []])
    );
    for (const [id, a] of Object.entries(graph.assemblies))
      for (const member of a.entities) result[member].push(id);
    for (const list of Object.values(result)) list.sort();
    return result;
  }
  function descendants(graph, id) {
    const found = /* @__PURE__ */ new Set();
    const visit = (current) => {
      for (const child of graph.assemblies[current]?.entities || [])
        if (!found.has(child)) {
          found.add(child);
          visit(child);
        }
    };
    visit(id);
    found.delete(id);
    return [...found];
  }
  function assemblyOrder(graph) {
    const ordered = [], active = /* @__PURE__ */ new Set(), seen = /* @__PURE__ */ new Set();
    const visit = (id) => {
      if (seen.has(id)) return;
      if (active.has(id)) throw new Error("Assembly membership cycle");
      active.add(id);
      for (const child of graph.assemblies[id].entities)
        if (graph.assemblies[child]) visit(child);
      active.delete(id);
      seen.add(id);
      ordered.push(id);
    };
    Object.keys(graph.assemblies).forEach(visit);
    return ordered;
  }
  function revealPath(graph, id) {
    const owners = parents(graph), path = [];
    while (owners[id]?.length) {
      id = owners[id][0];
      path.push(id);
    }
    return path;
  }

  // geometry.ts
  function connectionCentre(ctx2, node) {
    const p = node.position();
    return {
      x: p.x,
      y: p.y - (node.hasClass("frame") ? node.height() / 2 - ctx2.HEADER / 2 : 0)
    };
  }
  function headerEndpoint(ctx2, node, other) {
    const p = ctx2.connectionCentre(node), q = ctx2.connectionCentre(other);
    const dx = q.x - p.x, dy = q.y - p.y;
    const scale = Math.max(
      Math.abs(dx) / (node.width() / 2),
      Math.abs(dy) / (ctx2.HEADER / 2)
    );
    return scale ? { x: p.x + dx / scale, y: p.y + dy / scale } : { x: p.x, y: p.y + ctx2.HEADER / 2 };
  }
  function endpoint(ctx2, edge, source) {
    const node = source ? edge.source() : edge.target();
    const other = source ? edge.target() : edge.source();
    const p = node.position();
    if (node.hasClass("frame")) {
      const q = ctx2.headerEndpoint(node, other);
      return `${q.x - p.x}px ${q.y - p.y}px`;
    }
    if (other.hasClass("frame")) {
      const q = ctx2.headerEndpoint(other, node);
      return `${Math.atan2(q.y - p.y, q.x - p.x) * 180 / Math.PI + 90}deg`;
    }
    return "outside-to-node";
  }
  function connectionGeometry(ctx2, n) {
    return {
      ...ctx2.connectionCentre(n),
      w: n.width(),
      h: n.hasClass("frame") ? ctx2.HEADER : n.height(),
      nodePosition: { ...n.position() }
    };
  }
  function updateConnections(ctx2) {
    const eligible = ctx2.cy.edges().filter((e) => ctx2.fourPorts && !ctx2.layoutMode && !e.hasClass("hidden"));
    const references = /* @__PURE__ */ new Map(), pairs = /* @__PURE__ */ new Map();
    const finite = (p) => p && Number.isFinite(p.x) && Number.isFinite(p.y);
    ctx2.routes = /* @__PURE__ */ new Map();
    const nativePairs = eligible.filter(
      (e) => !e.source().hasClass("frame") && !e.target().hasClass("frame") && e.source().id() !== e.target().id() && Math.hypot(
        e.source().position().x - e.target().position().x,
        e.source().position().y - e.target().position().y
      ) > 1e-6
    );
    ctx2.cy.batch(
      () => nativePairs.forEach((e) => {
        e.removeStyle(ctx2.routingStyle);
        e.style({
          "curve-style": "straight",
          "source-endpoint": "outside-to-line",
          "target-endpoint": "outside-to-line"
        });
      })
    );
    nativePairs.forEach((e) => {
      const source = e.sourceEndpoint(), target = e.targetEndpoint();
      if (finite(source) && finite(target))
        references.set(e.id(), {
          sourceReference: source,
          targetReference: target
        });
    });
    for (const e of [...eligible].sort((a, b) => a.id().localeCompare(b.id()))) {
      const key = JSON.stringify([e.source().id(), e.target().id()].sort());
      if (!pairs.has(key)) pairs.set(key, []);
      pairs.get(key).push(e.id());
    }
    ctx2.cy.batch(
      () => ctx2.cy.edges().forEach((e) => {
        const active = eligible.has(e);
        e.toggleClass("four-port", active);
        if (!active) {
          e.removeStyle(ctx2.routingStyle);
          e.style({
            "source-endpoint": ctx2.endpoint(e, true),
            "target-endpoint": ctx2.endpoint(e, false)
          });
          return;
        }
        const source = e.source(), target = e.target();
        const pair = pairs.get(JSON.stringify([source.id(), target.id()].sort()));
        const result = route({
          source: ctx2.connectionGeometry(source),
          target: ctx2.connectionGeometry(target),
          sourceId: source.id(),
          targetId: target.id(),
          ...references.get(e.id()),
          previous: ctx2.portChoices.get(e.id()),
          lane: pair.indexOf(e.id()),
          laneCount: pair.length
        });
        ctx2.portChoices.set(e.id(), {
          sourcePort: result.sourcePort,
          targetPort: result.targetPort
        });
        ctx2.routes.set(e.id(), result);
        e.style(
          style(result, source.position(), target.position())
        );
      })
    );
    const labels = ctx2.cy.edges().filter((e) => !e.hasClass("hidden")).map((e) => {
      const geometry = {
        source: e.sourceEndpoint(),
        target: e.targetEndpoint(),
        controls: e.controlPoints() || []
      };
      const arc = sampleCurve(geometry), width = labelWidth(geometry, arc);
      ctx2.labelMeasure.font = `${e.style("font-style")} ${e.style("font-weight")} ${e.numericStyle("font-size")}px ${e.style("font-family")}`;
      let text = e.style("label");
      if (e.style("text-transform") === "uppercase") text = text.toUpperCase();
      if (e.style("text-transform") === "lowercase") text = text.toLowerCase();
      const fitted = fitLabel(
        text,
        Math.max(1, width),
        (text2) => Math.ceil(ctx2.labelMeasure.measureText(text2).width)
      );
      const style2 = {
        "text-max-width": Math.max(1, width),
        "text-opacity": width >= 32 ? 1 : 0
      };
      if (e.hasClass("four-port"))
        style2["text-rotation"] = `${labelAngle(geometry, fitted.width + 2 * e.numericStyle("text-background-padding"), arc)}rad`;
      return [e, style2];
    });
    ctx2.cy.batch(() => labels.forEach(([e, style2]) => e.style(style2)));
  }
  function syncBoxes(ctx2) {
    if (ctx2.syncing || !ctx2.cy) return;
    ctx2.syncing = true;
    {
      for (const id of assemblyOrder(ctx2.data)) {
        const assembly = ctx2.data.assemblies[id];
        const node = ctx2.cy.getElementById(id);
        node.data("frameZ", Math.min(4, revealPath(ctx2.data, id).length));
        node.data(
          "title",
          `${ctx2.collapsed.has(id) ? "\u25B8" : "\u25BE"} ${assembly.name}`
        );
        const members = ctx2.cy.collection(
          assembly.entities.map((mid) => ctx2.cy.getElementById(mid)[0]).filter(
            (n) => n && !n.hasClass("hidden")
          )
        );
        const frame = ctx2.mode === "outlines" && !ctx2.layoutMode && !ctx2.collapsed.has(id) && !node.hasClass("hidden") && members.length > 0;
        node.toggleClass("frame", frame);
        if (frame) {
          if (ctx2.drag?.id === id) continue;
          const bb = members.boundingBox({
            includeLabels: true,
            includeOverlays: false,
            useCache: false
          });
          const w = Math.max(180, bb.w + 2 * ctx2.PAD), h = bb.h + 2 * ctx2.PAD + ctx2.HEADER;
          const stop = ctx2.HEADER / h * 100;
          node.data({
            boxWidth: w,
            boxHeight: h,
            bandStops: `0% ${stop}% ${stop}% 100%`
          });
          node.position({
            x: (bb.x1 + bb.x2) / 2,
            y: (bb.y1 + bb.y2 - ctx2.HEADER) / 2
          });
        } else if (ctx2.compactPositions[id] && ctx2.drag?.id !== id) {
          node.position({ ...ctx2.compactPositions[id] });
        }
      }
    }
    ctx2.updateConnections();
    ctx2.syncing = false;
  }

  // document.ts
  var isEdge = (data) => "source" in data;

  // navigation.ts
  function pushHistory(ctx2) {
    ctx2.history.push(ctx2.snapshot());
    ctx2.$("back").disabled = false;
  }
  function changeCollapse(ctx2, ids, value) {
    ctx2.pushHistory();
    for (const id of ids)
      value ? ctx2.collapsed.add(id) : ctx2.collapsed.delete(id);
    ctx2.applyVisibility();
  }
  function fit(ctx2) {
    if (ctx2.visible().length) ctx2.cy.fit(ctx2.visible(), 55);
  }
  function focusOn(ctx2, id) {
    ctx2.pushHistory();
    const assembly = ctx2.data.assemblies[id];
    if (assembly) ctx2.focusIds = /* @__PURE__ */ new Set([id, ...descendants(ctx2.data, id)]);
    else {
      const element = ctx2.cy.getElementById(id);
      ctx2.focusIds = /* @__PURE__ */ new Set([id]);
      if (element.isEdge()) {
        ctx2.focusIds.add(element.data("source"));
        ctx2.focusIds.add(element.data("target"));
      }
      for (const item of ctx2.data.elements) {
        const edge = item.data;
        if (isEdge(edge) && (edge.source === id || edge.target === id)) {
          ctx2.focusIds.add(edge.source);
          ctx2.focusIds.add(edge.target);
        }
      }
      for (const [aid] of ctx2.memberships(id)) ctx2.focusIds.add(aid);
    }
    for (const nid of [...ctx2.focusIds])
      for (const aid of ctx2.projection.memberships[nid] || [])
        if (ctx2.collapsed.has(aid)) ctx2.focusIds.add(aid);
    ctx2.applyVisibility();
    ctx2.fit();
  }
  function reset(ctx2) {
    ctx2.pushHistory();
    ctx2.focusIds = null;
    ctx2.applyVisibility();
    ctx2.fit();
  }
  function restore(ctx2) {
    ctx2.updating = true;
    ctx2.cy.batch(
      () => ctx2.cy.nodes().forEach((n) => {
        n.position({ ...ctx2.data.positions[n.id()] });
      })
    );
    for (const id of Object.keys(ctx2.data.assemblies))
      ctx2.compactPositions[id] = { ...ctx2.data.positions[id] };
    ctx2.updating = false;
    ctx2.syncBoxes();
    ctx2.$("timing").textContent = "Reference arrangement restored";
  }
  function reveal(ctx2, id, assemblyId) {
    ctx2.pushHistory();
    if (assemblyId) {
      for (const ancestor of revealPath(ctx2.data, assemblyId))
        ctx2.collapsed.delete(ancestor);
      ctx2.collapsed.delete(assemblyId);
    }
    if (ctx2.focusIds) {
      ctx2.focusIds.add(id);
      if (assemblyId) {
        ctx2.focusIds.add(assemblyId);
        for (const mid of ctx2.data.assemblies[assemblyId].entities)
          ctx2.focusIds.add(mid);
      }
    }
    ctx2.applyVisibility();
    ctx2.select(id);
    ctx2.fit();
  }
  function selectLinkedObject(ctx2) {
    if (!location.hash) return;
    const params = new URLSearchParams(location.hash.slice(1)), ids = params.getAll("select");
    if ([...params.keys()].some((k) => k !== "select") || ids.length !== 1 || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
      ids[0]
    ) || !ctx2.data.details[ids[0]]) {
      ctx2.make(
        "p",
        "This review link does not identify an object in the current graph.",
        ctx2.$("diagnostics"),
        "issue"
      );
      return;
    }
    ctx2.select(ids[0]);
  }

  // inspector.ts
  function valueText(ctx2, value) {
    if (value === null) return "Unknown / not supplied";
    if (value && typeof value === "object" && "units" in value)
      return `${ctx2.valueText(value.value)} ${value.units}`.trim();
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  }
  function evidence(ctx2, parent, fact) {
    if (!fact) {
      ctx2.make("p", "No Fact attached to this item.", parent, "code");
      return;
    }
    const box = ctx2.make("details", void 0, parent);
    ctx2.make("summary", `Evidence \xB7 ${fact.reconciliation || fact.status}`, box);
    if (fact.reconciliation)
      ctx2.make(
        "p",
        `Selected claim is ${fact.reconciliation}. Other claims are retained.`,
        box,
        "issue"
      );
    const visited = /* @__PURE__ */ new Set();
    const appendClaim = (id, host, depth) => {
      if (visited.has(id)) {
        ctx2.make("p", `Previously shown claim ${id}`, host, "code");
        return;
      }
      visited.add(id);
      const c = ctx2.data.claims[id];
      if (!c) return;
      const item = ctx2.make("details", void 0, host);
      ctx2.make(
        "summary",
        `${c.kind}${fact.selected === id ? " \xB7 selected" : ""}`,
        item
      );
      ctx2.make("pre", JSON.stringify(c.value, null, 2), item);
      if (c.method) ctx2.make("pre", JSON.stringify(c.method, null, 2), item);
      for (const source of c.sources) {
        if (source.claim) {
          if (depth < 8) appendClaim(source.claim, item, depth + 1);
          else
            ctx2.make(
              "p",
              "Further evidence available in the embedded view data.",
              item
            );
        } else {
          ctx2.make("p", source.name, item);
          ctx2.make(
            "pre",
            JSON.stringify(
              { reference: source.reference, checksum: source.checksum },
              null,
              2
            ),
            item
          );
        }
      }
    };
    fact.claims.forEach((id) => appendClaim(id, box, 0));
  }
  function nav(ctx2, parent, text, id) {
    const b = ctx2.make("button", text, parent, "nav");
    b.dataset.target = id;
    b.onclick = () => ctx2.select(id, true);
    return b;
  }
  function renderSelection(ctx2) {
    const host = ctx2.$("selection");
    host.replaceChildren();
    ctx2.$("focus").disabled = !ctx2.inspected;
    if (!ctx2.inspected) {
      ctx2.make(
        "p",
        "Search for or select any object or connection. Focus and expand only when you choose.",
        host,
        "empty"
      );
      return;
    }
    const element = ctx2.cy.getElementById(ctx2.inspected), d = ctx2.data.details[ctx2.inspected];
    if (!d && element.length) {
      const edge = element.data();
      ctx2.make("h2", edge.label, host);
      ctx2.make(
        "p",
        edge.connector === "summary" ? "Collapsed relationship summary. This line represents hidden detail; it is not a new domain relationship." : "Recorded Assembly membership, shown as a display connector.",
        host
      );
      ctx2.nav(host, `From \xB7 ${ctx2.label(edge.source)}`, edge.source);
      ctx2.nav(host, `To \xB7 ${ctx2.label(edge.target)}`, edge.target);
      if (edge.membershipPaths?.some((path) => path.length > 2)) {
        ctx2.make("h3", "Membership paths", host);
        for (const path of edge.membershipPaths)
          ctx2.make("p", path.map(ctx2.label).join(" \u2192 "), host);
      }
      if (edge.originalIds) {
        ctx2.make("h3", "Original relationships", host);
        for (const id of edge.originalIds) {
          const original = ctx2.cy.getElementById(id).data();
          ctx2.nav(
            host,
            `${ctx2.label(original.source)} \u2192 ${original.label} \u2192 ${ctx2.label(original.target)}`,
            id
          );
          ctx2.evidence(host, ctx2.data.details[id].fact);
        }
      }
      return;
    }
    if (!d) return;
    ctx2.make("h2", element.data("label"), host);
    ctx2.make(
      "span",
      element.isEdge() ? "Relationship" : ctx2.data.assemblies[ctx2.inspected] ? "Assembly" : "Entity",
      host,
      "tag"
    );
    if (d.classification?.name !== "Assembly")
      ctx2.make("span", d.classification?.name || "Unclassified", host, "tag");
    ctx2.make("p", element.data("code") || ctx2.inspected, host, "code");
    if (element.hasClass("hidden")) {
      ctx2.make(
        "p",
        "Hidden in the current view. Inspection does not expand Assemblies.",
        host,
        "issue"
      );
      if (element.isNode()) {
        const containers = ctx2.memberships(ctx2.inspected).filter(
          ([id]) => ctx2.collapsed.has(id) || ctx2.projection.hiddenIds.includes(id)
        );
        if (containers.length)
          for (const [id, a] of containers) {
            const b = ctx2.make("button", `Reveal in ${a.name}`, host, "nav");
            b.onclick = () => ctx2.reveal(ctx2.inspected, id);
          }
        else {
          const b = ctx2.make("button", "Reveal in view", host, "nav");
          b.onclick = () => ctx2.reveal(ctx2.inspected);
        }
      }
    }
    const assembly = ctx2.data.assemblies[ctx2.inspected];
    if (assembly) {
      const b = ctx2.make(
        "button",
        ctx2.collapsed.has(ctx2.inspected) ? "Expand Assembly" : "Collapse Assembly",
        host,
        "nav"
      );
      b.id = "toggle-collapse";
      b.onclick = () => ctx2.changeCollapse([ctx2.inspected], !ctx2.collapsed.has(ctx2.inspected));
      ctx2.make(
        "p",
        `${assembly.entities.length} recorded members. Highlighting identifies exact membership; rectangles may also enclose nonmembers.`,
        host
      );
      const list = ctx2.make("details", void 0, host);
      ctx2.make("summary", "Exact members", list);
      assembly.entities.forEach((id) => ctx2.nav(list, ctx2.label(id), id));
    }
    if (ctx2.data.diagnostics.ambiguousParents.includes(ctx2.inspected) || ctx2.data.diagnostics.containmentCycles.includes(ctx2.inspected))
      ctx2.make(
        "p",
        "No unique display hierarchy is assumed. All domain relationships are retained.",
        host,
        "issue"
      );
    for (const key of ["measurements", "labels", "features"]) {
      if (!d[key].length) continue;
      ctx2.make("h3", key, host);
      for (const item of d[key]) {
        const dl = ctx2.make("dl", void 0, host);
        ctx2.make("dt", item.name, dl);
        ctx2.make("dd", ctx2.valueText(item.value), dl);
        if (item.definition) ctx2.make("p", item.definition, host, "code");
        ctx2.evidence(host, item.fact);
      }
    }
    const findings = (ctx2.data.reviewItems || []).filter(
      (item) => item.targets.includes(ctx2.inspected)
    );
    if (findings.length) {
      ctx2.make("h3", "Review findings", host);
      for (const item of findings) {
        const row = ctx2.make("details", void 0, host);
        ctx2.make("summary", `${item.id} \xB7 ${item.group} \xB7 ${item.kind}`, row);
        ctx2.make("p", item.scope, row);
        ctx2.make("p", item.explanation, row);
        for (const [name, value] of Object.entries(item.values)) {
          if ((name !== "Known subtotal" || value !== null) && (!Array.isArray(value) || value.length))
            ctx2.make(
              "p",
              `${name}: ${value === null ? "Unknown" : ctx2.valueText(value)}`,
              row
            );
        }
        for (const reference of item.references)
          ctx2.make("p", reference, row, "code");
      }
    }
    if (d.fact) {
      ctx2.make("h3", "Object provenance", host);
      ctx2.evidence(host, d.fact);
    }
    const groups = ctx2.memberships(ctx2.inspected);
    if (groups.length) {
      ctx2.make("h3", "Member of", host);
      for (const [id, a] of groups) ctx2.nav(host, a.name, id);
    }
    if (element.isEdge()) {
      ctx2.make("h3", "Endpoints", host);
      ctx2.nav(
        host,
        `From \xB7 ${ctx2.label(element.data("source"))}`,
        element.data("source")
      );
      ctx2.nav(
        host,
        `To \xB7 ${ctx2.label(element.data("target"))}`,
        element.data("target")
      );
    } else {
      for (const [direction, edges] of [
        [
          "Incoming",
          element.incomers(
            'edge[connector="domain"]'
          )
        ],
        [
          "Outgoing",
          element.outgoers(
            'edge[connector="domain"]'
          )
        ]
      ]) {
        if (!edges.length) continue;
        ctx2.make("h3", `${direction} relationships`, host);
        edges.forEach((edge) => {
          const other = direction === "Incoming" ? edge.source() : edge.target();
          ctx2.nav(
            host,
            `${edge.data("label")} \xB7 ${other.data("label")}${edge.hasClass("hidden") ? " (hidden by view)" : ""}`,
            edge.id()
          );
        });
      }
    }
  }

  // styles.ts
  var styles = [
    {
      selector: "node",
      style: {
        shape: "round-rectangle",
        width: 125,
        height: 68,
        "background-color": "#ffffff",
        "border-color": "#94a6b9",
        "border-width": 1.5,
        label: "data(title)",
        "text-wrap": "wrap",
        "text-max-width": 115,
        "font-size": 14,
        "font-family": "sans-serif",
        color: "#263d50",
        "text-valign": "center",
        "text-halign": "center",
        "z-index-compare": "manual",
        "z-index": 10
      }
    },
    {
      selector: 'node[kind="assembly"]',
      style: {
        width: 170,
        height: 42,
        "text-max-width": 160,
        "background-color": "#e3edf6",
        "border-color": "#347ba7",
        "font-weight": "bold"
      }
    },
    {
      selector: "node.shared",
      style: {
        "background-color": "#e7f6f1",
        "border-color": "#278976",
        "border-width": 3
      }
    },
    {
      selector: "edge",
      style: {
        width: 1.5,
        "curve-style": "bezier",
        "control-point-step-size": 55,
        "line-color": "#8c9dad",
        "target-arrow-color": "#8c9dad",
        "target-arrow-shape": "triangle",
        label: "data(label)",
        "font-size": 12,
        "text-rotation": "autorotate",
        "text-wrap": "ellipsis",
        "text-background-color": "#ffffff",
        "text-background-opacity": 0.9,
        "text-background-padding": 2,
        color: "#536c81",
        "z-index-compare": "manual",
        "z-index": 5
      }
    },
    {
      selector: 'edge[connector="summary"]',
      style: {
        width: 4,
        "line-color": "#65518c",
        "target-arrow-color": "#65518c"
      }
    },
    {
      selector: 'edge[connector="membership"]',
      style: {
        width: 1.5,
        "line-style": "dotted",
        "target-arrow-shape": "none",
        "line-color": "#508b78",
        color: "#36705e"
      }
    },
    {
      selector: ".member",
      style: {
        "border-color": "#176897",
        "border-width": 3,
        "line-color": "#176897",
        "target-arrow-color": "#176897"
      }
    },
    { selector: "node.member", style: { "background-color": "#e5f2ff" } },
    {
      selector: ":selected",
      style: {
        "border-color": "#c48214",
        "border-width": 4,
        "line-color": "#c48214",
        "target-arrow-color": "#c48214"
      }
    },
    { selector: "edge:selected", style: { width: 5 } },
    {
      selector: "node.frame",
      style: {
        shape: "rectangle",
        width: "data(boxWidth)",
        height: "data(boxHeight)",
        "text-max-width": "data(boxWidth)",
        "text-valign": "top-inside",
        "text-margin-y": 9,
        "background-fill": "linear-gradient",
        "background-gradient-stop-colors": "#d9e8f3 #d9e8f3 #f6f9fc #f6f9fc",
        "background-gradient-stop-positions": "data(bandStops)",
        "background-opacity": 0.45,
        "z-index": "data(frameZ)"
      }
    },
    { selector: ".hidden", style: { display: "none" } }
  ];

  // projection.ts
  function projectCollapse(graph, collapsedIds, allowedTypes = null) {
    assemblyOrder(graph);
    const collapsed = new Set(collapsedIds), memberships = parents(graph);
    const nodes = graph.elements.filter((e) => !isEdge(e.data)).map((e) => e.data);
    const originals = graph.elements.map((e) => e.data).filter(isEdge);
    const visibility = /* @__PURE__ */ new Map();
    function visible(id) {
      if (!visibility.has(id))
        visibility.set(
          id,
          !memberships[id].length || memberships[id].some(
            (parent) => visible(parent) && !collapsed.has(parent)
          )
        );
      return visibility.get(id);
    }
    const hidden = new Set(nodes.filter((n) => !visible(n.id)).map((n) => n.id));
    function representatives(id) {
      return visible(id) ? [id] : [...new Set(memberships[id].flatMap(representatives))].sort();
    }
    const edges = [], groups = /* @__PURE__ */ new Map();
    for (const edge of originals) {
      if (allowedTypes && !allowedTypes.has(edge.type)) continue;
      if (visible(edge.source) && visible(edge.target)) {
        edges.push({ ...edge, connector: "domain" });
        continue;
      }
      for (const source of representatives(edge.source))
        for (const target of representatives(edge.target)) {
          if (source === target) continue;
          const key = JSON.stringify([source, target]);
          if (!groups.has(key))
            groups.set(key, { source, target, originals: /* @__PURE__ */ new Map() });
          groups.get(key).originals.set(edge.id, edge);
        }
    }
    for (const [key, group] of groups) {
      const underlying = [...group.originals.values()].sort(
        (a, b) => a.id.localeCompare(b.id)
      );
      edges.push({
        id: "summary:" + key,
        source: group.source,
        target: group.target,
        label: new Set(underlying.map((e) => e.type)).size === 1 ? underlying[0].label : "Relationships",
        connector: "summary",
        originalIds: underlying.map((e) => e.id),
        displayOnly: true
      });
    }
    for (const node of nodes) {
      let walk = function(id, path) {
        for (const owner of memberships[id]) {
          const next = [...path, owner];
          if (visible(owner)) {
            if (collapsed.has(owner)) {
              if (!connections.has(owner)) connections.set(owner, []);
              connections.get(owner).push(next);
            }
          } else walk(owner, next);
        }
      };
      if (hidden.has(node.id)) continue;
      const connections = /* @__PURE__ */ new Map();
      walk(node.id, [node.id]);
      for (const [assembly, paths] of connections)
        edges.push({
          id: "membership:" + JSON.stringify([node.id, assembly]),
          source: node.id,
          target: assembly,
          label: paths.some((p) => p.length === 2) ? "Member of" : "Member within",
          connector: "membership",
          displayOnly: true,
          membershipPaths: paths
        });
    }
    return {
      hiddenIds: [...hidden].sort(),
      memberships,
      edges: edges.sort((a, b) => a.id.localeCompare(b.id))
    };
  }

  // renderer.ts
  function updateCounts(ctx2) {
    ctx2.$("counts").textContent = `${ctx2.visible().nodes().length} / ${ctx2.cy.nodes().length} objects \xB7 ${ctx2.visible().edges().length} displayed connections`;
  }
  function highlight(ctx2) {
    ctx2.cy.elements().removeClass("member");
    const assembly = ctx2.data.assemblies[ctx2.inspected];
    if (!assembly) return;
    const ids = /* @__PURE__ */ new Set([...assembly.entities, ...assembly.relationships]);
    ctx2.cy.elements().forEach((e) => {
      if (ids.has(e.id()) || e.data("connector") === "summary" && e.data("originalIds").some((id) => ids.has(id)))
        e.addClass("member");
    });
  }
  function applyVisibility(ctx2) {
    const start = performance.now();
    ctx2.updating = true;
    ctx2.projection = projectCollapse(ctx2.data, ctx2.collapsed, ctx2.filters);
    const hidden = new Set(ctx2.projection.hiddenIds);
    const edges = new Map(ctx2.projection.edges.map((e) => [e.id, e]));
    ctx2.cy.batch(() => {
      ctx2.cy.edges("[?displayOnly]").remove();
      ctx2.cy.add(
        ctx2.projection.edges.filter((e) => e.displayOnly).map((e) => ({ data: e }))
      );
      ctx2.cy.nodes().forEach((n) => {
        n.toggleClass(
          "hidden",
          hidden.has(n.id()) || Boolean(ctx2.focusIds && !ctx2.focusIds.has(n.id()))
        );
      });
      ctx2.cy.edges().forEach((e) => {
        e.toggleClass(
          "hidden",
          !edges.has(e.id()) || e.source().hasClass("hidden") || e.target().hasClass("hidden") || e.data("connector") === "membership" && !ctx2.showMembership
        );
      });
      ctx2.cy.elements(":selected").unselect();
      const selected = ctx2.cy.getElementById(ctx2.inspected || "");
      if (selected.length && !selected.hasClass("hidden")) selected.select();
      if (ctx2.inspected && !selected.length && !ctx2.data.details[ctx2.inspected])
        ctx2.inspected = null;
    });
    ctx2.updating = false;
    ctx2.syncBoxes();
    ctx2.highlight();
    ctx2.renderSelection();
    ctx2.updateCounts();
    ctx2.metrics.filterMs = performance.now() - start;
  }
  function select(ctx2, id) {
    const start = performance.now(), e = ctx2.cy.getElementById(id);
    if (!e.length) return;
    ctx2.updating = true;
    ctx2.cy.elements(":selected").unselect();
    ctx2.inspected = id;
    if (!e.hasClass("hidden")) e.select();
    ctx2.updating = false;
    ctx2.highlight();
    ctx2.renderSelection();
    ctx2.metrics.selectionMs = performance.now() - start;
  }
  function syncFilters(ctx2) {
    document.querySelectorAll("#filters input").forEach((i) => i.checked = ctx2.filters.has(i.value));
    ctx2.$("member-links").checked = ctx2.showMembership;
  }
  function setupFilters(ctx2) {
    ctx2.$("filters").replaceChildren();
    const types = [
      ...new Set(
        ctx2.data.elements.filter((e) => "source" in e.data).map((e) => e.data.type)
      )
    ];
    ctx2.filters = new Set(types);
    for (const type of types) {
      const l = ctx2.make("label", void 0, ctx2.$("filters")), input = ctx2.make("input", void 0, l);
      input.type = "checkbox";
      input.value = type;
      input.checked = true;
      ctx2.make(
        "span",
        ctx2.data.elements.find((e) => "source" in e.data && e.data.type === type).data.label,
        l
      );
      input.onchange = () => {
        ctx2.pushHistory();
        input.checked ? ctx2.filters.add(type) : ctx2.filters.delete(type);
        ctx2.applyVisibility();
      };
    }
  }
  function loadDataset(ctx2, index) {
    const start = performance.now();
    ctx2.updating = true;
    if (ctx2.cy) ctx2.cy.destroy();
    ctx2.portChoices = /* @__PURE__ */ new Map();
    ctx2.routes = /* @__PURE__ */ new Map();
    ctx2.data = ctx2.datasets[index];
    ctx2.inspected = null;
    ctx2.collapsed = /* @__PURE__ */ new Set();
    ctx2.history = [];
    ctx2.drag = null;
    Object.keys(ctx2.metrics).forEach((key) => ctx2.metrics[key] = 0);
    ctx2.$("dataset").value = String(index);
    ctx2.$("back").disabled = true;
    ctx2.$("search").value = "";
    ctx2.$("results").replaceChildren();
    ctx2.compactPositions = Object.fromEntries(
      Object.keys(ctx2.data.assemblies).map((id) => [
        id,
        { ...ctx2.data.positions[id] }
      ])
    );
    const elements = structuredClone(ctx2.data.elements);
    for (const e of elements)
      if ("source" in e.data) e.data.connector = "domain";
      else e.data.title = e.data.label;
    ctx2.cy = globalThis.cytoscape({
      container: ctx2.$("cy"),
      elements,
      layout: { name: "preset" },
      selectionType: "single",
      minZoom: 0.04,
      maxZoom: 4,
      wheelSensitivity: 0.2,
      style: styles
    });
    for (const [id] of Object.entries(ctx2.data.assemblies))
      ctx2.cy.getElementById(id).data({ boxWidth: 170, boxHeight: 42, bandStops: "0% 85% 85% 100%" });
    ctx2.cy.nodes().forEach((n) => {
      if (ctx2.memberships(n.id()).length > 1) n.addClass("shared");
    });
    ctx2.cy.on("select unselect", "node,edge", () => {
      if (ctx2.updating) return;
      ctx2.inspected = ctx2.cy.$(":selected").first().id() || null;
      ctx2.highlight();
      ctx2.renderSelection();
    });
    ctx2.cy.on("tap", (ev) => {
      if (ev.target === ctx2.cy) {
        ctx2.cy.elements(":selected").unselect();
        ctx2.inspected = null;
        ctx2.highlight();
        ctx2.renderSelection();
      }
    });
    ctx2.cy.on("grab", "node", (ev) => {
      const n = ev.target, a = ctx2.data.assemblies[n.id()];
      ctx2.drag = {
        id: n.id(),
        start: { ...n.position() },
        members: a && !ctx2.collapsed.has(n.id()) ? descendants(ctx2.data, n.id()).map((id) => ctx2.cy.getElementById(id)).filter((m) => m.length && !m.hasClass("hidden")).map((m) => ({ id: m.id(), position: { ...m.position() } })) : []
      };
    });
    ctx2.cy.on("drag", "node", (ev) => {
      if (ctx2.drag?.id !== ev.target.id()) return;
      const pos = ev.target.position(), dx = pos.x - ctx2.drag.start.x, dy = pos.y - ctx2.drag.start.y;
      ctx2.updating = true;
      ctx2.cy.batch(
        () => ctx2.drag.members.forEach((m) => {
          const p = { x: m.position.x + dx, y: m.position.y + dy };
          ctx2.cy.getElementById(m.id).position(p);
          if (ctx2.data.assemblies[m.id]) ctx2.compactPositions[m.id] = { ...p };
        })
      );
      if (ctx2.data.assemblies[ctx2.drag.id])
        ctx2.compactPositions[ctx2.drag.id] = { ...pos };
      ctx2.updating = false;
      ctx2.syncBoxes();
    });
    ctx2.cy.on("free", "node", () => {
      ctx2.drag = null;
      ctx2.syncBoxes();
    });
    ctx2.cy.on("position", "node", (ev) => {
      if (ctx2.syncing || ctx2.updating || ctx2.drag || ctx2.layoutMode) return;
      if (ctx2.data.assemblies[ev.target.id()] && !ev.target.hasClass("frame"))
        ctx2.compactPositions[ev.target.id()] = { ...ev.target.position() };
      ctx2.syncBoxes();
    });
    ctx2.setupFilters();
    ctx2.showMembership = true;
    ctx2.syncFilters();
    ctx2.focusIds = ctx2.data.initialFocus ? /* @__PURE__ */ new Set([
      ctx2.data.initialFocus,
      ...ctx2.data.assemblies[ctx2.data.initialFocus].entities
    ]) : null;
    ctx2.updating = false;
    ctx2.applyVisibility();
    ctx2.fit();
    ctx2.$("notes").replaceChildren();
    ctx2.data.notes.forEach((n) => ctx2.make("p", n, ctx2.$("notes")));
    ctx2.$("diagnostics").replaceChildren();
    const diag = ctx2.data.diagnostics;
    if (diag.ambiguousParents.length || diag.containmentCycles.length) {
      const host = ctx2.make(
        "p",
        `${diag.ambiguousParents.length} object(s) with multiple containment parents; ${diag.containmentCycles.length} in containment cycles. No display parent was chosen.`,
        ctx2.$("diagnostics"),
        "issue"
      );
      for (const id of /* @__PURE__ */ new Set([
        ...diag.ambiguousParents,
        ...diag.containmentCycles
      ]))
        ctx2.nav(host, ctx2.label(id), id);
    }
    ctx2.$("anchors").disabled = !ctx2.data.anchors.length;
    ctx2.$("anchors").checked = false;
    ctx2.selectLinkedObject();
    ctx2.metrics.loadMs = performance.now() - start;
    ctx2.$("timing").textContent = `Loaded in ${ctx2.metrics.loadMs.toFixed(0)} ms \xB7 reference arrangement`;
  }
  async function relayout(ctx2) {
    const start = performance.now();
    ctx2.$("relayout").disabled = true;
    ctx2.layoutMode = true;
    ctx2.syncBoxes();
    const anchors = ctx2.$("anchors").checked ? ctx2.data.anchors.filter((id) => !ctx2.cy.getElementById(id).hasClass("hidden")).map((id) => ({
      nodeId: id,
      position: { ...ctx2.cy.getElementById(id).position() }
    })) : [];
    const options = {
      name: "fcose",
      quality: "proof",
      randomize: false,
      animate: false,
      nodeDimensionsIncludeLabels: true,
      packComponents: false,
      fit: false,
      nodeRepulsion: 6500,
      idealEdgeLength: 130,
      numIter: 1500
    };
    if (anchors.length) {
      options.fixedNodeConstraint = anchors;
      if (ctx2.data.alignment)
        options.alignmentConstraint = {
          vertical: ctx2.data.alignment.vertical.filter(
            (g) => g.every((id) => !ctx2.cy.getElementById(id).hasClass("hidden"))
          )
        };
    }
    try {
      await new Promise((resolve, reject) => {
        try {
          ctx2.visible().layout({ ...options, stop: resolve }).run();
        } catch (e) {
          reject(e);
        }
      });
      for (const id of Object.keys(ctx2.data.assemblies))
        ctx2.compactPositions[id] = { ...ctx2.cy.getElementById(id).position() };
      ctx2.metrics.layoutMs = performance.now() - start;
      ctx2.$("timing").textContent = `fCoSE \xB7 ${ctx2.metrics.layoutMs.toFixed(0)} ms${anchors.length ? " \xB7 fixed anchors" : ""}`;
    } finally {
      ctx2.layoutMode = false;
      ctx2.syncBoxes();
      ctx2.fit();
      ctx2.$("relayout").disabled = false;
    }
  }
  function setMode(ctx2, next) {
    ctx2.mode = next;
    ctx2.$("outlines").classList.toggle("active", next === "outlines");
    ctx2.$("membership").classList.toggle("active", next === "membership");
    ctx2.syncBoxes();
  }

  // app.ts
  var ctx = {};
  ctx.connectionCentre = (...args) => connectionCentre(ctx, ...args);
  ctx.headerEndpoint = (...args) => headerEndpoint(ctx, ...args);
  ctx.endpoint = (...args) => endpoint(ctx, ...args);
  ctx.connectionGeometry = (...args) => connectionGeometry(ctx, ...args);
  ctx.updateConnections = (...args) => updateConnections(ctx, ...args);
  ctx.syncBoxes = (...args) => syncBoxes(ctx, ...args);
  ctx.pushHistory = (...args) => pushHistory(ctx, ...args);
  ctx.changeCollapse = (...args) => changeCollapse(ctx, ...args);
  ctx.fit = (...args) => fit(ctx, ...args);
  ctx.focusOn = (...args) => focusOn(ctx, ...args);
  ctx.reset = (...args) => reset(ctx, ...args);
  ctx.restore = (...args) => restore(ctx, ...args);
  ctx.reveal = (...args) => reveal(ctx, ...args);
  ctx.selectLinkedObject = (...args) => selectLinkedObject(ctx, ...args);
  ctx.valueText = (...args) => valueText(ctx, ...args);
  ctx.evidence = (...args) => evidence(ctx, ...args);
  ctx.nav = (...args) => nav(ctx, ...args);
  ctx.renderSelection = (...args) => renderSelection(ctx, ...args);
  ctx.highlight = (...args) => highlight(ctx, ...args);
  ctx.updateCounts = (...args) => updateCounts(ctx, ...args);
  ctx.applyVisibility = (...args) => applyVisibility(ctx, ...args);
  ctx.select = (id) => select(ctx, id);
  ctx.syncFilters = (...args) => syncFilters(ctx, ...args);
  ctx.setupFilters = (...args) => setupFilters(ctx, ...args);
  ctx.loadDataset = (...args) => loadDataset(ctx, ...args);
  ctx.relayout = (...args) => relayout(ctx, ...args);
  ctx.setMode = (...args) => setMode(ctx, ...args);
  ctx.datasets = JSON.parse(
    document.getElementById("graph-data").textContent
  ).datasets;
  ctx.$ = (id) => document.getElementById(id);
  ctx.make = (tag, text, parent, cls) => {
    const e = document.createElement(tag);
    if (text !== void 0) e.textContent = String(text);
    if (cls) e.className = cls;
    if (parent) parent.append(e);
    return e;
  };
  ctx.HEADER = 36;
  ctx.PAD = 24;
  ctx.labelMeasure = document.createElement("canvas").getContext("2d");
  ctx.cy = void 0;
  ctx.data = void 0;
  ctx.projection = void 0;
  ctx.inspected = null;
  ctx.focusIds = null;
  ctx.history = [];
  ctx.collapsed = /* @__PURE__ */ new Set();
  ctx.filters = /* @__PURE__ */ new Set();
  ctx.mode = "outlines";
  ctx.showMembership = true;
  ctx.fourPorts = true;
  ctx.compactPositions = {};
  ctx.drag = null;
  ctx.syncing = false;
  ctx.updating = false;
  ctx.layoutMode = false;
  ctx.portChoices = /* @__PURE__ */ new Map();
  ctx.routes = /* @__PURE__ */ new Map();
  ctx.metrics = { loadMs: 0, layoutMs: 0, selectionMs: 0, filterMs: 0 };
  ctx.label = (id) => ctx.data.details[id]?.name || ctx.cy.getElementById(id).data("label") || id;
  ctx.memberships = (id) => Object.entries(ctx.data.assemblies).filter(
    ([, a]) => a.entities.includes(id) || a.relationships.includes(id)
  );
  ctx.visible = () => ctx.cy.elements().filter((e) => !e.hasClass("hidden"));
  ctx.snapshot = () => ({
    focus: ctx.focusIds ? [...ctx.focusIds] : null,
    filters: [...ctx.filters],
    collapsed: [...ctx.collapsed],
    showMembership: ctx.showMembership
  });
  ctx.routingStyle = "curve-style control-point-distances control-point-weights control-point-step-size edge-distances loop-direction loop-sweep text-rotation";
  ctx.datasets.forEach((d, i) => {
    const o = ctx.make("option", d.name, ctx.$("dataset"));
    o.value = String(i);
  });
  ctx.$("dataset").onchange = () => ctx.loadDataset(Number(ctx.$("dataset").value));
  ctx.$("membership").onclick = () => ctx.setMode("membership");
  ctx.$("outlines").onclick = () => ctx.setMode("outlines");
  ctx.$("four-port-routing").onchange = () => {
    ctx.fourPorts = ctx.$("four-port-routing").checked;
    ctx.syncBoxes();
  };
  ctx.$("fit").onclick = ctx.fit;
  ctx.$("restore").onclick = ctx.restore;
  ctx.$("relayout").onclick = ctx.relayout;
  ctx.$("focus").onclick = () => {
    if (ctx.inspected) ctx.focusOn(ctx.inspected);
  };
  ctx.$("reset").onclick = ctx.reset;
  ctx.$("collapse-all").onclick = () => ctx.changeCollapse(Object.keys(ctx.data.assemblies), true);
  ctx.$("expand-all").onclick = () => ctx.changeCollapse(Object.keys(ctx.data.assemblies), false);
  ctx.$("member-links").onchange = () => {
    ctx.pushHistory();
    ctx.showMembership = ctx.$("member-links").checked;
    ctx.applyVisibility();
  };
  ctx.$("back").onclick = () => {
    const previous = ctx.history.pop();
    if (!previous) return;
    ctx.focusIds = previous.focus ? new Set(previous.focus) : null;
    ctx.filters = new Set(previous.filters);
    ctx.collapsed = new Set(previous.collapsed);
    ctx.showMembership = previous.showMembership;
    ctx.syncFilters();
    ctx.applyVisibility();
    ctx.fit();
    ctx.$("back").disabled = !ctx.history.length;
  };
  ctx.$("clear").onclick = () => {
    ctx.cy.elements(":selected").unselect();
    ctx.inspected = null;
    ctx.highlight();
    ctx.renderSelection();
  };
  ctx.$("search").oninput = () => {
    const q = ctx.$("search").value.trim().toLowerCase();
    ctx.$("results").replaceChildren();
    if (!q) return;
    ctx.cy.nodes().filter(
      (n) => [n.data("label"), n.data("code"), n.id()].some(
        (v) => (v || "").toLowerCase().includes(q)
      )
    ).slice(0, 8).forEach((n) => {
      const button = ctx.make(
        "button",
        `${n.data("label")} \xB7 ${n.data("code")}`,
        ctx.$("results")
      );
      button.onclick = () => {
        ctx.select(n.id());
        if (!n.hasClass("hidden")) {
          const bb = n.renderedBoundingBox();
          if (bb.x1 < 0 || bb.y1 < 0 || bb.x2 > ctx.cy.width() || bb.y2 > ctx.cy.height())
            ctx.cy.center(n);
        }
        ctx.$("results").replaceChildren();
      };
    });
  };
  ctx.$("search").onkeydown = (e) => {
    if (e.key === "Enter") ctx.$("results").querySelector("button")?.click();
    if (e.key === "Escape") ctx.$("results").replaceChildren();
  };
  new ResizeObserver(() => {
    if (ctx.cy) ctx.cy.resize();
  }).observe(ctx.$("stage"));
  window.spike = {
    get cy() {
      return ctx.cy;
    },
    get data() {
      return ctx.data;
    },
    get selected() {
      return ctx.inspected;
    },
    get collapsed() {
      return [...ctx.collapsed];
    },
    get projection() {
      return ctx.projection;
    },
    get metrics() {
      return { ...ctx.metrics };
    },
    get routes() {
      return Object.fromEntries(ctx.routes);
    },
    get visibleIds() {
      return ctx.visible().map((e) => e.id());
    },
    loadDataset: ctx.loadDataset,
    select: ctx.select,
    focusOn: ctx.focusOn,
    reset: ctx.reset,
    restore: ctx.restore,
    relayout: ctx.relayout,
    setMode: ctx.setMode,
    syncBoxes: ctx.syncBoxes,
    changeCollapse: ctx.changeCollapse
  };
  window.graphReview = window.spike;
  window.addEventListener("hashchange", ctx.selectLinkedObject);
  ctx.loadDataset(0);
})();
