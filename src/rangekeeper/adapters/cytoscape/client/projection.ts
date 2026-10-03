/** Pure collapse projection. Focus is deliberately not an input. */
import { parents, assemblyOrder } from "./membership";
import {
  isEdge,
  type GraphDocument,
  type EdgeData,
  type Projection,
} from "./document";
export function projectCollapse(
  graph: GraphDocument,
  collapsedIds: Iterable<string>,
  allowedTypes: Set<string> | null = null,
): Projection {
  assemblyOrder(graph); // Reject malformed membership cycles before recursion.
  const collapsed = new Set(collapsedIds),
    memberships = parents(graph);
  const nodes = graph.elements
    .filter((e) => !isEdge(e.data))
    .map((e) => e.data);
  const originals = graph.elements.map((e) => e.data).filter(isEdge);
  const visibility = new Map<string, boolean>();
  function visible(id: string): boolean {
    if (!visibility.has(id))
      visibility.set(
        id,
        !memberships[id].length ||
          memberships[id].some(
            (parent) => visible(parent) && !collapsed.has(parent),
          ),
      );
    return visibility.get(id)!;
  }
  const hidden = new Set(nodes.filter((n) => !visible(n.id)).map((n) => n.id));
  function representatives(id: string): string[] {
    return visible(id)
      ? [id]
      : [...new Set(memberships[id].flatMap(representatives))].sort();
  }
  const edges: EdgeData[] = [],
    groups = new Map<
      string,
      { source: string; target: string; originals: Map<string, EdgeData> }
    >();
  for (const edge of originals) {
    if (allowedTypes && !allowedTypes.has(edge.type!)) continue;
    if (visible(edge.source) && visible(edge.target)) {
      edges.push({ ...edge, connector: "domain" });
      continue;
    }
    for (const source of representatives(edge.source))
      for (const target of representatives(edge.target)) {
        if (source === target) continue;
        const key = JSON.stringify([source, target]);
        if (!groups.has(key))
          groups.set(key, { source, target, originals: new Map() });
        groups.get(key)!.originals.set(edge.id, edge);
      }
  }
  for (const [key, group] of groups) {
    const underlying = [...group.originals.values()].sort((a, b) =>
      a.id.localeCompare(b.id),
    );
    edges.push({
      id: "summary:" + key,
      source: group.source,
      target: group.target,
      label:
        new Set(underlying.map((e) => e.type)).size === 1
          ? underlying[0].label
          : "Relationships",
      connector: "summary",
      originalIds: underlying.map((e) => e.id),
      displayOnly: true,
    });
  }
  for (const node of nodes) {
    if (hidden.has(node.id)) continue;
    const connections = new Map<string, string[][]>();
    function walk(id: string, path: string[]) {
      for (const owner of memberships[id]) {
        const next = [...path, owner];
        if (visible(owner)) {
          if (collapsed.has(owner)) {
            if (!connections.has(owner)) connections.set(owner, []);
            connections.get(owner)!.push(next);
          }
        } else walk(owner, next);
      }
    }
    walk(node.id, [node.id]);
    for (const [assembly, paths] of connections)
      edges.push({
        id: "membership:" + JSON.stringify([node.id, assembly]),
        source: node.id,
        target: assembly,
        label: paths.some((p) => p.length === 2)
          ? "Member of"
          : "Member within",
        connector: "membership",
        displayOnly: true,
        membershipPaths: paths,
      });
  }
  return {
    hiddenIds: [...hidden].sort(),
    memberships,
    edges: edges.sort((a, b) => a.id.localeCompare(b.id)),
  };
}
