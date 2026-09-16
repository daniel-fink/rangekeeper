import type cytoscape from "cytoscape";
import type { ViewerContext } from "./context";
import * as fourPortRouting from "./routing";
import { projectCollapse } from "./projection";
import { assemblyOrder, descendants, revealPath } from "./membership";
export function valueText(ctx: ViewerContext, value) {
  if (value === null) return "Unknown / not supplied";
  if (value && typeof value === "object" && "units" in value)
    return `${ctx.valueText(value.value)} ${value.units}`.trim();
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
export function evidence(ctx: ViewerContext, parent, fact) {
  if (!fact) {
    ctx.make("p", "No Fact attached to this item.", parent, "code");
    return;
  }
  const box = ctx.make("details", undefined, parent);
  ctx.make("summary", `Evidence · ${fact.reconciliation || fact.status}`, box);
  if (fact.reconciliation)
    ctx.make(
      "p",
      `Selected claim is ${fact.reconciliation}. Other claims are retained.`,
      box,
      "issue",
    );
  const visited = new Set();
  const appendClaim = (id, host, depth) => {
    if (visited.has(id)) {
      ctx.make("p", `Previously shown claim ${id}`, host, "code");
      return;
    }
    visited.add(id);
    const c = ctx.data.claims[id];
    if (!c) return;
    const item = ctx.make("details", undefined, host);
    ctx.make(
      "summary",
      `${c.kind}${fact.selected === id ? " · selected" : ""}`,
      item,
    );
    ctx.make("pre", JSON.stringify(c.value, null, 2), item);
    if (c.method) ctx.make("pre", JSON.stringify(c.method, null, 2), item);
    for (const source of c.sources) {
      if (source.claim) {
        if (depth < 8) appendClaim(source.claim, item, depth + 1);
        else
          ctx.make(
            "p",
            "Further evidence available in the embedded view data.",
            item,
          );
      } else {
        ctx.make("p", source.name, item);
        ctx.make(
          "pre",
          JSON.stringify(
            { reference: source.reference, checksum: source.checksum },
            null,
            2,
          ),
          item,
        );
      }
    }
  };
  fact.claims.forEach((id) => appendClaim(id, box, 0));
}
export function nav(ctx: ViewerContext, parent, text, id) {
  const b = ctx.make("button", text, parent, "nav");
  b.dataset.target = id;
  b.onclick = () => ctx.select(id, true);
  return b;
}
export function renderSelection(ctx: ViewerContext) {
  const host = ctx.$("selection");
  host.replaceChildren();
  ctx.$("focus").disabled = !ctx.inspected;
  if (!ctx.inspected) {
    ctx.make(
      "p",
      "Search for or select any object or connection. Focus and expand only when you choose.",
      host,
      "empty",
    );
    return;
  }
  const element = ctx.cy.getElementById(ctx.inspected),
    d = ctx.data.details[ctx.inspected];
  if (!d && element.length) {
    const edge = element.data();
    ctx.make("h2", edge.label, host);
    ctx.make(
      "p",
      edge.connector === "summary"
        ? "Collapsed relationship summary. This line represents hidden detail; it is not a new domain relationship."
        : "Recorded Assembly membership, shown as a display connector.",
      host,
    );
    ctx.nav(host, `From · ${ctx.label(edge.source)}`, edge.source);
    ctx.nav(host, `To · ${ctx.label(edge.target)}`, edge.target);
    if (edge.membershipPaths?.some((path) => path.length > 2)) {
      ctx.make("h3", "Membership paths", host);
      for (const path of edge.membershipPaths)
        ctx.make("p", path.map(ctx.label).join(" → "), host);
    }
    if (edge.originalIds) {
      ctx.make("h3", "Original relationships", host);
      for (const id of edge.originalIds) {
        const original = ctx.cy.getElementById(id).data();
        ctx.nav(
          host,
          `${ctx.label(original.source)} → ${original.label} → ${ctx.label(original.target)}`,
          id,
        );
        ctx.evidence(host, ctx.data.details[id].fact);
      }
    }
    return;
  }
  if (!d) return;
  ctx.make("h2", element.data("label"), host);
  ctx.make(
    "span",
    element.isEdge()
      ? "Relationship"
      : ctx.data.assemblies[ctx.inspected]
        ? "Assembly"
        : "Entity",
    host,
    "tag",
  );
  if (d.classification?.name !== "Assembly")
    ctx.make("span", d.classification?.name || "Unclassified", host, "tag");
  ctx.make("p", element.data("code") || ctx.inspected, host, "code");
  if (element.hasClass("hidden")) {
    ctx.make(
      "p",
      "Hidden in the current view. Inspection does not expand Assemblies.",
      host,
      "issue",
    );
    if (element.isNode()) {
      const containers = ctx
        .memberships(ctx.inspected)
        .filter(
          ([id]) =>
            ctx.collapsed.has(id) || ctx.projection.hiddenIds.includes(id),
        );
      if (containers.length)
        for (const [id, a] of containers) {
          const b = ctx.make("button", `Reveal in ${a.name}`, host, "nav");
          b.onclick = () => ctx.reveal(ctx.inspected, id);
        }
      else {
        const b = ctx.make("button", "Reveal in view", host, "nav");
        b.onclick = () => ctx.reveal(ctx.inspected);
      }
    }
  }
  const assembly = ctx.data.assemblies[ctx.inspected];
  if (assembly) {
    const b = ctx.make(
      "button",
      ctx.collapsed.has(ctx.inspected)
        ? "Expand Assembly"
        : "Collapse Assembly",
      host,
      "nav",
    );
    b.id = "toggle-collapse";
    b.onclick = () =>
      ctx.changeCollapse([ctx.inspected], !ctx.collapsed.has(ctx.inspected));
    ctx.make(
      "p",
      `${assembly.entities.length} recorded members. Highlighting identifies exact membership; rectangles may also enclose nonmembers.`,
      host,
    );
    const list = ctx.make("details", undefined, host);
    ctx.make("summary", "Exact members", list);
    assembly.entities.forEach((id) => ctx.nav(list, ctx.label(id), id));
  }
  if (
    ctx.data.diagnostics.ambiguousParents.includes(ctx.inspected) ||
    ctx.data.diagnostics.containmentCycles.includes(ctx.inspected)
  )
    ctx.make(
      "p",
      "No unique display hierarchy is assumed. All domain relationships are retained.",
      host,
      "issue",
    );
  for (const key of ["measurements", "labels", "features"]) {
    if (!d[key].length) continue;
    ctx.make("h3", key, host);
    for (const item of d[key]) {
      const dl = ctx.make("dl", undefined, host);
      ctx.make("dt", item.name, dl);
      ctx.make("dd", ctx.valueText(item.value), dl);
      if (item.definition) ctx.make("p", item.definition, host, "code");
      ctx.evidence(host, item.fact);
    }
  }
  const findings = (ctx.data.reviewItems || []).filter((item) =>
    item.targets.includes(ctx.inspected),
  );
  if (findings.length) {
    ctx.make("h3", "Review findings", host);
    for (const item of findings) {
      const row = ctx.make("details", undefined, host);
      ctx.make("summary", `${item.id} · ${item.group} · ${item.kind}`, row);
      ctx.make("p", item.scope, row);
      ctx.make("p", item.explanation, row);
      for (const [name, value] of Object.entries(item.values)) {
        if (
          (name !== "Known subtotal" || value !== null) &&
          (!Array.isArray(value) || value.length)
        )
          ctx.make(
            "p",
            `${name}: ${value === null ? "Unknown" : ctx.valueText(value)}`,
            row,
          );
      }
      for (const reference of item.references)
        ctx.make("p", reference, row, "code");
    }
  }
  if (d.fact) {
    ctx.make("h3", "Object provenance", host);
    ctx.evidence(host, d.fact);
  }
  const groups = ctx.memberships(ctx.inspected);
  if (groups.length) {
    ctx.make("h3", "Member of", host);
    for (const [id, a] of groups) ctx.nav(host, a.name, id);
  }
  if (element.isEdge()) {
    ctx.make("h3", "Endpoints", host);
    ctx.nav(
      host,
      `From · ${ctx.label(element.data("source"))}`,
      element.data("source"),
    );
    ctx.nav(
      host,
      `To · ${ctx.label(element.data("target"))}`,
      element.data("target"),
    );
  } else {
    for (const [direction, edges] of [
      [
        "Incoming",
        (element as cytoscape.NodeSingular).incomers(
          'edge[connector="domain"]',
        ),
      ],
      [
        "Outgoing",
        (element as cytoscape.NodeSingular).outgoers(
          'edge[connector="domain"]',
        ),
      ],
    ] as const) {
      if (!edges.length) continue;
      ctx.make("h3", `${direction} relationships`, host);
      edges.forEach((edge) => {
        const other = direction === "Incoming" ? edge.source() : edge.target();
        ctx.nav(
          host,
          `${edge.data("label")} · ${other.data("label")}${edge.hasClass("hidden") ? " (hidden by view)" : ""}`,
          edge.id(),
        );
      });
    }
  }
}
