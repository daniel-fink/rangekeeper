import {
  initialPresentation,
  movingRectangles,
  translate,
} from "./presentation";
import { styles } from "./styles";
import type cytoscape from "cytoscape";
import type { Viewer } from "./context";
import * as fourPortRouting from "./routing";
import { projectCollapse } from "./projection";
import { assemblyOrder, descendants, revealPath } from "./membership";
export function updateCounts(viewer: Viewer) {
  viewer.$("counts").textContent =
    `${viewer.visible().nodes().length} / ${viewer.cy.nodes().length} objects · ${viewer.visible().edges().length} displayed connections`;
}
export function highlight(viewer: Viewer) {
  viewer.cy.elements().removeClass("member");
  const assembly = viewer.data.assemblies[viewer.inspected];
  if (!assembly) return;
  const ids = new Set([...assembly.entities, ...assembly.relationships]);
  viewer.cy.elements().forEach((e) => {
    if (
      ids.has(e.id()) ||
      (e.data("connector") === "summary" &&
        e.data("originalIds").some((id) => ids.has(id)))
    )
      e.addClass("member");
  });
}
export function applyVisibility(viewer: Viewer) {
  const start = performance.now();
  viewer.updating = true;
  viewer.projection = projectCollapse(viewer.data, viewer.collapsed, viewer.filters);
  const hidden = new Set(viewer.projection.hiddenIds);
  const edges = new Map(viewer.projection.edges.map((e) => [e.id, e]));
  viewer.cy.batch(() => {
    viewer.cy.edges("[?displayOnly]").remove();
    viewer.cy.add(
      viewer.projection.edges
        .filter((e) => e.displayOnly)
        .map((e) => ({ data: e })),
    );
    viewer.cy.nodes().forEach((n) => {
      n.toggleClass(
        "hidden",
        hidden.has(n.id()) ||
          Boolean(viewer.focusIds && !viewer.focusIds.has(n.id())),
      );
    });
    viewer.cy.edges().forEach((e) => {
      e.toggleClass(
        "hidden",
        !edges.has(e.id()) ||
          e.source().hasClass("hidden") ||
          e.target().hasClass("hidden") ||
          (e.data("connector") === "membership" && !viewer.showMembership),
      );
    });
    viewer.cy.elements(":selected").unselect();
    const selected = viewer.cy.getElementById(viewer.inspected || "");
    if (selected.length && !selected.hasClass("hidden")) selected.select();
    if (viewer.inspected && !selected.length && !viewer.data.details[viewer.inspected])
      viewer.inspected = null;
  });
  viewer.updating = false;
  viewer.syncBoxes();
  viewer.highlight();
  viewer.renderSelection();
  viewer.updateCounts();
  viewer.metrics.filterMs = performance.now() - start;
}
export function select(viewer: Viewer, id) {
  const start = performance.now(),
    e = viewer.cy.getElementById(id);
  if (!e.length) return;
  viewer.updating = true;
  viewer.cy.elements(":selected").unselect();
  viewer.inspected = id;
  if (!e.hasClass("hidden")) e.select();
  viewer.updating = false;
  viewer.highlight();
  viewer.renderSelection();
  viewer.metrics.selectionMs = performance.now() - start;
}
export function syncFilters(viewer: Viewer) {
  document
    .querySelectorAll<HTMLInputElement>("#filters input")
    .forEach((i) => (i.checked = viewer.filters.has(i.value)));
  viewer.$("member-links").checked = viewer.showMembership;
}
export function setupFilters(viewer: Viewer) {
  viewer.$("filters").replaceChildren();
  const types = [
    ...new Set(
      viewer.data.elements
        .filter((e) => "source" in e.data)
        .map((e) => e.data.type),
    ),
  ];
  viewer.filters = new Set(types);
  for (const type of types) {
    const l = viewer.make("label", undefined, viewer.$("filters")),
      input = viewer.make("input", undefined, l);
    input.type = "checkbox";
    input.value = type;
    input.checked = true;
    viewer.make(
      "span",
      viewer.data.elements.find((e) => "source" in e.data && e.data.type === type)
        .data.label,
      l,
    );
    input.onchange = () => {
      viewer.remember();
      input.checked ? viewer.filters.add(type) : viewer.filters.delete(type);
      viewer.applyVisibility();
    };
  }
}
export function loadDataset(viewer: Viewer, index) {
  const start = performance.now();
  viewer.updating = true;
  if (viewer.dragFrame != null) cancelAnimationFrame(viewer.dragFrame);
  viewer.dragFrame = null;
  if (viewer.cy) viewer.cy.destroy();
  viewer.portChoices = new Map();
  viewer.routes = new Map();
  viewer.data = viewer.datasets[index];
  viewer.presentation = initialPresentation(viewer.data);
  viewer.showSpacingAdvisories = false;
  viewer.$("spacing-advisories").checked = false;
  viewer.$("spacing-advisory-control").hidden = !viewer.data.savedLayout;
  viewer.$("presentation-conflicts")?.replaceChildren();
  if (viewer.$("presentation-conflicts"))
    delete viewer.$("presentation-conflicts").dataset.signature;
  viewer.mode = "outlines";
  viewer.HEADER = viewer.data.savedLayout?.problem.header ?? 36;
  viewer.$("relayout").disabled = Boolean(viewer.data.savedLayout);
  viewer.$("membership").disabled = Boolean(viewer.data.savedLayout);
  viewer.$("restore").textContent = viewer.data.savedLayout
    ? "Restore saved layout"
    : "Restore arrangement";
  viewer.inspected = null;
  viewer.collapsed = new Set();
  viewer.history = [];
  viewer.drag = null;
  Object.keys(viewer.metrics).forEach((key) => (viewer.metrics[key] = 0));
  viewer.$("dataset").value = String(index);
  viewer.$("back").disabled = true;
  viewer.$("search").value = "";
  viewer.$("results").replaceChildren();
  viewer.compactPositions = Object.fromEntries(
    Object.keys(viewer.data.assemblies).map((id) => [
      id,
      { ...viewer.data.positions[id] },
    ]),
  );
  const elements = structuredClone(viewer.data.elements);
  for (const e of elements)
    if ("source" in e.data) e.data.connector = "domain";
    else e.data.title = e.data.label;
  viewer.cy = (globalThis.cytoscape as typeof import("cytoscape"))({
    container: viewer.$("cy"),
    elements,
    layout: { name: "preset" },
    selectionType: "single",
    autoungrabify: false,
    minZoom: 0.04,
    maxZoom: 4,
    wheelSensitivity: 0.2,
    style: styles,
  });
  if (viewer.data.savedLayout) {
    for (const n of viewer.cy.nodes()) {
      const r = viewer.data.savedLayout.geometry.rectangles[n.id()];
      n.data({
        savedWidth: r.width - 3,
        savedHeight: r.height - 3,
        savedTextWidth: r.width - 16,
      });
    }
    viewer.cy.nodes().addClass("saved");
  }
  viewer.$("outlines").classList.add("active");
  viewer.$("membership").classList.remove("active");
  viewer.$("canvas-note").textContent = viewer.data.savedLayout
    ? "Drag nodes or assembly headers to arrange · boxes fit visible members · changes are session-only."
    : "Outlines show selected visible scope, not ownership or physical boundaries.";
  for (const [id] of Object.entries(viewer.data.assemblies))
    viewer.cy
      .getElementById(id)
      .data({ boxWidth: 170, boxHeight: 42, bandStops: "0% 85% 85% 100%" });
  viewer.cy.nodes().forEach((n) => {
    if (viewer.memberships(n.id()).length > 1) n.addClass("shared");
  });
  viewer.cy.on("select unselect", "node,edge", () => {
    if (viewer.updating) return;
    viewer.inspected = viewer.cy.$(":selected").first().id() || null;
    viewer.highlight();
    viewer.renderSelection();
  });
  viewer.cy.on("tap", (ev) => {
    if (ev.target === viewer.cy) {
      viewer.cy.elements(":selected").unselect();
      viewer.inspected = null;
      viewer.highlight();
      viewer.renderSelection();
    }
  });
  viewer.cy.on("grab", "node", (ev) => {
    const n = ev.target,
      a = viewer.data.assemblies[n.id()];
    viewer.drag = {
      id: n.id(),
      start: { ...n.position() },
      rectangles: viewer.presentation
        ? movingRectangles(viewer.data, viewer.presentation, n.id())
        : undefined,
      members:
        a && !viewer.collapsed.has(n.id())
          ? descendants(viewer.data, n.id())
              .map((id) => viewer.cy.getElementById(id))
              .filter((m) => m.length && !m.hasClass("hidden"))
              .map((m) => ({ id: m.id(), position: { ...m.position() } }))
          : [],
    };
  });
  viewer.cy.on("drag", "node", (ev) => {
    if (viewer.drag?.id !== ev.target.id()) return;
    if (viewer.presentation) {
      viewer.drag.latest = { ...ev.target.position() };
      if (viewer.dragFrame == null)
        viewer.dragFrame = requestAnimationFrame(() => {
          viewer.dragFrame = null;
          flushPresentationDrag(viewer);
        });
      return;
    }
    const pos = ev.target.position(),
      dx = pos.x - viewer.drag.start.x,
      dy = pos.y - viewer.drag.start.y;
    viewer.updating = true;
    viewer.cy.batch(() =>
      viewer.drag.members.forEach((m) => {
        const p = { x: m.position.x + dx, y: m.position.y + dy };
        viewer.cy.getElementById(m.id).position(p);
        if (viewer.data.assemblies[m.id]) viewer.compactPositions[m.id] = { ...p };
      }),
    );
    if (viewer.data.assemblies[viewer.drag.id])
      viewer.compactPositions[viewer.drag.id] = { ...pos };
    viewer.updating = false;
    viewer.syncBoxes();
  });
  viewer.cy.on("free", "node", () => {
    if (viewer.dragFrame != null) cancelAnimationFrame(viewer.dragFrame);
    viewer.dragFrame = null;
    flushPresentationDrag(viewer);
    viewer.drag = null;
    viewer.syncBoxes();
  });
  viewer.cy.on("position", "node", (ev) => {
    if (viewer.syncing || viewer.updating || viewer.drag || viewer.layoutMode) return;
    if (viewer.data.assemblies[ev.target.id()] && !ev.target.hasClass("frame"))
      viewer.compactPositions[ev.target.id()] = { ...ev.target.position() };
    if (viewer.presentation) {
      const n = ev.target,
        r = viewer.presentation.rectangles[n.id()];
      viewer.presentation.rectangles[n.id()] = {
        ...r,
        x: n.position().x - r.width / 2,
        y: n.position().y - r.height / 2,
      };
      viewer.presentation.adjusted = true;
    }
    viewer.syncBoxes();
  });
  viewer.setupFilters();
  viewer.showMembership = !viewer.data.savedLayout;
  viewer.syncFilters();
  viewer.focusIds = viewer.data.initialFocus
    ? new Set([
        viewer.data.initialFocus,
        ...viewer.data.assemblies[viewer.data.initialFocus].entities,
      ])
    : null;
  viewer.updating = false;
  viewer.applyVisibility();
  viewer.fit();
  viewer.$("notes").replaceChildren();
  viewer.data.notes.forEach((n) => viewer.make("p", n, viewer.$("notes")));
  viewer.$("diagnostics").replaceChildren();
  const diag = viewer.data.diagnostics;
  if (diag.ambiguousParents.length || diag.containmentCycles.length) {
    const host = viewer.make(
      "p",
      `${diag.ambiguousParents.length} object(s) with multiple containment parents; ${diag.containmentCycles.length} in containment cycles. No display parent was chosen.`,
      viewer.$("diagnostics"),
      "issue",
    );
    for (const id of new Set([
      ...diag.ambiguousParents,
      ...diag.containmentCycles,
    ]))
      viewer.nav(host, viewer.label(id), id);
  }
  viewer.$("anchors").disabled =
    Boolean(viewer.data.savedLayout) || !viewer.data.anchors.length;
  viewer.$("anchors").checked = false;
  viewer.selectLinkedObject();
  viewer.metrics.loadMs = performance.now() - start;
  viewer.$("timing").textContent =
    `Loaded in ${viewer.metrics.loadMs.toFixed(0)} ms · ${viewer.data.savedLayout ? "saved starting layout · draggable" : "reference arrangement"}`;
}
export async function relayout(viewer: Viewer) {
  if (viewer.data.savedLayout) return;
  const start = performance.now();
  viewer.$("relayout").disabled = true;
  viewer.layoutMode = true;
  viewer.syncBoxes();
  const anchors = viewer.$("anchors").checked
    ? viewer.data.anchors
        .filter((id) => !viewer.cy.getElementById(id).hasClass("hidden"))
        .map((id) => ({
          nodeId: id,
          position: { ...viewer.cy.getElementById(id).position() },
        }))
    : [];
  const options: cytoscape.LayoutOptions & {
    fixedNodeConstraint?: unknown;
    alignmentConstraint?: unknown;
    [key: string]: unknown;
  } = {
    name: "fcose",
    quality: "proof",
    randomize: false,
    animate: false,
    nodeDimensionsIncludeLabels: true,
    packComponents: false,
    fit: false,
    nodeRepulsion: 6500,
    idealEdgeLength: 130,
    numIter: 1500,
  };
  if (anchors.length) {
    options.fixedNodeConstraint = anchors;
    if (viewer.data.alignment)
      options.alignmentConstraint = {
        vertical: viewer.data.alignment.vertical.filter((g) =>
          g.every((id) => !viewer.cy.getElementById(id).hasClass("hidden")),
        ),
      };
  }
  try {
    await new Promise((resolve, reject) => {
      try {
        viewer
          .visible()
          .layout({ ...options, stop: resolve })
          .run();
      } catch (e) {
        reject(e);
      }
    });
    for (const id of Object.keys(viewer.data.assemblies))
      viewer.compactPositions[id] = { ...viewer.cy.getElementById(id).position() };
    viewer.metrics.layoutMs = performance.now() - start;
    viewer.$("timing").textContent =
      `fCoSE · ${viewer.metrics.layoutMs.toFixed(0)} ms${anchors.length ? " · fixed anchors" : ""}`;
  } finally {
    viewer.layoutMode = false;
    viewer.syncBoxes();
    viewer.fit();
    viewer.$("relayout").disabled = false;
  }
}
export function setMode(viewer: Viewer, next) {
  if (viewer.data.savedLayout && next !== "outlines") return;
  viewer.mode = next;
  viewer.$("outlines").classList.toggle("active", next === "outlines");
  viewer.$("membership").classList.toggle("active", next === "membership");
  viewer.syncBoxes();
}

function flushPresentationDrag(viewer: Viewer) {
  const d = viewer.drag;
  if (!viewer.presentation || !d?.latest) return;
  translate(
    viewer.presentation,
    d.rectangles,
    d.latest.x - d.start.x,
    d.latest.y - d.start.y,
  );
  viewer.syncBoxes();
}
