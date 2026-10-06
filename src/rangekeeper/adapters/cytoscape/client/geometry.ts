import { resizePresentation } from "./presentation";
import type cytoscape from "cytoscape";
import type { Viewer } from "./context";
import * as fourPortRouting from "./routing";
import { projectCollapse } from "./projection";
import { assemblyOrder, descendants, revealPath } from "./membership";
export function connectionCentre(viewer: Viewer, node) {
  const p = node.position();
  return {
    x: p.x,
    y: p.y - (node.hasClass("frame") ? node.height() / 2 - viewer.HEADER / 2 : 0),
  };
}
export function headerEndpoint(viewer: Viewer, node, other) {
  const p = viewer.connectionCentre(node),
    q = viewer.connectionCentre(other);
  const dx = q.x - p.x,
    dy = q.y - p.y;
  const scale = Math.max(
    Math.abs(dx) / (node.width() / 2),
    Math.abs(dy) / (viewer.HEADER / 2),
  );
  return scale
    ? { x: p.x + dx / scale, y: p.y + dy / scale }
    : { x: p.x, y: p.y + viewer.HEADER / 2 };
}
export function endpoint(viewer: Viewer, edge, source) {
  const node = source ? edge.source() : edge.target();
  const other = source ? edge.target() : edge.source();
  const p = node.position();
  if (node.hasClass("frame")) {
    // Native explicit endpoints follow the header perimeter within the larger node.
    const q = viewer.headerEndpoint(node, other);
    return `${q.x - p.x}px ${q.y - p.y}px`;
  }
  if (other.hasClass("frame")) {
    const q = viewer.headerEndpoint(other, node);
    return `${(Math.atan2(q.y - p.y, q.x - p.x) * 180) / Math.PI + 90}deg`;
  }
  return "outside-to-node";
}
export function connectionGeometry(viewer: Viewer, n) {
  return {
    ...viewer.connectionCentre(n),
    w: n.width(),
    h: n.hasClass("frame") ? viewer.HEADER : n.height(),
    nodePosition: { ...n.position() },
  };
}
export function updateConnections(viewer: Viewer) {
  const eligible = viewer.cy
    .edges()
    .filter((e) => viewer.fourPorts && !viewer.layoutMode && !e.hasClass("hidden"));
  const references = new Map(),
    pairs = new Map();
  const finite = (p) => p && Number.isFinite(p.x) && Number.isFinite(p.y);
  viewer.routes = new Map();
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
  viewer.cy.batch(() =>
    nativePairs.forEach((e) => {
      e.removeStyle(viewer.routingStyle);
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
  viewer.cy.batch(() =>
    viewer.cy.edges().forEach((e) => {
      const active = eligible.has(e);
      e.toggleClass("four-port", active);
      if (!active) {
        e.removeStyle(viewer.routingStyle);
        e.style({
          "source-endpoint": viewer.endpoint(e, true),
          "target-endpoint": viewer.endpoint(e, false),
        });
        return;
      }
      const source = e.source(),
        target = e.target();
      const pair = pairs.get(JSON.stringify([source.id(), target.id()].sort()));
      const result = fourPortRouting.route({
        source: viewer.connectionGeometry(source),
        target: viewer.connectionGeometry(target),
        sourceId: source.id(),
        targetId: target.id(),
        ...references.get(e.id()),
        previous: viewer.portChoices.get(e.id()),
        lane: pair.indexOf(e.id()),
        laneCount: pair.length,
      });
      viewer.portChoices.set(e.id(), {
        sourcePort: result.sourcePort,
        targetPort: result.targetPort,
      });
      viewer.routes.set(e.id(), result);
      e.style(
        fourPortRouting.style(result, source.position(), target.position()),
      );
    }),
  );
  // Read geometry after routing styles have flushed. This also supports the
  // comparison mode without changing its curve or native label rotation.
  const labels = viewer.cy
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
      viewer.labelMeasure.font = `${e.style("font-style")} ${e.style("font-weight")} ${e.numericStyle("font-size")}px ${e.style("font-family")}`;
      let text = e.style("label");
      if (e.style("text-transform") === "uppercase") text = text.toUpperCase();
      if (e.style("text-transform") === "lowercase") text = text.toLowerCase();
      const fitted = fourPortRouting.fitLabel(
        text,
        Math.max(1, width),
        (text) => Math.ceil(viewer.labelMeasure.measureText(text).width),
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
  viewer.cy.batch(() => labels.forEach(([e, style]) => e.style(style)));
}
export function syncBoxes(viewer: Viewer) {
  if (viewer.syncing || !viewer.cy) return;
  viewer.syncing = true;
  if (viewer.data.savedLayout) {
    const saved = viewer.data.savedLayout,
      state = viewer.presentation;
    const visible = new Set(
      viewer
        .visible()
        .nodes()
        .map((n) => n.id()),
    );
    resizePresentation(
      viewer.data,
      state,
      visible,
      viewer.collapsed,
      viewer.drag?.id,
      viewer.showSpacingAdvisories,
    );
    for (const n of viewer.cy.nodes()) {
      const r = state.display[n.id()],
        assembly = viewer.data.assemblies[n.id()];
      const frame = Boolean(
        assembly &&
          !viewer.collapsed.has(n.id()) &&
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
        frameZ: Math.min(4, revealPath(viewer.data, n.id()).length),
        title: assembly
          ? `${viewer.collapsed.has(n.id()) ? "▸" : "▾"} ${assembly.name}`
          : n.data("label"),
      });
      n.position({ x: r.x + r.width / 2, y: r.y + r.height / 2 });
    }
    renderConflicts(viewer);
    viewer.updateConnections();
    viewer.syncing = false;
    return;
  }
  {
    for (const id of assemblyOrder(viewer.data)) {
      const assembly = viewer.data.assemblies[id];
      const node = viewer.cy.getElementById(id);
      node.data("frameZ", Math.min(4, revealPath(viewer.data, id).length));
      node.data(
        "title",
        `${viewer.collapsed.has(id) ? "▸" : "▾"} ${assembly.name}`,
      );
      const members = viewer.cy.collection(
        assembly.entities
          .map((mid) => viewer.cy.getElementById(mid)[0])
          .filter(
            (n) => n && !n.hasClass("hidden"),
          ) as unknown as cytoscape.CollectionArgument,
      );
      const frame =
        viewer.mode === "outlines" &&
        !viewer.layoutMode &&
        !viewer.collapsed.has(id) &&
        !node.hasClass("hidden") &&
        members.length > 0;
      node.toggleClass("frame", frame);
      if (frame) {
        if (viewer.drag?.id === id) continue;
        const bb = members.boundingBox({
          includeLabels: true,
          includeOverlays: false,
          useCache: false,
        } as cytoscape.BoundingBoxOptions & { useCache: boolean });
        const w = Math.max(180, bb.w + 2 * viewer.PAD),
          h = bb.h + 2 * viewer.PAD + viewer.HEADER;
        const stop = (viewer.HEADER / h) * 100;
        node.data({
          boxWidth: w,
          boxHeight: h,
          bandStops: `0% ${stop}% ${stop}% 100%`,
        });
        node.position({
          x: (bb.x1 + bb.x2) / 2,
          y: (bb.y1 + bb.y2 - viewer.HEADER) / 2,
        });
      } else if (viewer.compactPositions[id] && viewer.drag?.id !== id) {
        node.position({ ...viewer.compactPositions[id] });
      }
    }
  }
  // Flush frame geometry before reading width/height for header attachment points.
  // Cytoscape defers mapped style updates until the preceding batch ends.
  viewer.updateConnections();
  viewer.syncing = false;
}

function renderConflicts(viewer: Viewer) {
  const state = viewer.presentation,
    conflicts = state.conflicts;
  const errors = conflicts.filter((c) => c.code !== "clearance"),
    advisories = conflicts.filter((c) => c.code === "clearance");
  const affected = new Set(errors.flatMap((c) => c.objects));
  const nearby = new Set(advisories.flatMap((c) => c.objects));
  viewer.cy.nodes().forEach((n) => {
    n.toggleClass("presentation-conflict", affected.has(n.id()));
    n.toggleClass(
      "presentation-advisory",
      nearby.has(n.id()) && !affected.has(n.id()),
    );
  });
  const host = viewer.$("presentation-conflicts");
  if (!host) return;
  const signature = JSON.stringify([
    state.adjusted,
    conflicts,
    viewer.showSpacingAdvisories,
  ]);
  if (host.dataset.signature === signature) return;
  host.dataset.signature = signature;
  host.replaceChildren();
  viewer.make(
    "p",
    `${state.adjusted ? "Adjusted presentation" : "Saved starting layout"} · ${errors.length} visible enclosure/collision conflict(s).${viewer.showSpacingAdvisories ? ` ${advisories.length} spacing ${advisories.length === 1 ? "advisory" : "advisories"} (amber).` : ""}`,
    host,
  );
  if (state.adjusted)
    viewer.make(
      "p",
      "Grid, ordering and compactness have not been revalidated. Changes last until reload or dataset switch.",
      host,
    );
  if (conflicts.length) {
    const details = viewer.make("details", undefined, host);
    viewer.make("summary", "Inspect conflicts and advisories", details);
    for (const c of conflicts.slice(0, 50)) {
      const row = viewer.make("p", c.message + ": ", details);
      for (const id of c.objects) {
        const b = viewer.make("button", viewer.label(id), row);
        b.onclick = () => {
          viewer.select(id);
          viewer.cy.center(viewer.cy.getElementById(id));
        };
      }
    }
    if (conflicts.length > 50)
      viewer.make("p", `Showing 50 of ${conflicts.length} findings.`, details);
  }
}
