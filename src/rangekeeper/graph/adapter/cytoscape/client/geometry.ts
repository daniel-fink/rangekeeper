import { resizePresentation } from "./presentation";
import type cytoscape from "cytoscape";
import type { ViewerContext } from "./context";
import * as fourPortRouting from "./routing";
import { projectCollapse } from "./projection";
import { assemblyOrder, descendants, revealPath } from "./membership";
export function connectionCentre(ctx: ViewerContext, node) {
  const p = node.position();
  return {
    x: p.x,
    y: p.y - (node.hasClass("frame") ? node.height() / 2 - ctx.HEADER / 2 : 0),
  };
}
export function headerEndpoint(ctx: ViewerContext, node, other) {
  const p = ctx.connectionCentre(node),
    q = ctx.connectionCentre(other);
  const dx = q.x - p.x,
    dy = q.y - p.y;
  const scale = Math.max(
    Math.abs(dx) / (node.width() / 2),
    Math.abs(dy) / (ctx.HEADER / 2),
  );
  return scale
    ? { x: p.x + dx / scale, y: p.y + dy / scale }
    : { x: p.x, y: p.y + ctx.HEADER / 2 };
}
export function endpoint(ctx: ViewerContext, edge, source) {
  const node = source ? edge.source() : edge.target();
  const other = source ? edge.target() : edge.source();
  const p = node.position();
  if (node.hasClass("frame")) {
    // Native explicit endpoints follow the header perimeter within the larger node.
    const q = ctx.headerEndpoint(node, other);
    return `${q.x - p.x}px ${q.y - p.y}px`;
  }
  if (other.hasClass("frame")) {
    const q = ctx.headerEndpoint(other, node);
    return `${(Math.atan2(q.y - p.y, q.x - p.x) * 180) / Math.PI + 90}deg`;
  }
  return "outside-to-node";
}
export function connectionGeometry(ctx: ViewerContext, n) {
  return {
    ...ctx.connectionCentre(n),
    w: n.width(),
    h: n.hasClass("frame") ? ctx.HEADER : n.height(),
    nodePosition: { ...n.position() },
  };
}
export function updateConnections(ctx: ViewerContext) {
  const eligible = ctx.cy
    .edges()
    .filter((e) => ctx.fourPorts && !ctx.layoutMode && !e.hasClass("hidden"));
  const references = new Map(),
    pairs = new Map();
  const finite = (p) => p && Number.isFinite(p.x) && Number.isFinite(p.y);
  ctx.routes = new Map();
  // Read an unsnapped native reference before applying our curves, synchronously
  // within the same render frame. Header pairs use effective-rectangle geometry.
  const nativePairs = eligible.filter(
    (e: cytoscape.EdgeSingular) =>
      !e.source().hasClass("frame") &&
      !e.target().hasClass("frame") &&
      e.source().id() !== e.target().id() &&
      Math.hypot(
        e.source().position().x - e.target().position().x,
        e.source().position().y - e.target().position().y,
      ) > 1e-6,
  );
  ctx.cy.batch(() =>
    nativePairs.forEach((e) => {
      e.removeStyle(ctx.routingStyle);
      e.style({
        "curve-style": "straight",
        "source-endpoint": "outside-to-line",
        "target-endpoint": "outside-to-line",
      });
    }),
  );
  nativePairs.forEach((e) => {
    const source = e.sourceEndpoint(),
      target = e.targetEndpoint();
    if (finite(source) && finite(target))
      references.set(e.id(), {
        sourceReference: source,
        targetReference: target,
      });
  });
  for (const e of [...eligible].sort((a, b) => a.id().localeCompare(b.id()))) {
    const key = JSON.stringify([e.source().id(), e.target().id()].sort());
    if (!pairs.has(key)) pairs.set(key, []);
    pairs.get(key).push(e.id());
  }
  ctx.cy.batch(() =>
    ctx.cy.edges().forEach((e) => {
      const active = eligible.has(e);
      e.toggleClass("four-port", active);
      if (!active) {
        e.removeStyle(ctx.routingStyle);
        e.style({
          "source-endpoint": ctx.endpoint(e, true),
          "target-endpoint": ctx.endpoint(e, false),
        });
        return;
      }
      const source = e.source(),
        target = e.target();
      const pair = pairs.get(JSON.stringify([source.id(), target.id()].sort()));
      const result = fourPortRouting.route({
        source: ctx.connectionGeometry(source),
        target: ctx.connectionGeometry(target),
        sourceId: source.id(),
        targetId: target.id(),
        ...references.get(e.id()),
        previous: ctx.portChoices.get(e.id()),
        lane: pair.indexOf(e.id()),
        laneCount: pair.length,
      });
      ctx.portChoices.set(e.id(), {
        sourcePort: result.sourcePort,
        targetPort: result.targetPort,
      });
      ctx.routes.set(e.id(), result);
      e.style(
        fourPortRouting.style(result, source.position(), target.position()),
      );
    }),
  );
  // Read geometry after routing styles have flushed. This also supports the
  // comparison mode without changing its curve or native label rotation.
  const labels = ctx.cy
    .edges()
    .filter((e) => !e.hasClass("hidden"))
    .map((e: cytoscape.EdgeSingular) => {
      const geometry = {
        source: e.sourceEndpoint(),
        target: e.targetEndpoint(),
        controls: e.controlPoints() || [],
      };
      const arc = fourPortRouting.sampleCurve(geometry),
        width = fourPortRouting.labelWidth(geometry, arc);
      ctx.labelMeasure.font = `${e.style("font-style")} ${e.style("font-weight")} ${e.numericStyle("font-size")}px ${e.style("font-family")}`;
      let text = e.style("label");
      if (e.style("text-transform") === "uppercase") text = text.toUpperCase();
      if (e.style("text-transform") === "lowercase") text = text.toLowerCase();
      const fitted = fourPortRouting.fitLabel(
        text,
        Math.max(1, width),
        (text) => Math.ceil(ctx.labelMeasure.measureText(text).width),
      );
      const style = {
        "text-max-width": Math.max(1, width),
        "text-opacity": width >= 32 ? 1 : 0,
      };
      if (e.hasClass("four-port"))
        style["text-rotation"] =
          `${fourPortRouting.labelAngle(geometry, fitted.width + 2 * e.numericStyle("text-background-padding"), arc)}rad`;
      return [e, style] as const;
    });
  ctx.cy.batch(() => labels.forEach(([e, style]) => e.style(style)));
}
export function syncBoxes(ctx: ViewerContext) {
  if (ctx.syncing || !ctx.cy) return;
  ctx.syncing = true;
  if (ctx.data.savedLayout) {
    const saved = ctx.data.savedLayout,
      state = ctx.presentation;
    const visible = new Set(
      ctx
        .visible()
        .nodes()
        .map((n) => n.id()),
    );
    resizePresentation(
      ctx.data,
      state,
      visible,
      ctx.collapsed,
      ctx.drag?.id,
      ctx.showSpacingAdvisories,
    );
    for (const n of ctx.cy.nodes()) {
      const r = state.display[n.id()],
        assembly = ctx.data.assemblies[n.id()];
      const frame = Boolean(
        assembly &&
          !ctx.collapsed.has(n.id()) &&
          assembly.entities.some((i) => visible.has(i)) &&
          visible.has(n.id()),
      );
      const stop = Math.min(100, (saved.problem.header / r.height) * 100);
      n.toggleClass("frame", frame);
      n.data({
        savedWidth: r.width - 3,
        savedHeight: r.height - 3,
        savedTextWidth: r.width - 16,
        boxWidth: r.width - 3,
        boxHeight: r.height - 3,
        bandStops: `0% ${stop}% ${stop}% 100%`,
        frameZ: Math.min(4, revealPath(ctx.data, n.id()).length),
        title: assembly
          ? `${ctx.collapsed.has(n.id()) ? "▸" : "▾"} ${assembly.name}`
          : n.data("label"),
      });
      n.position({ x: r.x + r.width / 2, y: r.y + r.height / 2 });
    }
    renderConflicts(ctx);
    ctx.updateConnections();
    ctx.syncing = false;
    return;
  }
  {
    for (const id of assemblyOrder(ctx.data)) {
      const assembly = ctx.data.assemblies[id];
      const node = ctx.cy.getElementById(id);
      node.data("frameZ", Math.min(4, revealPath(ctx.data, id).length));
      node.data(
        "title",
        `${ctx.collapsed.has(id) ? "▸" : "▾"} ${assembly.name}`,
      );
      const members = ctx.cy.collection(
        assembly.entities
          .map((mid) => ctx.cy.getElementById(mid)[0])
          .filter(
            (n) => n && !n.hasClass("hidden"),
          ) as unknown as cytoscape.CollectionArgument,
      );
      const frame =
        ctx.mode === "outlines" &&
        !ctx.layoutMode &&
        !ctx.collapsed.has(id) &&
        !node.hasClass("hidden") &&
        members.length > 0;
      node.toggleClass("frame", frame);
      if (frame) {
        if (ctx.drag?.id === id) continue;
        const bb = members.boundingBox({
          includeLabels: true,
          includeOverlays: false,
          useCache: false,
        } as cytoscape.BoundingBoxOptions & { useCache: boolean });
        const w = Math.max(180, bb.w + 2 * ctx.PAD),
          h = bb.h + 2 * ctx.PAD + ctx.HEADER;
        const stop = (ctx.HEADER / h) * 100;
        node.data({
          boxWidth: w,
          boxHeight: h,
          bandStops: `0% ${stop}% ${stop}% 100%`,
        });
        node.position({
          x: (bb.x1 + bb.x2) / 2,
          y: (bb.y1 + bb.y2 - ctx.HEADER) / 2,
        });
      } else if (ctx.compactPositions[id] && ctx.drag?.id !== id) {
        node.position({ ...ctx.compactPositions[id] });
      }
    }
  }
  // Flush frame geometry before reading width/height for header attachment points.
  // Cytoscape defers mapped style updates until the preceding batch ends.
  ctx.updateConnections();
  ctx.syncing = false;
}

