import { isEdge } from "./document";
import type { ViewerContext } from "./context";
import * as fourPortRouting from "./routing";
import { projectCollapse } from "./projection";
import { assemblyOrder, descendants, revealPath } from "./membership";
export function pushHistory(ctx: ViewerContext) {
  ctx.history.push(ctx.snapshot());
  ctx.$("back").disabled = false;
}
export function changeCollapse(ctx: ViewerContext, ids, value) {
  ctx.pushHistory();
  for (const id of ids)
    value ? ctx.collapsed.add(id) : ctx.collapsed.delete(id);
  ctx.applyVisibility();
}
export function fit(ctx: ViewerContext) {
  if (ctx.visible().length) ctx.cy.fit(ctx.visible(), 55);
}
export function focusOn(ctx: ViewerContext, id) {
  ctx.pushHistory();
  const assembly = ctx.data.assemblies[id];
  if (assembly) ctx.focusIds = new Set([id, ...descendants(ctx.data, id)]);
  else {
    const element = ctx.cy.getElementById(id);
    ctx.focusIds = new Set([id]);
    if (element.isEdge()) {
      ctx.focusIds.add(element.data("source"));
      ctx.focusIds.add(element.data("target"));
    }
    for (const item of ctx.data.elements) {
      const edge = item.data;
      if (isEdge(edge) && (edge.source === id || edge.target === id)) {
        ctx.focusIds.add(edge.source);
        ctx.focusIds.add(edge.target);
      }
    }
    for (const [aid] of ctx.memberships(id)) ctx.focusIds.add(aid);
  }
  // A collapsed representative can provide context for a hidden focused endpoint.
  for (const nid of [...ctx.focusIds])
    for (const aid of ctx.projection.memberships[nid] || [])
      if (ctx.collapsed.has(aid)) ctx.focusIds.add(aid);
  ctx.applyVisibility();
  ctx.fit();
}
export function reset(ctx: ViewerContext) {
  ctx.pushHistory();
  ctx.focusIds = null;
  ctx.applyVisibility();
  ctx.fit();
}
export function restore(ctx: ViewerContext) {
  ctx.updating = true;
  ctx.cy.batch(() =>
    ctx.cy.nodes().forEach((n) => {
      n.position({ ...ctx.data.positions[n.id()] });
    }),
  );
  for (const id of Object.keys(ctx.data.assemblies))
    ctx.compactPositions[id] = { ...ctx.data.positions[id] };
  ctx.updating = false;
  ctx.syncBoxes();
  ctx.$("timing").textContent = "Reference arrangement restored";
}
export function reveal(ctx: ViewerContext, id, assemblyId) {
  ctx.pushHistory();
  if (assemblyId) {
    for (const ancestor of revealPath(ctx.data, assemblyId))
      ctx.collapsed.delete(ancestor);
    ctx.collapsed.delete(assemblyId);
  }
  if (ctx.focusIds) {
    ctx.focusIds.add(id);
    if (assemblyId) {
      ctx.focusIds.add(assemblyId);
      for (const mid of ctx.data.assemblies[assemblyId].entities)
        ctx.focusIds.add(mid);
    }
  }
  ctx.applyVisibility();
  ctx.select(id);
  ctx.fit();
}
export function selectLinkedObject(ctx: ViewerContext) {
  if (!location.hash) return;
  const params = new URLSearchParams(location.hash.slice(1)),
    ids = params.getAll("select");
  if (
    [...params.keys()].some((k) => k !== "select") ||
    ids.length !== 1 ||
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
      ids[0],
    ) ||
    !ctx.data.details[ids[0]]
  ) {
    ctx.make(
      "p",
      "This review link does not identify an object in the current graph.",
      ctx.$("diagnostics"),
      "issue",
    );
    return;
  }
  ctx.select(ids[0]);
}
