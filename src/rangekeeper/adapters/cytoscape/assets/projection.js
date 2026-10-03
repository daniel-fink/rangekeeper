var rkProjection = (() => {
  var __defProp = Object.defineProperty;
  var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
  var __getOwnPropNames = Object.getOwnPropertyNames;
  var __hasOwnProp = Object.prototype.hasOwnProperty;
  var __export = (target, all) => {
    for (var name in all)
      __defProp(target, name, { get: all[name], enumerable: true });
  };
  var __copyProps = (to, from, except, desc) => {
    if (from && typeof from === "object" || typeof from === "function") {
      for (let key of __getOwnPropNames(from))
        if (!__hasOwnProp.call(to, key) && key !== except)
          __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
    }
    return to;
  };
  var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

  // projection.ts
  var projection_exports = {};
  __export(projection_exports, {
    projectCollapse: () => projectCollapse
  });

  // membership.ts
  function parents(graph) {
    const result = Object.fromEntries(
      graph.elements.filter((e) => !("source" in e.data)).map((e) => [e.data.id, []])
    );
    for (const [id, a] of Object.entries(graph.assemblies))
      for (const member of a.entities) result[member].push(id);
    for (const list of Object.values(result)) list.sort();
    return result;
  }
  function assemblyOrder(graph) {
    const ordered = [], active = /* @__PURE__ */ new Set(), seen = /* @__PURE__ */ new Set();
    const visit = (id) => {
      if (seen.has(id)) return;
      if (active.has(id)) throw new Error("Assembly membership cycle");
      active.add(id);
      for (const child of graph.assemblies[id].entities)
        if (graph.assemblies[child]) visit(child);
      active.delete(id);
      seen.add(id);
      ordered.push(id);
    };
    Object.keys(graph.assemblies).forEach(visit);
    return ordered;
  }

  // document.ts
  var isEdge = (data) => "source" in data;

  // projection.ts
  function projectCollapse(graph, collapsedIds, allowedTypes = null) {
    assemblyOrder(graph);
    const collapsed = new Set(collapsedIds), memberships = parents(graph);
    const nodes = graph.elements.filter((e) => !isEdge(e.data)).map((e) => e.data);
    const originals = graph.elements.map((e) => e.data).filter(isEdge);
    const visibility = /* @__PURE__ */ new Map();
    function visible(id) {
      if (!visibility.has(id))
        visibility.set(
          id,
          !memberships[id].length || memberships[id].some(
            (parent) => visible(parent) && !collapsed.has(parent)
          )
        );
      return visibility.get(id);
    }
    const hidden = new Set(nodes.filter((n) => !visible(n.id)).map((n) => n.id));
    function representatives(id) {
      return visible(id) ? [id] : [...new Set(memberships[id].flatMap(representatives))].sort();
    }
    const edges = [], groups = /* @__PURE__ */ new Map();
    for (const edge of originals) {
      if (allowedTypes && !allowedTypes.has(edge.type)) continue;
      if (visible(edge.source) && visible(edge.target)) {
        edges.push({ ...edge, connector: "domain" });
        continue;
      }
      for (const source of representatives(edge.source))
        for (const target of representatives(edge.target)) {
          if (source === target) continue;
          const key = JSON.stringify([source, target]);
          if (!groups.has(key))
            groups.set(key, { source, target, originals: /* @__PURE__ */ new Map() });
          groups.get(key).originals.set(edge.id, edge);
        }
    }
    for (const [key, group] of groups) {
      const underlying = [...group.originals.values()].sort(
        (a, b) => a.id.localeCompare(b.id)
      );
      edges.push({
        id: "summary:" + key,
        source: group.source,
        target: group.target,
        label: new Set(underlying.map((e) => e.type)).size === 1 ? underlying[0].label : "Relationships",
        connector: "summary",
        originalIds: underlying.map((e) => e.id),
        displayOnly: true
      });
    }
    for (const node of nodes) {
      let walk = function(id, path) {
        for (const owner of memberships[id]) {
          const next = [...path, owner];
          if (visible(owner)) {
            if (collapsed.has(owner)) {
              if (!connections.has(owner)) connections.set(owner, []);
              connections.get(owner).push(next);
            }
          } else walk(owner, next);
        }
      };
      if (hidden.has(node.id)) continue;
      const connections = /* @__PURE__ */ new Map();
      walk(node.id, [node.id]);
      for (const [assembly, paths] of connections)
        edges.push({
          id: "membership:" + JSON.stringify([node.id, assembly]),
          source: node.id,
          target: assembly,
          label: paths.some((p) => p.length === 2) ? "Member of" : "Member within",
          connector: "membership",
          displayOnly: true,
          membershipPaths: paths
        });
    }
    return {
      hiddenIds: [...hidden].sort(),
      memberships,
      edges: edges.sort((a, b) => a.id.localeCompare(b.id))
    };
  }
  return __toCommonJS(projection_exports);
})();
