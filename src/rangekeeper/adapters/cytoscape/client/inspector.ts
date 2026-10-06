import type cytoscape from "cytoscape";
import type { Viewer } from "./context";
import * as fourPortRouting from "./routing";
import { projectCollapse } from "./projection";
import { assemblyOrder, descendants, revealPath } from "./membership";
export function valueText(viewer: Viewer, value) {
  if (value === null) return "Unknown / not supplied";
  if (value && typeof value === "object" && "units" in value)
    return `${viewer.valueText(value.value)} ${value.units}`.trim();
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
function decisionRecord(claim) {
  if (claim?.method?.code !== "reviewed-decision") return null;
  try {
    const value =
      typeof claim.value === "string" ? JSON.parse(claim.value) : claim.value;
    return value &&
      typeof value.id === "string" &&
      typeof value.text === "string"
      ? value
      : null;
  } catch {
    return null;
  }
}
function renderDecision(viewer: Viewer, claim, host) {
  const decision = decisionRecord(claim);
  if (!decision) return false;
  viewer.make(
    "h4",
    `${decision.id} · ${decision.status || "Status not recorded"}`,
    host,
  );
  viewer.make("p", decision.text, host);
  viewer.make(
    "p",
    `${decision.source || "Attribution not recorded"} · ${decision.date || "Date not recorded"}`,
    host,
  );
  if (viewer.data.reviewUrl === "review.html") {
    const link = document.createElement("a");
    link.textContent = "Open decision and mapping review";
    link.href = "review.html#decision-" + encodeURIComponent(decision.id);
    link.target = "_blank";
    link.rel = "noopener";
    host.append(link);
  }
  return true;
}
export function evidence(viewer: Viewer, parent, fact) {
  if (!fact) {
    viewer.make("p", "No Fact attached to this item.", parent, "code");
    return;
  }
  const box = viewer.make("details", undefined, parent);
  viewer.make("summary", `Evidence · ${fact.reconciliation || fact.status}`, box);
  if (fact.reconciliation)
    viewer.make(
      "p",
      `Selected claim is ${fact.reconciliation}. Other claims are retained.`,
      box,
      "issue",
    );
  // Make every reviewed decision reachable without expanding a deep Claim chain.
  const pending = [...fact.claims],
    seenDecisions = new Set(),
    seenClaims = new Set();
  const decisions = [];
  while (pending.length) {
    const id = pending.pop();
    if (seenClaims.has(id)) continue;
    seenClaims.add(id);
    const claim = viewer.data.claims[id];
    if (!claim) continue;
    const record = decisionRecord(claim);
    if (record && !seenDecisions.has(record.id)) {
      seenDecisions.add(record.id);
      decisions.push(claim);
    }
    for (const source of claim.sources)
      if (source.claim) pending.push(source.claim);
  }
  if (decisions.length) {
    const list = viewer.make("details", undefined, box);
    viewer.make("summary", `Reviewed decisions · ${decisions.length}`, list);
    for (const claim of decisions) renderDecision(viewer, claim, list);
  }
  const visited = new Set();
  const appendClaim = (id, host, depth) => {
    if (visited.has(id)) {
      viewer.make("p", `Previously shown claim ${id}`, host, "code");
      return;
    }
    visited.add(id);
    const c = viewer.data.claims[id];
    if (!c) return;
    const item = viewer.make("details", undefined, host);
    viewer.make(
      "summary",
      `${c.kind}${fact.selected === id ? " · selected" : ""}`,
      item,
    );
    if (!renderDecision(viewer, c, item))
      viewer.make("pre", JSON.stringify(c.value, null, 2), item);
    if (c.method) viewer.make("pre", JSON.stringify(c.method, null, 2), item);
    for (const source of c.sources) {
      if (source.claim) {
        if (depth < 8) appendClaim(source.claim, item, depth + 1);
        else
          viewer.make(
            "p",
            "Further evidence available in the embedded view data.",
            item,
          );
      } else {
        viewer.make("p", source.name, item);
        viewer.make(
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
export function nav(viewer: Viewer, parent, text, id) {
  const b = viewer.make("button", text, parent, "nav");
  b.dataset.target = id;
  b.onclick = () => viewer.select(id, true);
  return b;
}
export function renderSelection(viewer: Viewer) {
  const host = viewer.$("selection");
  host.replaceChildren();
  viewer.$("focus").disabled = !viewer.inspected;
  if (!viewer.inspected) {
    viewer.make(
      "p",
      "Search for or select any object or connection. Focus and expand only when you choose.",
      host,
      "empty",
    );
    return;
  }
  const element = viewer.cy.getElementById(viewer.inspected),
    d = viewer.data.details[viewer.inspected];
  if (!d && element.length) {
    const edge = element.data();
    viewer.make("h2", edge.label, host);
    viewer.make(
      "p",
      edge.connector === "summary"
        ? "Collapsed relationship summary. This line represents hidden detail; it is not a new domain relationship."
        : "Recorded Assembly membership, shown as a display connector.",
      host,
    );
    viewer.nav(host, `From · ${viewer.label(edge.source)}`, edge.source);
    viewer.nav(host, `To · ${viewer.label(edge.target)}`, edge.target);
    if (edge.membershipPaths?.some((path) => path.length > 2)) {
      viewer.make("h3", "Membership paths", host);
      for (const path of edge.membershipPaths)
        viewer.make("p", path.map(viewer.label).join(" → "), host);
    }
    if (edge.originalIds) {
      viewer.make("h3", "Original relationships", host);
      for (const id of edge.originalIds) {
        const original = viewer.cy.getElementById(id).data();
        viewer.nav(
          host,
          `${viewer.label(original.source)} → ${original.label} → ${viewer.label(original.target)}`,
          id,
        );
        viewer.evidence(host, viewer.data.details[id].fact);
      }
    }
    return;
  }
  if (!d) return;
  viewer.make("h2", element.data("label"), host);
  viewer.make(
    "span",
    element.isEdge()
      ? "Relationship"
      : viewer.data.assemblies[viewer.inspected]
        ? "Assembly"
        : "Entity",
    host,
    "tag",
  );
  if (d.classification?.name !== "Assembly")
    viewer.make("span", d.classification?.name || "Unclassified", host, "tag");
  viewer.make("p", element.data("code") || viewer.inspected, host, "code");
  if (element.hasClass("hidden")) {
    viewer.make(
      "p",
      "Hidden in the current view. Inspection does not expand Assemblies.",
      host,
      "issue",
    );
    if (element.isNode()) {
      const containers = viewer
        .memberships(viewer.inspected)
        .filter(
          ([id]) =>
            viewer.collapsed.has(id) || viewer.projection.hiddenIds.includes(id),
        );
      if (containers.length)
        for (const [id, a] of containers) {
          const b = viewer.make("button", `Reveal in ${a.name}`, host, "nav");
          b.onclick = () => viewer.reveal(viewer.inspected, id);
        }
      else {
        const b = viewer.make("button", "Reveal in view", host, "nav");
        b.onclick = () => viewer.reveal(viewer.inspected);
      }
    }
  }
  const assembly = viewer.data.assemblies[viewer.inspected];
  if (assembly) {
    const b = viewer.make(
      "button",
      viewer.collapsed.has(viewer.inspected)
        ? "Expand Assembly"
        : "Collapse Assembly",
      host,
      "nav",
    );
    b.id = "toggle-collapse";
    b.onclick = () =>
      viewer.collapse([viewer.inspected], !viewer.collapsed.has(viewer.inspected));
    viewer.make(
      "p",
      `${assembly.entities.length} recorded members. ${viewer.data.savedLayout ? "Boxes fit visible members and resize as you arrange or change scope. Highlighting identifies direct membership; red outlines flag presentation conflicts." : "Highlighting identifies exact membership; rectangles may also enclose nonmembers."}`,
      host,
    );
    const list = viewer.make("details", undefined, host);
    viewer.make("summary", "Exact members", list);
    assembly.entities.forEach((id) => viewer.nav(list, viewer.label(id), id));
  }
  if (
    viewer.data.diagnostics.ambiguousParents.includes(viewer.inspected) ||
    viewer.data.diagnostics.containmentCycles.includes(viewer.inspected)
  )
    viewer.make(
      "p",
      "No unique display hierarchy is assumed. All domain relationships are retained.",
      host,
      "issue",
    );
  for (const key of ["measurements", "labels", "features", "flows"]) {
    if (!d[key]?.length) continue;
    viewer.make("h3", key, host);
    for (const item of d[key]) {
      const dl = viewer.make("dl", undefined, host);
      viewer.make("dt", item.name, dl);
      viewer.make("dd", viewer.valueText(item.value), dl);
      if (item.definition) viewer.make("p", item.definition, host, "code");
      viewer.evidence(host, item.fact);
    }
  }
  const findings = (viewer.data.reviewItems || []).filter((item) =>
    item.targets.includes(viewer.inspected),
  );
  if (findings.length) {
    viewer.make("h3", "Review findings", host);
    for (const item of findings) {
      const row = viewer.make("details", undefined, host);
      viewer.make("summary", `${item.id} · ${item.group} · ${item.kind}`, row);
      viewer.make("p", item.scope, row);
      viewer.make("p", item.explanation, row);
      for (const [name, value] of Object.entries(item.values)) {
        if (
          (name !== "Known subtotal" || value !== null) &&
          (!Array.isArray(value) || value.length)
        )
          viewer.make(
            "p",
            `${name}: ${value === null ? "Unknown" : viewer.valueText(value)}`,
            row,
          );
      }
      for (const reference of item.references)
        viewer.make("p", reference, row, "code");
    }
  }
  if (d.fact) {
    viewer.make("h3", "Object provenance", host);
    viewer.evidence(host, d.fact);
  }
  const groups = viewer.memberships(viewer.inspected);
  if (groups.length) {
    viewer.make("h3", "Member of", host);
    for (const [id, a] of groups) viewer.nav(host, a.name, id);
  }
  if (element.isEdge()) {
    viewer.make("h3", "Endpoints", host);
    viewer.nav(
      host,
      `From · ${viewer.label(element.data("source"))}`,
      element.data("source"),
    );
    viewer.nav(
      host,
      `To · ${viewer.label(element.data("target"))}`,
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
      viewer.make("h3", `${direction} relationships`, host);
      edges.forEach((edge) => {
        const other = direction === "Incoming" ? edge.source() : edge.target();
        viewer.nav(
          host,
          `${edge.data("label")} · ${other.data("label")}${edge.hasClass("hidden") ? " (hidden by view)" : ""}`,
          edge.id(),
        );
      });
    }
  }
}
