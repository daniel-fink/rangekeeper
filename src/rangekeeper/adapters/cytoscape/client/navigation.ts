import { initialPresentation } from "./presentation";
import { isEdge } from "./document";
import type { Viewer } from "./context";
import * as fourPortRouting from "./routing";
import { projectCollapse } from "./projection";
import { assemblyOrder, descendants, revealPath } from "./membership";
export function remember(viewer: Viewer) {
  viewer.history.push(viewer.snapshot());
  viewer.$("back").disabled = false;
}
export function collapse(viewer: Viewer, ids, value) {
  viewer.remember();
  for (const id of ids)
    value ? viewer.collapsed.add(id) : viewer.collapsed.delete(id);
  viewer.applyVisibility();
}
export function fit(viewer: Viewer) {
  if (viewer.visible().length) viewer.cy.fit(viewer.visible(), 55);
}
export function focus(viewer: Viewer, id) {
  viewer.remember();
  const assembly = viewer.data.assemblies[id];
  if (assembly) viewer.focusIds = new Set([id, ...descendants(viewer.data, id)]);
  else {
    const element = viewer.cy.getElementById(id);
    viewer.focusIds = new Set([id]);
    if (element.isEdge()) {
      viewer.focusIds.add(element.data("source"));
      viewer.focusIds.add(element.data("target"));
    }
    for (const item of viewer.data.elements) {
      const edge = item.data;
      if (isEdge(edge) && (edge.source === id || edge.target === id)) {
        viewer.focusIds.add(edge.source);
        viewer.focusIds.add(edge.target);
      }
    }
    for (const [aid] of viewer.memberships(id)) viewer.focusIds.add(aid);
  }
  // A collapsed representative can provide context for a hidden focused endpoint.
  for (const nid of [...viewer.focusIds])
    for (const aid of viewer.projection.memberships[nid] || [])
      if (viewer.collapsed.has(aid)) viewer.focusIds.add(aid);
  viewer.applyVisibility();
  viewer.fit();
}
export function reset(viewer: Viewer) {
  viewer.remember();
  viewer.focusIds = null;
  viewer.applyVisibility();
  viewer.fit();
}
export function restore(viewer: Viewer) {
  if (viewer.data.savedLayout) {
    if (viewer.dragFrame != null) cancelAnimationFrame(viewer.dragFrame);
    viewer.dragFrame = null;
    viewer.drag = null;
    viewer.presentation = initialPresentation(viewer.data);
    viewer.collapsed.clear();
    viewer.focusIds = null;
    viewer.applyVisibility();
    viewer.$("timing").textContent = "Checked saved layout restored";
    return;
  }
  viewer.updating = true;
  viewer.cy.batch(() =>
    viewer.cy.nodes().forEach((n) => {
      n.position({ ...viewer.data.positions[n.id()] });
    }),
  );
  for (const id of Object.keys(viewer.data.assemblies))
    viewer.compactPositions[id] = { ...viewer.data.positions[id] };
  viewer.updating = false;
  viewer.syncBoxes();
  viewer.$("timing").textContent = "Reference arrangement restored";
}
export function reveal(viewer: Viewer, id, assemblyId) {
  viewer.remember();
  if (assemblyId) {
    for (const ancestor of revealPath(viewer.data, assemblyId))
      viewer.collapsed.delete(ancestor);
    viewer.collapsed.delete(assemblyId);
  }
  if (viewer.focusIds) {
    viewer.focusIds.add(id);
    if (assemblyId) {
      viewer.focusIds.add(assemblyId);
      for (const mid of viewer.data.assemblies[assemblyId].entities)
        viewer.focusIds.add(mid);
    }
  }
  viewer.applyVisibility();
  viewer.select(id);
  viewer.fit();
}
export function selectLinkedObject(viewer: Viewer) {
  if (!location.hash) return;
  const params = new URLSearchParams(location.hash.slice(1)),
    ids = params.getAll("select");
  if (
    [...params.keys()].some((k) => k !== "select") ||
    ids.length !== 1 ||
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
      ids[0],
    ) ||
    !viewer.data.details[ids[0]]
  ) {
    viewer.make(
      "p",
      "This review link does not identify an object in the current graph.",
      viewer.$("diagnostics"),
      "issue",
    );
    return;
  }
  viewer.select(ids[0]);
}
