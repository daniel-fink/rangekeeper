/** Membership navigation is independent of domain relationship classifications. */
import type { GraphDocument } from "./document";
export function parents(graph: GraphDocument): Record<string, string[]> {
  const result = Object.fromEntries(
    graph.elements
      .filter((e) => !("source" in e.data))
      .map((e) => [e.data.id, [] as string[]]),
  );
  for (const [id, a] of Object.entries(graph.assemblies))
    for (const member of a.entities) result[member].push(id);
  for (const list of Object.values(result)) list.sort();
  return result;
}
export function descendants(graph: GraphDocument, id: string): string[] {
  const found = new Set<string>();
  const visit = (current: string) => {
    for (const child of graph.assemblies[current]?.entities || [])
      if (!found.has(child)) {
        found.add(child);
        visit(child);
      }
  };
  visit(id);
  found.delete(id);
  return [...found];
}
export function assemblyOrder(graph: GraphDocument): string[] {
  const ordered: string[] = [],
    active = new Set<string>(),
    seen = new Set<string>();
  const visit = (id: string) => {
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
/** Choose one deterministic path to a root; Reveal opens that path only. */
export function revealPath(graph: GraphDocument, id: string): string[] {
  const owners = parents(graph),
    path: string[] = [];
  while (owners[id]?.length) {
    id = owners[id][0];
    path.push(id);
  }
  return path;
}
