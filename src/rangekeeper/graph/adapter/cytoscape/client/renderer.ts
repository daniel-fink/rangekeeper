import { styles } from "./styles";
import type cytoscape from "cytoscape";
import type { ViewerContext } from "./context";
import * as fourPortRouting from "./routing";
import { projectCollapse } from "./projection";
import { assemblyOrder, descendants, revealPath } from "./membership";
export function updateCounts(ctx: ViewerContext) {
  ctx.$("counts").textContent =
    `${ctx.visible().nodes().length} / ${ctx.cy.nodes().length} objects · ${ctx.visible().edges().length} displayed connections`;
}
export function highlight(ctx: ViewerContext) {
  ctx.cy.elements().removeClass("member");
  const assembly = ctx.data.assemblies[ctx.inspected];
  if (!assembly) return;
  const ids = new Set([...assembly.entities, ...assembly.relationships]);
  ctx.cy.elements().forEach((e) => {
    if (
      ids.has(e.id()) ||
      (e.data("connector") === "summary" &&
        e.data("originalIds").some((id) => ids.has(id)))
    )
      e.addClass("member");
  });
}
export function applyVisibility(ctx: ViewerContext) {
  const start = performance.now();
  ctx.updating = true;
  ctx.projection = projectCollapse(ctx.data, ctx.collapsed, ctx.filters);
  const hidden = new Set(ctx.projection.hiddenIds);
  const edges = new Map(ctx.projection.edges.map((e) => [e.id, e]));
  ctx.cy.batch(() => {
    ctx.cy.edges("[?displayOnly]").remove();
    ctx.cy.add(
      ctx.projection.edges
        .filter((e) => e.displayOnly)
        .map((e) => ({ data: e })),
    );
    ctx.cy.nodes().forEach((n) => {
      n.toggleClass(
        "hidden",
        hidden.has(n.id()) ||
          Boolean(ctx.focusIds && !ctx.focusIds.has(n.id())),
      );
    });
    ctx.cy.edges().forEach((e) => {
      e.toggleClass(
        "hidden",
        !edges.has(e.id()) ||
          e.source().hasClass("hidden") ||
          e.target().hasClass("hidden") ||
          (e.data("connector") === "membership" && !ctx.showMembership),
      );
    });
    ctx.cy.elements(":selected").unselect();
    const selected = ctx.cy.getElementById(ctx.inspected || "");
    if (selected.length && !selected.hasClass("hidden")) selected.select();
    if (ctx.inspected && !selected.length && !ctx.data.details[ctx.inspected])
      ctx.inspected = null;
  });
  ctx.updating = false;
  ctx.syncBoxes();
  ctx.highlight();
  ctx.renderSelection();
  ctx.updateCounts();
  ctx.metrics.filterMs = performance.now() - start;
}
export function select(ctx: ViewerContext, id) {
  const start = performance.now(),
    e = ctx.cy.getElementById(id);
  if (!e.length) return;
  ctx.updating = true;
  ctx.cy.elements(":selected").unselect();
  ctx.inspected = id;
  if (!e.hasClass("hidden")) e.select();
  ctx.updating = false;
  ctx.highlight();
  ctx.renderSelection();
  ctx.metrics.selectionMs = performance.now() - start;
}
export function syncFilters(ctx: ViewerContext) {
  document
    .querySelectorAll<HTMLInputElement>("#filters input")
    .forEach((i) => (i.checked = ctx.filters.has(i.value)));
  ctx.$("member-links").checked = ctx.showMembership;
}
export function setupFilters(ctx: ViewerContext) {
  ctx.$("filters").replaceChildren();
  const types = [
    ...new Set(
      ctx.data.elements
        .filter((e) => "source" in e.data)
        .map((e) => e.data.type),
    ),
  ];
  ctx.filters = new Set(types);
  for (const type of types) {
    const l = ctx.make("label", undefined, ctx.$("filters")),
      input = ctx.make("input", undefined, l);
    input.type = "checkbox";
    input.value = type;
    input.checked = true;
    ctx.make(
      "span",
      ctx.data.elements.find((e) => "source" in e.data && e.data.type === type)
        .data.label,
      l,
    );
    input.onchange = () => {
      ctx.pushHistory();
      input.checked ? ctx.filters.add(type) : ctx.filters.delete(type);
      ctx.applyVisibility();
    };
  }
}
export function loadDataset(ctx: ViewerContext, index) {
  const start = performance.now();
  ctx.updating = true;
  if (ctx.cy) ctx.cy.destroy();
  ctx.portChoices = new Map();
  ctx.routes = new Map();
  ctx.data = ctx.datasets[index];
  ctx.inspected = null;
  ctx.collapsed = new Set();
  ctx.history = [];
  ctx.drag = null;
  Object.keys(ctx.metrics).forEach((key) => (ctx.metrics[key] = 0));
  ctx.$("dataset").value = String(index);
  ctx.$("back").disabled = true;
  ctx.$("search").value = "";
  ctx.$("results").replaceChildren();
  ctx.compactPositions = Object.fromEntries(
    Object.keys(ctx.data.assemblies).map((id) => [
      id,
      { ...ctx.data.positions[id] },
    ]),
  );
  const elements = structuredClone(ctx.data.elements);
  for (const e of elements)
    if ("source" in e.data) e.data.connector = "domain";
    else e.data.title = e.data.label;
  ctx.cy = (globalThis.cytoscape as typeof import("cytoscape"))({
    container: ctx.$("cy"),
    elements,
    layout: { name: "preset" },
    selectionType: "single",
    minZoom: 0.04,
    maxZoom: 4,
    wheelSensitivity: 0.2,
    style: styles,
  });
  for (const [id] of Object.entries(ctx.data.assemblies))
    ctx.cy
      .getElementById(id)
      .data({ boxWidth: 170, boxHeight: 42, bandStops: "0% 85% 85% 100%" });
  ctx.cy.nodes().forEach((n) => {
    if (ctx.memberships(n.id()).length > 1) n.addClass("shared");
  });
  ctx.cy.on("select unselect", "node,edge", () => {
    if (ctx.updating) return;
    ctx.inspected = ctx.cy.$(":selected").first().id() || null;
    ctx.highlight();
    ctx.renderSelection();
  });
  ctx.cy.on("tap", (ev) => {
    if (ev.target === ctx.cy) {
      ctx.cy.elements(":selected").unselect();
      ctx.inspected = null;
      ctx.highlight();
      ctx.renderSelection();
    }
  });
  ctx.cy.on("grab", "node", (ev) => {
    const n = ev.target,
      a = ctx.data.assemblies[n.id()];
    ctx.drag = {
      id: n.id(),
      start: { ...n.position() },
      members:
        a && !ctx.collapsed.has(n.id())
          ? descendants(ctx.data, n.id())
              .map((id) => ctx.cy.getElementById(id))
              .filter((m) => m.length && !m.hasClass("hidden"))
              .map((m) => ({ id: m.id(), position: { ...m.position() } }))
          : [],
    };
  });
  ctx.cy.on("drag", "node", (ev) => {
    if (ctx.drag?.id !== ev.target.id()) return;
    const pos = ev.target.position(),
      dx = pos.x - ctx.drag.start.x,
      dy = pos.y - ctx.drag.start.y;
    ctx.updating = true;
    ctx.cy.batch(() =>
      ctx.drag.members.forEach((m) => {
        const p = { x: m.position.x + dx, y: m.position.y + dy };
        ctx.cy.getElementById(m.id).position(p);
        if (ctx.data.assemblies[m.id]) ctx.compactPositions[m.id] = { ...p };
      }),
    );
    if (ctx.data.assemblies[ctx.drag.id])
      ctx.compactPositions[ctx.drag.id] = { ...pos };
    ctx.updating = false;
    ctx.syncBoxes();
  });
  ctx.cy.on("free", "node", () => {
    ctx.drag = null;
    ctx.syncBoxes();
  });
  ctx.cy.on("position", "node", (ev) => {
    if (ctx.syncing || ctx.updating || ctx.drag || ctx.layoutMode) return;
    if (ctx.data.assemblies[ev.target.id()] && !ev.target.hasClass("frame"))
      ctx.compactPositions[ev.target.id()] = { ...ev.target.position() };
    ctx.syncBoxes();
  });
  ctx.setupFilters();
  ctx.showMembership = true;
  ctx.syncFilters();
  ctx.focusIds = ctx.data.initialFocus
    ? new Set([
        ctx.data.initialFocus,
        ...ctx.data.assemblies[ctx.data.initialFocus].entities,
      ])
    : null;
  ctx.updating = false;
  ctx.applyVisibility();
  ctx.fit();
  ctx.$("notes").replaceChildren();
  ctx.data.notes.forEach((n) => ctx.make("p", n, ctx.$("notes")));
  ctx.$("diagnostics").replaceChildren();
  const diag = ctx.data.diagnostics;
  if (diag.ambiguousParents.length || diag.containmentCycles.length) {
    const host = ctx.make(
      "p",
      `${diag.ambiguousParents.length} object(s) with multiple containment parents; ${diag.containmentCycles.length} in containment cycles. No display parent was chosen.`,
      ctx.$("diagnostics"),
      "issue",
    );
    for (const id of new Set([
      ...diag.ambiguousParents,
      ...diag.containmentCycles,
    ]))
      ctx.nav(host, ctx.label(id), id);
  }
  ctx.$("anchors").disabled = !ctx.data.anchors.length;
  ctx.$("anchors").checked = false;
  ctx.selectLinkedObject();
  ctx.metrics.loadMs = performance.now() - start;
  ctx.$("timing").textContent =
    `Loaded in ${ctx.metrics.loadMs.toFixed(0)} ms · reference arrangement`;
}
export async function relayout(ctx: ViewerContext) {
  const start = performance.now();
  ctx.$("relayout").disabled = true;
  ctx.layoutMode = true;
  ctx.syncBoxes();
  const anchors = ctx.$("anchors").checked
    ? ctx.data.anchors
        .filter((id) => !ctx.cy.getElementById(id).hasClass("hidden"))
        .map((id) => ({
          nodeId: id,
          position: { ...ctx.cy.getElementById(id).position() },
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
    if (ctx.data.alignment)
      options.alignmentConstraint = {
        vertical: ctx.data.alignment.vertical.filter((g) =>
          g.every((id) => !ctx.cy.getElementById(id).hasClass("hidden")),
        ),
      };
  }
  try {
    await new Promise((resolve, reject) => {
      try {
        ctx
          .visible()
          .layout({ ...options, stop: resolve })
          .run();
      } catch (e) {
        reject(e);
      }
    });
    for (const id of Object.keys(ctx.data.assemblies))
      ctx.compactPositions[id] = { ...ctx.cy.getElementById(id).position() };
    ctx.metrics.layoutMs = performance.now() - start;
    ctx.$("timing").textContent =
      `fCoSE · ${ctx.metrics.layoutMs.toFixed(0)} ms${anchors.length ? " · fixed anchors" : ""}`;
  } finally {
    ctx.layoutMode = false;
    ctx.syncBoxes();
    ctx.fit();
    ctx.$("relayout").disabled = false;
  }
}
export function setMode(ctx: ViewerContext, next) {
  ctx.mode = next;
  ctx.$("outlines").classList.toggle("active", next === "outlines");
  ctx.$("membership").classList.toggle("active", next === "membership");
  ctx.syncBoxes();
}
