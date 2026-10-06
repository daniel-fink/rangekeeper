(() => {
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

  // presentation.ts
  function initialPresentation(graph) {
    if (!graph.savedLayout) return null;
    return {
      rectangles: structuredClone(graph.savedLayout.geometry.rectangles),
      display: structuredClone(graph.savedLayout.geometry.rectangles),
      adjusted: false,
      visibility: "",
      conflicts: []
    };
  }
  function translate(state, originals, dx, dy) {
    for (const [id, r] of Object.entries(originals))
      state.rectangles[id] = { ...r, x: r.x + dx, y: r.y + dy };
    if (dx || dy) state.adjusted = true;
  }
  function movingRectangles(graph, state, id) {
    return Object.fromEntries(
      [id, ...descendants(graph, id)].map((i) => [i, { ...state.rectangles[i] }])
    );
  }
  function resizePresentation(graph, state, visible, collapsed, dragging, showSpacing = false) {
    const signature = JSON.stringify([
      [...visible].sort(),
      [...collapsed].sort()
    ]);
    if (state.visibility && state.visibility !== signature) state.adjusted = true;
    state.visibility = signature;
    const boxes = structuredClone(state.rectangles), p = graph.savedLayout.problem;
    for (const id of assemblyOrder(graph)) {
      if (!visible.has(id)) continue;
      const members = graph.assemblies[id].entities.filter((i) => visible.has(i));
      if (collapsed.has(id) || !members.length) {
        boxes[id] = { ...boxes[id], height: p.header };
      } else if (state.adjusted && id !== dragging) {
        const rs = members.map((i) => boxes[i]);
        const left = Math.min(...rs.map((r) => r.x)), top = Math.min(...rs.map((r) => r.y));
        const right = Math.max(...rs.map((r) => r.x + r.width)), bottom = Math.max(...rs.map((r) => r.y + r.height));
        const min = p.assemblies?.find((a) => a.id === id)?.min_width ?? 180;
        const width = Math.max(min, right - left + 2 * p.padding);
        boxes[id] = {
          x: (left + right - width) / 2,
          y: top - p.padding - p.header,
          width,
          height: bottom - top + 2 * p.padding + p.header
        };
        state.rectangles[id] = { ...boxes[id] };
      }
    }
    state.display = boxes;
    state.conflicts = visibleConflicts(graph, boxes, visible, showSpacing);
  }
  var EPS = 0.01;
  function separated(a, b, gap = 0) {
    return a.x + a.width + gap <= b.x + EPS || b.x + b.width + gap <= a.x + EPS || a.y + a.height + gap <= b.y + EPS || b.y + b.height + gap <= a.y + EPS;
  }
  function visibleConflicts(graph, boxes, visible, showSpacing = false) {
    const groups = Object.keys(graph.assemblies).filter((i) => visible.has(i)).sort();
    const nodes = [...visible].filter((i) => !graph.assemblies[i]).sort();
    const result = [], gap = graph.savedLayout.problem.gap ?? 0, header = graph.savedLayout.problem.header;
    for (const outer of groups) {
      const members = new Set(descendants(graph, outer)), r = boxes[outer];
      for (const n of nodes) {
        if (members.has(n)) continue;
        if (!separated(boxes[n], r))
          result.push({
            code: "exclusion",
            objects: [n, outer],
            message: "Nonmember overlaps assembly"
          });
        else if (showSpacing && !separated(boxes[n], r, gap))
          result.push({
            code: "clearance",
            objects: [n, outer],
            message: `Spacing advisory: less than ${gap} layout units between nonmember and assembly`
          });
      }
      for (const inner of groups) {
        if (inner === outer || members.has(inner)) continue;
        const c = boxes[inner];
        if (r.x <= c.x + EPS && r.y <= c.y + EPS && c.x + c.width <= r.x + r.width + EPS && c.y + c.height <= r.y + r.height + EPS)
          result.push({
            code: "exclusion",
            objects: [inner, outer],
            message: "Unrelated assembly fully enclosed"
          });
      }
    }
    const obstacles = [
      ...nodes.map((i) => [i, boxes[i]]),
      ...groups.map((i) => [i, { ...boxes[i], height: header }])
    ].sort((a, b) => a[0].localeCompare(b[0]));
    for (let i = 0; i < obstacles.length; i++)
      for (let j = i + 1; j < obstacles.length; j++) {
        const [a, ra] = obstacles[i], [b, rb] = obstacles[j];
        if (!separated(ra, rb))
          result.push({
            code: "collision",
            objects: [a, b],
            message: "Node or assembly header overlaps another footprint"
          });
        else if (showSpacing && !separated(ra, rb, gap))
          result.push({
            code: "clearance",
            objects: [a, b],
            message: `Spacing advisory: less than ${gap} layout units between node/header footprints`
          });
      }
    return result.sort(
      (a, b) => Number(a.code === "clearance") - Number(b.code === "clearance")
    );
  }

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

  // geometry.ts
  function connectionCentre(viewer2, node) {
    const p = node.position();
    return {
      x: p.x,
      y: p.y - (node.hasClass("frame") ? node.height() / 2 - viewer2.HEADER / 2 : 0)
    };
  }
  function headerEndpoint(viewer2, node, other) {
    const p = viewer2.connectionCentre(node), q = viewer2.connectionCentre(other);
    const dx = q.x - p.x, dy = q.y - p.y;
    const scale = Math.max(
      Math.abs(dx) / (node.width() / 2),
      Math.abs(dy) / (viewer2.HEADER / 2)
    );
    return scale ? { x: p.x + dx / scale, y: p.y + dy / scale } : { x: p.x, y: p.y + viewer2.HEADER / 2 };
  }
  function endpoint(viewer2, edge, source) {
    const node = source ? edge.source() : edge.target();
    const other = source ? edge.target() : edge.source();
    const p = node.position();
    if (node.hasClass("frame")) {
      const q = viewer2.headerEndpoint(node, other);
      return `${q.x - p.x}px ${q.y - p.y}px`;
    }
    if (other.hasClass("frame")) {
      const q = viewer2.headerEndpoint(other, node);
      return `${Math.atan2(q.y - p.y, q.x - p.x) * 180 / Math.PI + 90}deg`;
    }
    return "outside-to-node";
  }
  function connectionGeometry(viewer2, n) {
    return {
      ...viewer2.connectionCentre(n),
      w: n.width(),
      h: n.hasClass("frame") ? viewer2.HEADER : n.height(),
      nodePosition: { ...n.position() }
    };
  }
  function updateConnections(viewer2) {
    const eligible = viewer2.cy.edges().filter((e) => viewer2.fourPorts && !viewer2.layoutMode && !e.hasClass("hidden"));
    const references = /* @__PURE__ */ new Map(), pairs = /* @__PURE__ */ new Map();
    const finite = (p) => p && Number.isFinite(p.x) && Number.isFinite(p.y);
    viewer2.routes = /* @__PURE__ */ new Map();
    const nativePairs = eligible.filter(
      (e) => !e.source().hasClass("frame") && !e.target().hasClass("frame") && e.source().id() !== e.target().id() && Math.hypot(
        e.source().position().x - e.target().position().x,
        e.source().position().y - e.target().position().y
      ) > 1e-6
    );
    viewer2.cy.batch(
      () => nativePairs.forEach((e) => {
        e.removeStyle(viewer2.routingStyle);
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
    viewer2.cy.batch(
      () => viewer2.cy.edges().forEach((e) => {
        const active = eligible.has(e);
        e.toggleClass("four-port", active);
        if (!active) {
          e.removeStyle(viewer2.routingStyle);
          e.style({
            "source-endpoint": viewer2.endpoint(e, true),
            "target-endpoint": viewer2.endpoint(e, false)
          });
          return;
        }
        const source = e.source(), target = e.target();
        const pair = pairs.get(JSON.stringify([source.id(), target.id()].sort()));
        const result = route({
          source: viewer2.connectionGeometry(source),
          target: viewer2.connectionGeometry(target),
          sourceId: source.id(),
          targetId: target.id(),
          ...references.get(e.id()),
          previous: viewer2.portChoices.get(e.id()),
          lane: pair.indexOf(e.id()),
          laneCount: pair.length
        });
        viewer2.portChoices.set(e.id(), {
          sourcePort: result.sourcePort,
          targetPort: result.targetPort
        });
        viewer2.routes.set(e.id(), result);
        e.style(
          style(result, source.position(), target.position())
        );
      })
    );
    const labels = viewer2.cy.edges().filter((e) => !e.hasClass("hidden")).map((e) => {
      const geometry = {
        source: e.sourceEndpoint(),
        target: e.targetEndpoint(),
        controls: e.controlPoints() || []
      };
      const arc = sampleCurve(geometry), width = labelWidth(geometry, arc);
      viewer2.labelMeasure.font = `${e.style("font-style")} ${e.style("font-weight")} ${e.numericStyle("font-size")}px ${e.style("font-family")}`;
      let text = e.style("label");
      if (e.style("text-transform") === "uppercase") text = text.toUpperCase();
      if (e.style("text-transform") === "lowercase") text = text.toLowerCase();
      const fitted = fitLabel(
        text,
        Math.max(1, width),
        (text2) => Math.ceil(viewer2.labelMeasure.measureText(text2).width)
      );
      const style2 = {
        "text-max-width": Math.max(1, width),
        "text-opacity": width >= 32 ? 1 : 0
      };
      if (e.hasClass("four-port"))
        style2["text-rotation"] = `${labelAngle(geometry, fitted.width + 2 * e.numericStyle("text-background-padding"), arc)}rad`;
      return [e, style2];
    });
    viewer2.cy.batch(() => labels.forEach(([e, style2]) => e.style(style2)));
  }
  function syncBoxes(viewer2) {
    if (viewer2.syncing || !viewer2.cy) return;
    viewer2.syncing = true;
    if (viewer2.data.savedLayout) {
      const saved = viewer2.data.savedLayout, state = viewer2.presentation;
      const visible = new Set(
        viewer2.visible().nodes().map((n) => n.id())
      );
      resizePresentation(
        viewer2.data,
        state,
        visible,
        viewer2.collapsed,
        viewer2.drag?.id,
        viewer2.showSpacingAdvisories
      );
      for (const n of viewer2.cy.nodes()) {
        const r = state.display[n.id()], assembly = viewer2.data.assemblies[n.id()];
        const frame = Boolean(
          assembly && !viewer2.collapsed.has(n.id()) && assembly.entities.some((i) => visible.has(i)) && visible.has(n.id())
        );
        const stop = Math.min(100, saved.problem.header / r.height * 100);
        n.toggleClass("frame", frame);
        n.data({
          savedWidth: r.width - 3,
          savedHeight: r.height - 3,
          savedTextWidth: r.width - 16,
          boxWidth: r.width - 3,
          boxHeight: r.height - 3,
          bandStops: `0% ${stop}% ${stop}% 100%`,
          frameZ: Math.min(4, revealPath(viewer2.data, n.id()).length),
          title: assembly ? `${viewer2.collapsed.has(n.id()) ? "\u25B8" : "\u25BE"} ${assembly.name}` : n.data("label")
        });
        n.position({ x: r.x + r.width / 2, y: r.y + r.height / 2 });
      }
      renderConflicts(viewer2);
      viewer2.updateConnections();
      viewer2.syncing = false;
      return;
    }
    {
      for (const id of assemblyOrder(viewer2.data)) {
        const assembly = viewer2.data.assemblies[id];
        const node = viewer2.cy.getElementById(id);
        node.data("frameZ", Math.min(4, revealPath(viewer2.data, id).length));
        node.data(
          "title",
          `${viewer2.collapsed.has(id) ? "\u25B8" : "\u25BE"} ${assembly.name}`
        );
        const members = viewer2.cy.collection(
          assembly.entities.map((mid) => viewer2.cy.getElementById(mid)[0]).filter(
            (n) => n && !n.hasClass("hidden")
          )
        );
        const frame = viewer2.mode === "outlines" && !viewer2.layoutMode && !viewer2.collapsed.has(id) && !node.hasClass("hidden") && members.length > 0;
        node.toggleClass("frame", frame);
        if (frame) {
          if (viewer2.drag?.id === id) continue;
          const bb = members.boundingBox({
            includeLabels: true,
            includeOverlays: false,
            useCache: false
          });
          const w = Math.max(180, bb.w + 2 * viewer2.PAD), h = bb.h + 2 * viewer2.PAD + viewer2.HEADER;
          const stop = viewer2.HEADER / h * 100;
          node.data({
            boxWidth: w,
            boxHeight: h,
            bandStops: `0% ${stop}% ${stop}% 100%`
          });
          node.position({
            x: (bb.x1 + bb.x2) / 2,
            y: (bb.y1 + bb.y2 - viewer2.HEADER) / 2
          });
        } else if (viewer2.compactPositions[id] && viewer2.drag?.id !== id) {
          node.position({ ...viewer2.compactPositions[id] });
        }
      }
    }
    viewer2.updateConnections();
    viewer2.syncing = false;
  }
  function renderConflicts(viewer2) {
    const state = viewer2.presentation, conflicts = state.conflicts;
    const errors = conflicts.filter((c) => c.code !== "clearance"), advisories = conflicts.filter((c) => c.code === "clearance");
    const affected = new Set(errors.flatMap((c) => c.objects));
    const nearby = new Set(advisories.flatMap((c) => c.objects));
    viewer2.cy.nodes().forEach((n) => {
      n.toggleClass("presentation-conflict", affected.has(n.id()));
      n.toggleClass(
        "presentation-advisory",
        nearby.has(n.id()) && !affected.has(n.id())
      );
    });
    const host = viewer2.$("presentation-conflicts");
    if (!host) return;
    const signature = JSON.stringify([
      state.adjusted,
      conflicts,
      viewer2.showSpacingAdvisories
    ]);
    if (host.dataset.signature === signature) return;
    host.dataset.signature = signature;
    host.replaceChildren();
    viewer2.make(
      "p",
      `${state.adjusted ? "Adjusted presentation" : "Saved starting layout"} \xB7 ${errors.length} visible enclosure/collision conflict(s).${viewer2.showSpacingAdvisories ? ` ${advisories.length} spacing ${advisories.length === 1 ? "advisory" : "advisories"} (amber).` : ""}`,
      host
    );
    if (state.adjusted)
      viewer2.make(
        "p",
        "Grid, ordering and compactness have not been revalidated. Changes last until reload or dataset switch.",
        host
      );
    if (conflicts.length) {
      const details = viewer2.make("details", void 0, host);
      viewer2.make("summary", "Inspect conflicts and advisories", details);
      for (const c of conflicts.slice(0, 50)) {
        const row = viewer2.make("p", c.message + ": ", details);
        for (const id of c.objects) {
          const b = viewer2.make("button", viewer2.label(id), row);
          b.onclick = () => {
            viewer2.select(id);
            viewer2.cy.center(viewer2.cy.getElementById(id));
          };
        }
      }
      if (conflicts.length > 50)
        viewer2.make("p", `Showing 50 of ${conflicts.length} findings.`, details);
    }
  }

  // document.ts
  var isEdge = (data) => "source" in data;

  // navigation.ts
  function remember(viewer2) {
    viewer2.history.push(viewer2.snapshot());
    viewer2.$("back").disabled = false;
  }
  function collapse(viewer2, ids, value) {
    viewer2.remember();
    for (const id of ids)
      value ? viewer2.collapsed.add(id) : viewer2.collapsed.delete(id);
    viewer2.applyVisibility();
  }
  function fit(viewer2) {
    if (viewer2.visible().length) viewer2.cy.fit(viewer2.visible(), 55);
  }
  function focus(viewer2, id) {
    viewer2.remember();
    const assembly = viewer2.data.assemblies[id];
    if (assembly) viewer2.focusIds = /* @__PURE__ */ new Set([id, ...descendants(viewer2.data, id)]);
    else {
      const element = viewer2.cy.getElementById(id);
      viewer2.focusIds = /* @__PURE__ */ new Set([id]);
      if (element.isEdge()) {
        viewer2.focusIds.add(element.data("source"));
        viewer2.focusIds.add(element.data("target"));
      }
      for (const item of viewer2.data.elements) {
        const edge = item.data;
        if (isEdge(edge) && (edge.source === id || edge.target === id)) {
          viewer2.focusIds.add(edge.source);
          viewer2.focusIds.add(edge.target);
        }
      }
      for (const [aid] of viewer2.memberships(id)) viewer2.focusIds.add(aid);
    }
    for (const nid of [...viewer2.focusIds])
      for (const aid of viewer2.projection.memberships[nid] || [])
        if (viewer2.collapsed.has(aid)) viewer2.focusIds.add(aid);
    viewer2.applyVisibility();
    viewer2.fit();
  }
  function reset(viewer2) {
    viewer2.remember();
    viewer2.focusIds = null;
    viewer2.applyVisibility();
    viewer2.fit();
  }
  function restore(viewer2) {
    if (viewer2.data.savedLayout) {
      if (viewer2.dragFrame != null) cancelAnimationFrame(viewer2.dragFrame);
      viewer2.dragFrame = null;
      viewer2.drag = null;
      viewer2.presentation = initialPresentation(viewer2.data);
      viewer2.collapsed.clear();
      viewer2.focusIds = null;
      viewer2.applyVisibility();
      viewer2.$("timing").textContent = "Checked saved layout restored";
      return;
    }
    viewer2.updating = true;
    viewer2.cy.batch(
      () => viewer2.cy.nodes().forEach((n) => {
        n.position({ ...viewer2.data.positions[n.id()] });
      })
    );
    for (const id of Object.keys(viewer2.data.assemblies))
      viewer2.compactPositions[id] = { ...viewer2.data.positions[id] };
    viewer2.updating = false;
    viewer2.syncBoxes();
    viewer2.$("timing").textContent = "Reference arrangement restored";
  }
  function reveal(viewer2, id, assemblyId) {
    viewer2.remember();
    if (assemblyId) {
      for (const ancestor of revealPath(viewer2.data, assemblyId))
        viewer2.collapsed.delete(ancestor);
      viewer2.collapsed.delete(assemblyId);
    }
    if (viewer2.focusIds) {
      viewer2.focusIds.add(id);
      if (assemblyId) {
        viewer2.focusIds.add(assemblyId);
        for (const mid of viewer2.data.assemblies[assemblyId].entities)
          viewer2.focusIds.add(mid);
      }
    }
    viewer2.applyVisibility();
    viewer2.select(id);
    viewer2.fit();
  }
  function selectLinkedObject(viewer2) {
    if (!location.hash) return;
    const params = new URLSearchParams(location.hash.slice(1)), ids = params.getAll("select");
    if ([...params.keys()].some((k) => k !== "select") || ids.length !== 1 || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
      ids[0]
    ) || !viewer2.data.details[ids[0]]) {
      viewer2.make(
        "p",
        "This review link does not identify an object in the current graph.",
        viewer2.$("diagnostics"),
        "issue"
      );
      return;
    }
    viewer2.select(ids[0]);
  }

  // inspector.ts
  function valueText(viewer2, value) {
    if (value === null) return "Unknown / not supplied";
    if (value && typeof value === "object" && "units" in value)
      return `${viewer2.valueText(value.value)} ${value.units}`.trim();
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  }
  function decisionRecord(claim) {
    if (claim?.method?.code !== "reviewed-decision") return null;
    try {
      const value = typeof claim.value === "string" ? JSON.parse(claim.value) : claim.value;
      return value && typeof value.id === "string" && typeof value.text === "string" ? value : null;
    } catch {
      return null;
    }
  }
  function renderDecision(viewer2, claim, host) {
    const decision = decisionRecord(claim);
    if (!decision) return false;
    viewer2.make(
      "h4",
      `${decision.id} \xB7 ${decision.status || "Status not recorded"}`,
      host
    );
    viewer2.make("p", decision.text, host);
    viewer2.make(
      "p",
      `${decision.source || "Attribution not recorded"} \xB7 ${decision.date || "Date not recorded"}`,
      host
    );
    if (viewer2.data.reviewUrl === "review.html") {
      const link = document.createElement("a");
      link.textContent = "Open decision and mapping review";
      link.href = "review.html#decision-" + encodeURIComponent(decision.id);
      link.target = "_blank";
      link.rel = "noopener";
      host.append(link);
    }
    return true;
  }
  function evidence(viewer2, parent, fact) {
    if (!fact) {
      viewer2.make("p", "No Fact attached to this item.", parent, "code");
      return;
    }
    const box = viewer2.make("details", void 0, parent);
    viewer2.make("summary", `Evidence \xB7 ${fact.reconciliation || fact.status}`, box);
    if (fact.reconciliation)
      viewer2.make(
        "p",
        `Selected claim is ${fact.reconciliation}. Other claims are retained.`,
        box,
        "issue"
      );
    const pending = [...fact.claims], seenDecisions = /* @__PURE__ */ new Set(), seenClaims = /* @__PURE__ */ new Set();
    const decisions = [];
    while (pending.length) {
      const id = pending.pop();
      if (seenClaims.has(id)) continue;
      seenClaims.add(id);
      const claim = viewer2.data.claims[id];
      if (!claim) continue;
      const record = decisionRecord(claim);
      if (record && !seenDecisions.has(record.id)) {
        seenDecisions.add(record.id);
        decisions.push(claim);
      }
      for (const source of claim.sources)
        if (source.claim) pending.push(source.claim);
    }
    if (decisions.length) {
      const list = viewer2.make("details", void 0, box);
      viewer2.make("summary", `Reviewed decisions \xB7 ${decisions.length}`, list);
      for (const claim of decisions) renderDecision(viewer2, claim, list);
    }
    const visited = /* @__PURE__ */ new Set();
    const appendClaim = (id, host, depth) => {
      if (visited.has(id)) {
        viewer2.make("p", `Previously shown claim ${id}`, host, "code");
        return;
      }
      visited.add(id);
      const c = viewer2.data.claims[id];
      if (!c) return;
      const item = viewer2.make("details", void 0, host);
      viewer2.make(
        "summary",
        `${c.kind}${fact.selected === id ? " \xB7 selected" : ""}`,
        item
      );
      if (!renderDecision(viewer2, c, item))
        viewer2.make("pre", JSON.stringify(c.value, null, 2), item);
      if (c.method) viewer2.make("pre", JSON.stringify(c.method, null, 2), item);
      for (const source of c.sources) {
        if (source.claim) {
          if (depth < 8) appendClaim(source.claim, item, depth + 1);
          else
            viewer2.make(
              "p",
              "Further evidence available in the embedded view data.",
              item
            );
        } else {
          viewer2.make("p", source.name, item);
          viewer2.make(
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
  function nav(viewer2, parent, text, id) {
    const b = viewer2.make("button", text, parent, "nav");
    b.dataset.target = id;
    b.onclick = () => viewer2.select(id, true);
    return b;
  }
  function renderSelection(viewer2) {
    const host = viewer2.$("selection");
    host.replaceChildren();
    viewer2.$("focus").disabled = !viewer2.inspected;
    if (!viewer2.inspected) {
      viewer2.make(
        "p",
        "Search for or select any object or connection. Focus and expand only when you choose.",
        host,
        "empty"
      );
      return;
    }
    const element = viewer2.cy.getElementById(viewer2.inspected), d = viewer2.data.details[viewer2.inspected];
    if (!d && element.length) {
      const edge = element.data();
      viewer2.make("h2", edge.label, host);
      viewer2.make(
        "p",
        edge.connector === "summary" ? "Collapsed relationship summary. This line represents hidden detail; it is not a new domain relationship." : "Recorded Assembly membership, shown as a display connector.",
        host
      );
      viewer2.nav(host, `From \xB7 ${viewer2.label(edge.source)}`, edge.source);
      viewer2.nav(host, `To \xB7 ${viewer2.label(edge.target)}`, edge.target);
      if (edge.membershipPaths?.some((path) => path.length > 2)) {
        viewer2.make("h3", "Membership paths", host);
        for (const path of edge.membershipPaths)
          viewer2.make("p", path.map(viewer2.label).join(" \u2192 "), host);
      }
      if (edge.originalIds) {
        viewer2.make("h3", "Original relationships", host);
        for (const id of edge.originalIds) {
          const original = viewer2.cy.getElementById(id).data();
          viewer2.nav(
            host,
            `${viewer2.label(original.source)} \u2192 ${original.label} \u2192 ${viewer2.label(original.target)}`,
            id
          );
          viewer2.evidence(host, viewer2.data.details[id].fact);
        }
      }
      return;
    }
    if (!d) return;
    viewer2.make("h2", element.data("label"), host);
    viewer2.make(
      "span",
      element.isEdge() ? "Relationship" : viewer2.data.assemblies[viewer2.inspected] ? "Assembly" : "Entity",
      host,
      "tag"
    );
    if (d.classification?.name !== "Assembly")
      viewer2.make("span", d.classification?.name || "Unclassified", host, "tag");
    viewer2.make("p", element.data("code") || viewer2.inspected, host, "code");
    if (element.hasClass("hidden")) {
      viewer2.make(
        "p",
        "Hidden in the current view. Inspection does not expand Assemblies.",
        host,
        "issue"
      );
      if (element.isNode()) {
        const containers = viewer2.memberships(viewer2.inspected).filter(
          ([id]) => viewer2.collapsed.has(id) || viewer2.projection.hiddenIds.includes(id)
        );
        if (containers.length)
          for (const [id, a] of containers) {
            const b = viewer2.make("button", `Reveal in ${a.name}`, host, "nav");
            b.onclick = () => viewer2.reveal(viewer2.inspected, id);
          }
        else {
          const b = viewer2.make("button", "Reveal in view", host, "nav");
          b.onclick = () => viewer2.reveal(viewer2.inspected);
        }
      }
    }
    const assembly = viewer2.data.assemblies[viewer2.inspected];
    if (assembly) {
      const b = viewer2.make(
        "button",
        viewer2.collapsed.has(viewer2.inspected) ? "Expand Assembly" : "Collapse Assembly",
        host,
        "nav"
      );
      b.id = "toggle-collapse";
      b.onclick = () => viewer2.collapse([viewer2.inspected], !viewer2.collapsed.has(viewer2.inspected));
      viewer2.make(
        "p",
        `${assembly.entities.length} recorded members. ${viewer2.data.savedLayout ? "Boxes fit visible members and resize as you arrange or change scope. Highlighting identifies direct membership; red outlines flag presentation conflicts." : "Highlighting identifies exact membership; rectangles may also enclose nonmembers."}`,
        host
      );
      const list = viewer2.make("details", void 0, host);
      viewer2.make("summary", "Exact members", list);
      assembly.entities.forEach((id) => viewer2.nav(list, viewer2.label(id), id));
    }
    if (viewer2.data.diagnostics.ambiguousParents.includes(viewer2.inspected) || viewer2.data.diagnostics.containmentCycles.includes(viewer2.inspected))
      viewer2.make(
        "p",
        "No unique display hierarchy is assumed. All domain relationships are retained.",
        host,
        "issue"
      );
    for (const key of ["measurements", "labels", "features", "flows"]) {
      if (!d[key]?.length) continue;
      viewer2.make("h3", key, host);
      for (const item of d[key]) {
        const dl = viewer2.make("dl", void 0, host);
        viewer2.make("dt", item.name, dl);
        viewer2.make("dd", viewer2.valueText(item.value), dl);
        if (item.definition) viewer2.make("p", item.definition, host, "code");
        viewer2.evidence(host, item.fact);
      }
    }
    const findings = (viewer2.data.reviewItems || []).filter(
      (item) => item.targets.includes(viewer2.inspected)
    );
    if (findings.length) {
      viewer2.make("h3", "Review findings", host);
      for (const item of findings) {
        const row = viewer2.make("details", void 0, host);
        viewer2.make("summary", `${item.id} \xB7 ${item.group} \xB7 ${item.kind}`, row);
        viewer2.make("p", item.scope, row);
        viewer2.make("p", item.explanation, row);
        for (const [name, value] of Object.entries(item.values)) {
          if ((name !== "Known subtotal" || value !== null) && (!Array.isArray(value) || value.length))
            viewer2.make(
              "p",
              `${name}: ${value === null ? "Unknown" : viewer2.valueText(value)}`,
              row
            );
        }
        for (const reference of item.references)
          viewer2.make("p", reference, row, "code");
      }
    }
    if (d.fact) {
      viewer2.make("h3", "Object provenance", host);
      viewer2.evidence(host, d.fact);
    }
    const groups = viewer2.memberships(viewer2.inspected);
    if (groups.length) {
      viewer2.make("h3", "Member of", host);
      for (const [id, a] of groups) viewer2.nav(host, a.name, id);
    }
    if (element.isEdge()) {
      viewer2.make("h3", "Endpoints", host);
      viewer2.nav(
        host,
        `From \xB7 ${viewer2.label(element.data("source"))}`,
        element.data("source")
      );
      viewer2.nav(
        host,
        `To \xB7 ${viewer2.label(element.data("target"))}`,
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
        viewer2.make("h3", `${direction} relationships`, host);
        edges.forEach((edge) => {
          const other = direction === "Incoming" ? edge.source() : edge.target();
          viewer2.nav(
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
    {
      selector: "node.saved",
      style: {
        width: "data(savedWidth)",
        height: "data(savedHeight)",
        padding: 0,
        "border-width": 1,
        "font-size": 12,
        "font-family": "monospace",
        "text-wrap": "ellipsis",
        "text-max-width": "data(savedTextWidth)",
        "text-outline-width": 0
      }
    },
    {
      selector: "node.presentation-conflict",
      style: { "border-color": "#c83232", color: "#a12222" }
    },
    {
      selector: "node.presentation-advisory",
      style: { "border-color": "#b7791f", color: "#946015" }
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
  function updateCounts(viewer2) {
    viewer2.$("counts").textContent = `${viewer2.visible().nodes().length} / ${viewer2.cy.nodes().length} objects \xB7 ${viewer2.visible().edges().length} displayed connections`;
  }
  function highlight(viewer2) {
    viewer2.cy.elements().removeClass("member");
    const assembly = viewer2.data.assemblies[viewer2.inspected];
    if (!assembly) return;
    const ids = /* @__PURE__ */ new Set([...assembly.entities, ...assembly.relationships]);
    viewer2.cy.elements().forEach((e) => {
      if (ids.has(e.id()) || e.data("connector") === "summary" && e.data("originalIds").some((id) => ids.has(id)))
        e.addClass("member");
    });
  }
  function applyVisibility(viewer2) {
    const start = performance.now();
    viewer2.updating = true;
    viewer2.projection = projectCollapse(viewer2.data, viewer2.collapsed, viewer2.filters);
    const hidden = new Set(viewer2.projection.hiddenIds);
    const edges = new Map(viewer2.projection.edges.map((e) => [e.id, e]));
    viewer2.cy.batch(() => {
      viewer2.cy.edges("[?displayOnly]").remove();
      viewer2.cy.add(
        viewer2.projection.edges.filter((e) => e.displayOnly).map((e) => ({ data: e }))
      );
      viewer2.cy.nodes().forEach((n) => {
        n.toggleClass(
          "hidden",
          hidden.has(n.id()) || Boolean(viewer2.focusIds && !viewer2.focusIds.has(n.id()))
        );
      });
      viewer2.cy.edges().forEach((e) => {
        e.toggleClass(
          "hidden",
          !edges.has(e.id()) || e.source().hasClass("hidden") || e.target().hasClass("hidden") || e.data("connector") === "membership" && !viewer2.showMembership
        );
      });
      viewer2.cy.elements(":selected").unselect();
      const selected = viewer2.cy.getElementById(viewer2.inspected || "");
      if (selected.length && !selected.hasClass("hidden")) selected.select();
      if (viewer2.inspected && !selected.length && !viewer2.data.details[viewer2.inspected])
        viewer2.inspected = null;
    });
    viewer2.updating = false;
    viewer2.syncBoxes();
    viewer2.highlight();
    viewer2.renderSelection();
    viewer2.updateCounts();
    viewer2.metrics.filterMs = performance.now() - start;
  }
  function select(viewer2, id) {
    const start = performance.now(), e = viewer2.cy.getElementById(id);
    if (!e.length) return;
    viewer2.updating = true;
    viewer2.cy.elements(":selected").unselect();
    viewer2.inspected = id;
    if (!e.hasClass("hidden")) e.select();
    viewer2.updating = false;
    viewer2.highlight();
    viewer2.renderSelection();
    viewer2.metrics.selectionMs = performance.now() - start;
  }
  function syncFilters(viewer2) {
    document.querySelectorAll("#filters input").forEach((i) => i.checked = viewer2.filters.has(i.value));
    viewer2.$("member-links").checked = viewer2.showMembership;
  }
  function setupFilters(viewer2) {
    viewer2.$("filters").replaceChildren();
    const types = [
      ...new Set(
        viewer2.data.elements.filter((e) => "source" in e.data).map((e) => e.data.type)
      )
    ];
    viewer2.filters = new Set(types);
    for (const type of types) {
      const l = viewer2.make("label", void 0, viewer2.$("filters")), input = viewer2.make("input", void 0, l);
      input.type = "checkbox";
      input.value = type;
      input.checked = true;
      viewer2.make(
        "span",
        viewer2.data.elements.find((e) => "source" in e.data && e.data.type === type).data.label,
        l
      );
      input.onchange = () => {
        viewer2.remember();
        input.checked ? viewer2.filters.add(type) : viewer2.filters.delete(type);
        viewer2.applyVisibility();
      };
    }
  }
  function loadDataset(viewer2, index) {
    const start = performance.now();
    viewer2.updating = true;
    if (viewer2.dragFrame != null) cancelAnimationFrame(viewer2.dragFrame);
    viewer2.dragFrame = null;
    if (viewer2.cy) viewer2.cy.destroy();
    viewer2.portChoices = /* @__PURE__ */ new Map();
    viewer2.routes = /* @__PURE__ */ new Map();
    viewer2.data = viewer2.datasets[index];
    viewer2.presentation = initialPresentation(viewer2.data);
    viewer2.showSpacingAdvisories = false;
    viewer2.$("spacing-advisories").checked = false;
    viewer2.$("spacing-advisory-control").hidden = !viewer2.data.savedLayout;
    viewer2.$("presentation-conflicts")?.replaceChildren();
    if (viewer2.$("presentation-conflicts"))
      delete viewer2.$("presentation-conflicts").dataset.signature;
    viewer2.mode = "outlines";
    viewer2.HEADER = viewer2.data.savedLayout?.problem.header ?? 36;
    viewer2.$("relayout").disabled = Boolean(viewer2.data.savedLayout);
    viewer2.$("membership").disabled = Boolean(viewer2.data.savedLayout);
    viewer2.$("restore").textContent = viewer2.data.savedLayout ? "Restore saved layout" : "Restore arrangement";
    viewer2.inspected = null;
    viewer2.collapsed = /* @__PURE__ */ new Set();
    viewer2.history = [];
    viewer2.drag = null;
    Object.keys(viewer2.metrics).forEach((key) => viewer2.metrics[key] = 0);
    viewer2.$("dataset").value = String(index);
    viewer2.$("back").disabled = true;
    viewer2.$("search").value = "";
    viewer2.$("results").replaceChildren();
    viewer2.compactPositions = Object.fromEntries(
      Object.keys(viewer2.data.assemblies).map((id) => [
        id,
        { ...viewer2.data.positions[id] }
      ])
    );
    const elements = structuredClone(viewer2.data.elements);
    for (const e of elements)
      if ("source" in e.data) e.data.connector = "domain";
      else e.data.title = e.data.label;
    viewer2.cy = globalThis.cytoscape({
      container: viewer2.$("cy"),
      elements,
      layout: { name: "preset" },
      selectionType: "single",
      autoungrabify: false,
      minZoom: 0.04,
      maxZoom: 4,
      wheelSensitivity: 0.2,
      style: styles
    });
    if (viewer2.data.savedLayout) {
      for (const n of viewer2.cy.nodes()) {
        const r = viewer2.data.savedLayout.geometry.rectangles[n.id()];
        n.data({
          savedWidth: r.width - 3,
          savedHeight: r.height - 3,
          savedTextWidth: r.width - 16
        });
      }
      viewer2.cy.nodes().addClass("saved");
    }
    viewer2.$("outlines").classList.add("active");
    viewer2.$("membership").classList.remove("active");
    viewer2.$("canvas-note").textContent = viewer2.data.savedLayout ? "Drag nodes or assembly headers to arrange \xB7 boxes fit visible members \xB7 changes are session-only." : "Outlines show selected visible scope, not ownership or physical boundaries.";
    for (const [id] of Object.entries(viewer2.data.assemblies))
      viewer2.cy.getElementById(id).data({ boxWidth: 170, boxHeight: 42, bandStops: "0% 85% 85% 100%" });
    viewer2.cy.nodes().forEach((n) => {
      if (viewer2.memberships(n.id()).length > 1) n.addClass("shared");
    });
    viewer2.cy.on("select unselect", "node,edge", () => {
      if (viewer2.updating) return;
      viewer2.inspected = viewer2.cy.$(":selected").first().id() || null;
      viewer2.highlight();
      viewer2.renderSelection();
    });
    viewer2.cy.on("tap", (ev) => {
      if (ev.target === viewer2.cy) {
        viewer2.cy.elements(":selected").unselect();
        viewer2.inspected = null;
        viewer2.highlight();
        viewer2.renderSelection();
      }
    });
    viewer2.cy.on("grab", "node", (ev) => {
      const n = ev.target, a = viewer2.data.assemblies[n.id()];
      viewer2.drag = {
        id: n.id(),
        start: { ...n.position() },
        rectangles: viewer2.presentation ? movingRectangles(viewer2.data, viewer2.presentation, n.id()) : void 0,
        members: a && !viewer2.collapsed.has(n.id()) ? descendants(viewer2.data, n.id()).map((id) => viewer2.cy.getElementById(id)).filter((m) => m.length && !m.hasClass("hidden")).map((m) => ({ id: m.id(), position: { ...m.position() } })) : []
      };
    });
    viewer2.cy.on("drag", "node", (ev) => {
      if (viewer2.drag?.id !== ev.target.id()) return;
      if (viewer2.presentation) {
        viewer2.drag.latest = { ...ev.target.position() };
        if (viewer2.dragFrame == null)
          viewer2.dragFrame = requestAnimationFrame(() => {
            viewer2.dragFrame = null;
            flushPresentationDrag(viewer2);
          });
        return;
      }
      const pos = ev.target.position(), dx = pos.x - viewer2.drag.start.x, dy = pos.y - viewer2.drag.start.y;
      viewer2.updating = true;
      viewer2.cy.batch(
        () => viewer2.drag.members.forEach((m) => {
          const p = { x: m.position.x + dx, y: m.position.y + dy };
          viewer2.cy.getElementById(m.id).position(p);
          if (viewer2.data.assemblies[m.id]) viewer2.compactPositions[m.id] = { ...p };
        })
      );
      if (viewer2.data.assemblies[viewer2.drag.id])
        viewer2.compactPositions[viewer2.drag.id] = { ...pos };
      viewer2.updating = false;
      viewer2.syncBoxes();
    });
    viewer2.cy.on("free", "node", () => {
      if (viewer2.dragFrame != null) cancelAnimationFrame(viewer2.dragFrame);
      viewer2.dragFrame = null;
      flushPresentationDrag(viewer2);
      viewer2.drag = null;
      viewer2.syncBoxes();
    });
    viewer2.cy.on("position", "node", (ev) => {
      if (viewer2.syncing || viewer2.updating || viewer2.drag || viewer2.layoutMode) return;
      if (viewer2.data.assemblies[ev.target.id()] && !ev.target.hasClass("frame"))
        viewer2.compactPositions[ev.target.id()] = { ...ev.target.position() };
      if (viewer2.presentation) {
        const n = ev.target, r = viewer2.presentation.rectangles[n.id()];
        viewer2.presentation.rectangles[n.id()] = {
          ...r,
          x: n.position().x - r.width / 2,
          y: n.position().y - r.height / 2
        };
        viewer2.presentation.adjusted = true;
      }
      viewer2.syncBoxes();
    });
    viewer2.setupFilters();
    viewer2.showMembership = !viewer2.data.savedLayout;
    viewer2.syncFilters();
    viewer2.focusIds = viewer2.data.initialFocus ? /* @__PURE__ */ new Set([
      viewer2.data.initialFocus,
      ...viewer2.data.assemblies[viewer2.data.initialFocus].entities
    ]) : null;
    viewer2.updating = false;
    viewer2.applyVisibility();
    viewer2.fit();
    viewer2.$("notes").replaceChildren();
    viewer2.data.notes.forEach((n) => viewer2.make("p", n, viewer2.$("notes")));
    viewer2.$("diagnostics").replaceChildren();
    const diag = viewer2.data.diagnostics;
    if (diag.ambiguousParents.length || diag.containmentCycles.length) {
      const host = viewer2.make(
        "p",
        `${diag.ambiguousParents.length} object(s) with multiple containment parents; ${diag.containmentCycles.length} in containment cycles. No display parent was chosen.`,
        viewer2.$("diagnostics"),
        "issue"
      );
      for (const id of /* @__PURE__ */ new Set([
        ...diag.ambiguousParents,
        ...diag.containmentCycles
      ]))
        viewer2.nav(host, viewer2.label(id), id);
    }
    viewer2.$("anchors").disabled = Boolean(viewer2.data.savedLayout) || !viewer2.data.anchors.length;
    viewer2.$("anchors").checked = false;
    viewer2.selectLinkedObject();
    viewer2.metrics.loadMs = performance.now() - start;
    viewer2.$("timing").textContent = `Loaded in ${viewer2.metrics.loadMs.toFixed(0)} ms \xB7 ${viewer2.data.savedLayout ? "saved starting layout \xB7 draggable" : "reference arrangement"}`;
  }
  async function relayout(viewer2) {
    if (viewer2.data.savedLayout) return;
    const start = performance.now();
    viewer2.$("relayout").disabled = true;
    viewer2.layoutMode = true;
    viewer2.syncBoxes();
    const anchors = viewer2.$("anchors").checked ? viewer2.data.anchors.filter((id) => !viewer2.cy.getElementById(id).hasClass("hidden")).map((id) => ({
      nodeId: id,
      position: { ...viewer2.cy.getElementById(id).position() }
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
      if (viewer2.data.alignment)
        options.alignmentConstraint = {
          vertical: viewer2.data.alignment.vertical.filter(
            (g) => g.every((id) => !viewer2.cy.getElementById(id).hasClass("hidden"))
          )
        };
    }
    try {
      await new Promise((resolve, reject) => {
        try {
          viewer2.visible().layout({ ...options, stop: resolve }).run();
        } catch (e) {
          reject(e);
        }
      });
      for (const id of Object.keys(viewer2.data.assemblies))
        viewer2.compactPositions[id] = { ...viewer2.cy.getElementById(id).position() };
      viewer2.metrics.layoutMs = performance.now() - start;
      viewer2.$("timing").textContent = `fCoSE \xB7 ${viewer2.metrics.layoutMs.toFixed(0)} ms${anchors.length ? " \xB7 fixed anchors" : ""}`;
    } finally {
      viewer2.layoutMode = false;
      viewer2.syncBoxes();
      viewer2.fit();
      viewer2.$("relayout").disabled = false;
    }
  }
  function setMode(viewer2, next) {
    if (viewer2.data.savedLayout && next !== "outlines") return;
    viewer2.mode = next;
    viewer2.$("outlines").classList.toggle("active", next === "outlines");
    viewer2.$("membership").classList.toggle("active", next === "membership");
    viewer2.syncBoxes();
  }
  function flushPresentationDrag(viewer2) {
    const d = viewer2.drag;
    if (!viewer2.presentation || !d?.latest) return;
    translate(
      viewer2.presentation,
      d.rectangles,
      d.latest.x - d.start.x,
      d.latest.y - d.start.y
    );
    viewer2.syncBoxes();
  }

  // app.ts
  var viewer = {};
  viewer.connectionCentre = (...args) => connectionCentre(viewer, ...args);
  viewer.headerEndpoint = (...args) => headerEndpoint(viewer, ...args);
  viewer.endpoint = (...args) => endpoint(viewer, ...args);
  viewer.connectionGeometry = (...args) => connectionGeometry(viewer, ...args);
  viewer.updateConnections = (...args) => updateConnections(viewer, ...args);
  viewer.syncBoxes = (...args) => syncBoxes(viewer, ...args);
  viewer.remember = (...args) => remember(viewer, ...args);
  viewer.collapse = (...args) => collapse(viewer, ...args);
  viewer.fit = (...args) => fit(viewer, ...args);
  viewer.focus = (...args) => focus(viewer, ...args);
  viewer.reset = (...args) => reset(viewer, ...args);
  viewer.restore = (...args) => restore(viewer, ...args);
  viewer.reveal = (...args) => reveal(viewer, ...args);
  viewer.selectLinkedObject = (...args) => selectLinkedObject(viewer, ...args);
  viewer.valueText = (...args) => valueText(viewer, ...args);
  viewer.evidence = (...args) => evidence(viewer, ...args);
  viewer.nav = (...args) => nav(viewer, ...args);
  viewer.renderSelection = (...args) => renderSelection(viewer, ...args);
  viewer.highlight = (...args) => highlight(viewer, ...args);
  viewer.updateCounts = (...args) => updateCounts(viewer, ...args);
  viewer.applyVisibility = (...args) => applyVisibility(viewer, ...args);
  viewer.select = (id) => select(viewer, id);
  viewer.syncFilters = (...args) => syncFilters(viewer, ...args);
  viewer.setupFilters = (...args) => setupFilters(viewer, ...args);
  viewer.loadDataset = (...args) => loadDataset(viewer, ...args);
  viewer.relayout = (...args) => relayout(viewer, ...args);
  viewer.setMode = (...args) => setMode(viewer, ...args);
  viewer.datasets = JSON.parse(
    document.getElementById("graph-data").textContent
  ).datasets;
  viewer.$ = (id) => document.getElementById(id);
  viewer.make = (tag, text, parent, cls) => {
    const e = document.createElement(tag);
    if (text !== void 0) e.textContent = String(text);
    if (cls) e.className = cls;
    if (parent) parent.append(e);
    return e;
  };
  viewer.HEADER = 36;
  viewer.PAD = 24;
  viewer.labelMeasure = document.createElement("canvas").getContext("2d");
  viewer.cy = void 0;
  viewer.data = void 0;
  viewer.projection = void 0;
  viewer.inspected = null;
  viewer.focusIds = null;
  viewer.history = [];
  viewer.collapsed = /* @__PURE__ */ new Set();
  viewer.filters = /* @__PURE__ */ new Set();
  viewer.mode = "outlines";
  viewer.showMembership = true;
  viewer.fourPorts = true;
  viewer.compactPositions = {};
  viewer.drag = null;
  viewer.presentation = null;
  viewer.showSpacingAdvisories = false;
  viewer.dragFrame = null;
  viewer.syncing = false;
  viewer.updating = false;
  viewer.layoutMode = false;
  viewer.portChoices = /* @__PURE__ */ new Map();
  viewer.routes = /* @__PURE__ */ new Map();
  viewer.metrics = { loadMs: 0, layoutMs: 0, selectionMs: 0, filterMs: 0 };
  viewer.label = (id) => viewer.data.details[id]?.name || viewer.cy.getElementById(id).data("label") || id;
  viewer.memberships = (id) => Object.entries(viewer.data.assemblies).filter(
    ([, a]) => a.entities.includes(id) || a.relationships.includes(id)
  );
  viewer.visible = () => viewer.cy.elements().filter((e) => !e.hasClass("hidden"));
  viewer.snapshot = () => ({
    focus: viewer.focusIds ? [...viewer.focusIds] : null,
    filters: [...viewer.filters],
    collapsed: [...viewer.collapsed],
    showMembership: viewer.showMembership
  });
  viewer.routingStyle = "curve-style control-point-distances control-point-weights control-point-step-size edge-distances loop-direction loop-sweep text-rotation";
  viewer.datasets.forEach((d, i) => {
    const o = viewer.make("option", d.name, viewer.$("dataset"));
    o.value = String(i);
  });
  viewer.$("dataset").onchange = () => viewer.loadDataset(Number(viewer.$("dataset").value));
  viewer.$("membership").onclick = () => viewer.setMode("membership");
  viewer.$("outlines").onclick = () => viewer.setMode("outlines");
  viewer.$("four-port-routing").onchange = () => {
    viewer.fourPorts = viewer.$("four-port-routing").checked;
    viewer.syncBoxes();
  };
  viewer.$("spacing-advisories").onchange = () => {
    viewer.showSpacingAdvisories = viewer.$("spacing-advisories").checked;
    viewer.syncBoxes();
  };
  viewer.$("fit").onclick = viewer.fit;
  viewer.$("restore").onclick = viewer.restore;
  viewer.$("relayout").onclick = viewer.relayout;
  viewer.$("focus").onclick = () => {
    if (viewer.inspected) viewer.focus(viewer.inspected);
  };
  viewer.$("reset").onclick = viewer.reset;
  viewer.$("collapse-all").onclick = () => viewer.collapse(Object.keys(viewer.data.assemblies), true);
  viewer.$("expand-all").onclick = () => viewer.collapse(Object.keys(viewer.data.assemblies), false);
  viewer.$("member-links").onchange = () => {
    viewer.remember();
    viewer.showMembership = viewer.$("member-links").checked;
    viewer.applyVisibility();
  };
  viewer.$("back").onclick = () => {
    const previous = viewer.history.pop();
    if (!previous) return;
    viewer.focusIds = previous.focus ? new Set(previous.focus) : null;
    viewer.filters = new Set(previous.filters);
    viewer.collapsed = new Set(previous.collapsed);
    viewer.showMembership = previous.showMembership;
    viewer.syncFilters();
    viewer.applyVisibility();
    viewer.fit();
    viewer.$("back").disabled = !viewer.history.length;
  };
  viewer.$("clear").onclick = () => {
    viewer.cy.elements(":selected").unselect();
    viewer.inspected = null;
    viewer.highlight();
    viewer.renderSelection();
  };
  viewer.$("search").oninput = () => {
    const q = viewer.$("search").value.trim().toLowerCase();
    viewer.$("results").replaceChildren();
    if (!q) return;
    viewer.cy.nodes().filter(
      (n) => [n.data("label"), n.data("code"), n.id()].some(
        (v) => (v || "").toLowerCase().includes(q)
      )
    ).slice(0, 8).forEach((n) => {
      const button = viewer.make(
        "button",
        `${n.data("label")} \xB7 ${n.data("code")}`,
        viewer.$("results")
      );
      button.onclick = () => {
        viewer.select(n.id());
        if (!n.hasClass("hidden")) {
          const bb = n.renderedBoundingBox();
          if (bb.x1 < 0 || bb.y1 < 0 || bb.x2 > viewer.cy.width() || bb.y2 > viewer.cy.height())
            viewer.cy.center(n);
        }
        viewer.$("results").replaceChildren();
      };
    });
  };
  viewer.$("search").onkeydown = (e) => {
    if (e.key === "Enter") viewer.$("results").querySelector("button")?.click();
    if (e.key === "Escape") viewer.$("results").replaceChildren();
  };
  new ResizeObserver(() => {
    if (viewer.cy) viewer.cy.resize();
  }).observe(viewer.$("stage"));
  window.graphReview = {
    get cy() {
      return viewer.cy;
    },
    get data() {
      return viewer.data;
    },
    get selected() {
      return viewer.inspected;
    },
    get collapsed() {
      return [...viewer.collapsed];
    },
    get projection() {
      return viewer.projection;
    },
    get presentation() {
      return structuredClone(viewer.presentation);
    },
    get metrics() {
      return { ...viewer.metrics };
    },
    get routes() {
      return Object.fromEntries(viewer.routes);
    },
    get visibleIds() {
      return viewer.visible().map((e) => e.id());
    },
    loadDataset: viewer.loadDataset,
    select: viewer.select,
    focus: viewer.focus,
    reset: viewer.reset,
    restore: viewer.restore,
    relayout: viewer.relayout,
    setMode: viewer.setMode,
    syncBoxes: viewer.syncBoxes,
    collapse: viewer.collapse
  };
  window.addEventListener("hashchange", viewer.selectLinkedObject);
  viewer.loadDataset(0);
})();
