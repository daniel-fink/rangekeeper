var fourPortRouting = (() => {
  var __defProp = Object.defineProperty;
  var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
  var __getOwnPropNames = Object.getOwnPropertyNames;
  var __hasOwnProp = Object.prototype.hasOwnProperty;
  var __export = (target, all) => {
    for (var name in all)
      __defProp(target, name, { get: all[name], enumerable: true });
  };
  var __copyProps = (to, from, except, desc) => {
    if (from && typeof from === "object" || typeof from === "function") {
      for (let key of __getOwnPropNames(from))
        if (!__hasOwnProp.call(to, key) && key !== except)
          __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
    }
    return to;
  };
  var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

  // routing.ts
  var routing_exports = {};
  __export(routing_exports, {
    choosePort: () => choosePort,
    curvePoint: () => curvePoint,
    fitLabel: () => fitLabel,
    handleLength: () => handleLength,
    intersection: () => intersection,
    labelAngle: () => labelAngle,
    labelWidth: () => labelWidth,
    normals: () => normals,
    ports: () => ports,
    route: () => route,
    sampleCurve: () => sampleCurve,
    style: () => style
  });
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
  return __toCommonJS(routing_exports);
})();
