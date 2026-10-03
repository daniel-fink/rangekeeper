/** Offline entry point. Owns one explicit viewer context; no domain mutations. */
import type { ViewerContext } from "./context";
import * as geometry from "./geometry";
import * as navigation from "./navigation";
import * as inspector from "./inspector";
import * as renderer from "./renderer";
const ctx = {} as ViewerContext;
ctx.connectionCentre = (...args) => geometry.connectionCentre(ctx, ...args);
ctx.headerEndpoint = (...args) => geometry.headerEndpoint(ctx, ...args);
ctx.endpoint = (...args) => geometry.endpoint(ctx, ...args);
ctx.connectionGeometry = (...args) => geometry.connectionGeometry(ctx, ...args);
ctx.updateConnections = (...args) => geometry.updateConnections(ctx, ...args);
ctx.syncBoxes = (...args) => geometry.syncBoxes(ctx, ...args);
ctx.pushHistory = (...args) => navigation.pushHistory(ctx, ...args);
ctx.changeCollapse = (...args) => navigation.changeCollapse(ctx, ...args);
ctx.fit = (...args) => navigation.fit(ctx, ...args);
ctx.focusOn = (...args) => navigation.focusOn(ctx, ...args);
ctx.reset = (...args) => navigation.reset(ctx, ...args);
ctx.restore = (...args) => navigation.restore(ctx, ...args);
ctx.reveal = (...args) => navigation.reveal(ctx, ...args);
ctx.selectLinkedObject = (...args) =>
  navigation.selectLinkedObject(ctx, ...args);
ctx.valueText = (...args) => inspector.valueText(ctx, ...args);
ctx.evidence = (...args) => inspector.evidence(ctx, ...args);
ctx.nav = (...args) => inspector.nav(ctx, ...args);
ctx.renderSelection = (...args) => inspector.renderSelection(ctx, ...args);
ctx.highlight = (...args) => renderer.highlight(ctx, ...args);
ctx.updateCounts = (...args) => renderer.updateCounts(ctx, ...args);
ctx.applyVisibility = (...args) => renderer.applyVisibility(ctx, ...args);
ctx.select = (id) => renderer.select(ctx, id);
ctx.syncFilters = (...args) => renderer.syncFilters(ctx, ...args);
ctx.setupFilters = (...args) => renderer.setupFilters(ctx, ...args);
ctx.loadDataset = (...args) => renderer.loadDataset(ctx, ...args);
ctx.relayout = (...args) => renderer.relayout(ctx, ...args);
ctx.setMode = (...args) => renderer.setMode(ctx, ...args);
ctx.datasets = JSON.parse(
  document.getElementById("graph-data").textContent,
).datasets;
ctx.$ = (id) => document.getElementById(id) as ReturnType<ViewerContext["$"]>;
ctx.make = (tag, text, parent, cls) => {
  const e = document.createElement(tag);
  if (text !== undefined) e.textContent = String(text);
  if (cls) e.className = cls;
  if (parent) parent.append(e);
  return e;
};
ctx.HEADER = 36;
ctx.PAD = 24;
ctx.labelMeasure = document.createElement("canvas").getContext("2d");
ctx.cy = undefined;
ctx.data = undefined;
ctx.projection = undefined;
ctx.inspected = null;
ctx.focusIds = null;
ctx.history = [];
ctx.collapsed = new Set();
ctx.filters = new Set();
ctx.mode = "outlines";
ctx.showMembership = true;
ctx.fourPorts = true;
ctx.compactPositions = {};
ctx.drag = null;
ctx.syncing = false;
ctx.updating = false;
ctx.layoutMode = false;
ctx.portChoices = new Map();
ctx.routes = new Map();
ctx.metrics = { loadMs: 0, layoutMs: 0, selectionMs: 0, filterMs: 0 };
ctx.label = (id) =>
  ctx.data.details[id]?.name || ctx.cy.getElementById(id).data("label") || id;
ctx.memberships = (id) =>
  Object.entries(ctx.data.assemblies).filter(
    ([, a]) => a.entities.includes(id) || a.relationships.includes(id),
  );
ctx.visible = () => ctx.cy.elements().filter((e) => !e.hasClass("hidden"));
ctx.snapshot = () => ({
  focus: ctx.focusIds ? [...ctx.focusIds] : null,
  filters: [...ctx.filters],
  collapsed: [...ctx.collapsed],
  showMembership: ctx.showMembership,
});
ctx.routingStyle =
  "curve-style control-point-distances control-point-weights control-point-step-size edge-distances loop-direction loop-sweep text-rotation";
("use strict");
ctx.datasets.forEach((d, i) => {
  const o = ctx.make("option", d.name, ctx.$("dataset"));
  o.value = String(i);
});
ctx.$("dataset").onchange = () =>
  ctx.loadDataset(Number(ctx.$("dataset").value));
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
ctx.$("collapse-all").onclick = () =>
  ctx.changeCollapse(Object.keys(ctx.data.assemblies), true);
ctx.$("expand-all").onclick = () =>
  ctx.changeCollapse(Object.keys(ctx.data.assemblies), false);
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
  ctx.cy
    .nodes()
    .filter((n) =>
      [n.data("label"), n.data("code"), n.id()].some((v) =>
        (v || "").toLowerCase().includes(q),
      ),
    )
    .slice(0, 8)
    .forEach((n) => {
      const button = ctx.make(
        "button",
        `${n.data("label")} · ${n.data("code")}`,
        ctx.$("results"),
      );
      button.onclick = () => {
        ctx.select(n.id());
        if (!n.hasClass("hidden")) {
          const bb = n.renderedBoundingBox();
          if (
            bb.x1 < 0 ||
            bb.y1 < 0 ||
            bb.x2 > ctx.cy.width() ||
            bb.y2 > ctx.cy.height()
          )
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
  changeCollapse: ctx.changeCollapse,
};
window.graphReview = window.spike;
window.addEventListener("hashchange", ctx.selectLinkedObject);
ctx.loadDataset(0);