function renderConflicts(ctx: ViewerContext) {
  const state = ctx.presentation,
    conflicts = state.conflicts;
  const errors = conflicts.filter((c) => c.code !== "clearance"),
    advisories = conflicts.filter((c) => c.code === "clearance");
  const affected = new Set(errors.flatMap((c) => c.objects));
  const nearby = new Set(advisories.flatMap((c) => c.objects));
  ctx.cy.nodes().forEach((n) => {
    n.toggleClass("presentation-conflict", affected.has(n.id()));
    n.toggleClass(
      "presentation-advisory",
      nearby.has(n.id()) && !affected.has(n.id()),
    );
  });
  const host = ctx.$("presentation-conflicts");
  if (!host) return;
  const signature = JSON.stringify([
    state.adjusted,
    conflicts,
    ctx.showSpacingAdvisories,
  ]);
  if (host.dataset.signature === signature) return;
  host.dataset.signature = signature;
  host.replaceChildren();
  ctx.make(
    "p",
    `${state.adjusted ? "Adjusted presentation" : "Saved starting layout"} · ${errors.length} visible enclosure/collision conflict(s).${ctx.showSpacingAdvisories ? ` ${advisories.length} spacing ${advisories.length === 1 ? "advisory" : "advisories"} (amber).` : ""}`,
    host,
  );
  if (state.adjusted)
    ctx.make(
      "p",
      "Grid, ordering and compactness have not been revalidated. Changes last until reload or dataset switch.",
      host,
    );
  if (conflicts.length) {
    const details = ctx.make("details", undefined, host);
    ctx.make("summary", "Inspect conflicts and advisories", details);
    for (const c of conflicts.slice(0, 50)) {
      const row = ctx.make("p", c.message + ": ", details);
      for (const id of c.objects) {
        const b = ctx.make("button", ctx.label(id), row);
        b.onclick = () => {
          ctx.select(id);
          ctx.cy.center(ctx.cy.getElementById(id));
        };
      }
    }
    if (conflicts.length > 50)
      ctx.make("p", `Showing 50 of ${conflicts.length} findings.`, details);
  }
}
