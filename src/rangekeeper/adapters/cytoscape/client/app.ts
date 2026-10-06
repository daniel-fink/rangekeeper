/** Offline entry point. Owns one explicit viewer context; no domain mutations. */
import type { Viewer } from "./context";
import * as geometry from "./geometry";
import * as navigation from "./navigation";
import * as inspector from "./inspector";
import * as renderer from "./renderer";
const viewer = {} as Viewer;
viewer.connectionCentre = (...args) => geometry.connectionCentre(viewer, ...args);
viewer.headerEndpoint = (...args) => geometry.headerEndpoint(viewer, ...args);
viewer.endpoint = (...args) => geometry.endpoint(viewer, ...args);
viewer.connectionGeometry = (...args) => geometry.connectionGeometry(viewer, ...args);
viewer.updateConnections = (...args) => geometry.updateConnections(viewer, ...args);
viewer.syncBoxes = (...args) => geometry.syncBoxes(viewer, ...args);
viewer.remember = (...args) => navigation.remember(viewer, ...args);
viewer.collapse = (...args) => navigation.collapse(viewer, ...args);
viewer.fit = (...args) => navigation.fit(viewer, ...args);
viewer.focus = (...args) => navigation.focus(viewer, ...args);
viewer.reset = (...args) => navigation.reset(viewer, ...args);
viewer.restore = (...args) => navigation.restore(viewer, ...args);
viewer.reveal = (...args) => navigation.reveal(viewer, ...args);
viewer.selectLinkedObject = (...args) =>
  navigation.selectLinkedObject(viewer, ...args);
viewer.valueText = (...args) => inspector.valueText(viewer, ...args);
viewer.evidence = (...args) => inspector.evidence(viewer, ...args);
viewer.nav = (...args) => inspector.nav(viewer, ...args);
viewer.renderSelection = (...args) => inspector.renderSelection(viewer, ...args);
viewer.highlight = (...args) => renderer.highlight(viewer, ...args);
viewer.updateCounts = (...args) => renderer.updateCounts(viewer, ...args);
viewer.applyVisibility = (...args) => renderer.applyVisibility(viewer, ...args);
viewer.select = (id) => renderer.select(viewer, id);
viewer.syncFilters = (...args) => renderer.syncFilters(viewer, ...args);
viewer.setupFilters = (...args) => renderer.setupFilters(viewer, ...args);
viewer.loadDataset = (...args) => renderer.loadDataset(viewer, ...args);
viewer.relayout = (...args) => renderer.relayout(viewer, ...args);
viewer.setMode = (...args) => renderer.setMode(viewer, ...args);
viewer.datasets = JSON.parse(
  document.getElementById("graph-data").textContent,
).datasets;
viewer.$ = (id) => document.getElementById(id) as ReturnType<Viewer["$"]>;
viewer.make = (tag, text, parent, cls) => {
  const e = document.createElement(tag);
  if (text !== undefined) e.textContent = String(text);
  if (cls) e.className = cls;
  if (parent) parent.append(e);
  return e;
};
viewer.HEADER = 36;
viewer.PAD = 24;
viewer.labelMeasure = document.createElement("canvas").getContext("2d");
viewer.cy = undefined;
viewer.data = undefined;
viewer.projection = undefined;
viewer.inspected = null;
viewer.focusIds = null;
viewer.history = [];
viewer.collapsed = new Set();
viewer.filters = new Set();
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
viewer.portChoices = new Map();
viewer.routes = new Map();
viewer.metrics = { loadMs: 0, layoutMs: 0, selectionMs: 0, filterMs: 0 };
viewer.label = (id) =>
  viewer.data.details[id]?.name || viewer.cy.getElementById(id).data("label") || id;
viewer.memberships = (id) =>
  Object.entries(viewer.data.assemblies).filter(
    ([, a]) => a.entities.includes(id) || a.relationships.includes(id),
  );
viewer.visible = () => viewer.cy.elements().filter((e) => !e.hasClass("hidden"));
viewer.snapshot = () => ({
  focus: viewer.focusIds ? [...viewer.focusIds] : null,
  filters: [...viewer.filters],
  collapsed: [...viewer.collapsed],
  showMembership: viewer.showMembership,
});
viewer.routingStyle =
  "curve-style control-point-distances control-point-weights control-point-step-size edge-distances loop-direction loop-sweep text-rotation";
("use strict");
viewer.datasets.forEach((d, i) => {
  const o = viewer.make("option", d.name, viewer.$("dataset"));
  o.value = String(i);
});
viewer.$("dataset").onchange = () =>
  viewer.loadDataset(Number(viewer.$("dataset").value));
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
viewer.$("collapse-all").onclick = () =>
  viewer.collapse(Object.keys(viewer.data.assemblies), true);
viewer.$("expand-all").onclick = () =>
  viewer.collapse(Object.keys(viewer.data.assemblies), false);
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
  viewer.cy
    .nodes()
    .filter((n) =>
      [n.data("label"), n.data("code"), n.id()].some((v) =>
        (v || "").toLowerCase().includes(q),
      ),
    )
    .slice(0, 8)
    .forEach((n) => {
      const button = viewer.make(
        "button",
        `${n.data("label")} · ${n.data("code")}`,
        viewer.$("results"),
      );
      button.onclick = () => {
        viewer.select(n.id());
        if (!n.hasClass("hidden")) {
          const bb = n.renderedBoundingBox();
          if (
            bb.x1 < 0 ||
            bb.y1 < 0 ||
            bb.x2 > viewer.cy.width() ||
            bb.y2 > viewer.cy.height()
          )
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
  collapse: viewer.collapse,
};

window.addEventListener("hashchange", viewer.selectLinkedObject);
viewer.loadDataset(0);
