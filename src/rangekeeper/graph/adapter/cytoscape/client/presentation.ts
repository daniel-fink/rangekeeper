/** Mutable, session-only geometry. Never writes the exported document. */
import type { GraphDocument } from "./document";
import { assemblyOrder, descendants } from "./membership";
export interface Rectangle {
  x: number;
  y: number;
  width: number;
  height: number;
}
export interface Conflict {
  code: "exclusion" | "collision" | "clearance";
  objects: string[];
  message: string;
}
export interface Presentation {
  rectangles: Record<string, Rectangle>;
  display: Record<string, Rectangle>;
  adjusted: boolean;
  visibility: string;
  conflicts: Conflict[];
}
export function initialPresentation(graph: GraphDocument): Presentation | null {
  if (!graph.savedLayout) return null;
  return {
    rectangles: structuredClone(graph.savedLayout.geometry.rectangles),
    display: structuredClone(graph.savedLayout.geometry.rectangles),
    adjusted: false,
    visibility: "",
    conflicts: [],
  };
}
export function translate(
  state: Presentation,
  originals: Record<string, Rectangle>,
  dx: number,
  dy: number,
) {
  for (const [id, r] of Object.entries(originals))
    state.rectangles[id] = { ...r, x: r.x + dx, y: r.y + dy };
  if (dx || dy) state.adjusted = true;
}
export function movingRectangles(
  graph: GraphDocument,
  state: Presentation,
  id: string,
) {
  return Object.fromEntries(
    [id, ...descendants(graph, id)].map((i) => [i, { ...state.rectangles[i] }]),
  );
}
export function resizePresentation(
  graph: GraphDocument,
  state: Presentation,
  visible: Set<string>,
  collapsed: Set<string>,
  dragging?: string,
  showSpacing = false,
) {
  const signature = JSON.stringify([
    [...visible].sort(),
    [...collapsed].sort(),
  ]);
  if (state.visibility && state.visibility !== signature) state.adjusted = true;
  state.visibility = signature;
  const boxes = structuredClone(state.rectangles),
    p = graph.savedLayout.problem;
  for (const id of assemblyOrder(graph)) {
    if (!visible.has(id)) continue;
    const members = graph.assemblies[id].entities.filter((i) => visible.has(i));
    if (collapsed.has(id) || !members.length) {
      boxes[id] = { ...boxes[id], height: p.header };
    } else if (state.adjusted && id !== dragging) {
      const rs = members.map((i) => boxes[i]);
      const left = Math.min(...rs.map((r) => r.x)),
        top = Math.min(...rs.map((r) => r.y));
      const right = Math.max(...rs.map((r) => r.x + r.width)),
        bottom = Math.max(...rs.map((r) => r.y + r.height));
      const min = p.assemblies?.find((a) => a.id === id)?.min_width ?? 180;
      const width = Math.max(min, right - left + 2 * p.padding);
      boxes[id] = {
        x: (left + right - width) / 2,
        y: top - p.padding - p.header,
        width,
        height: bottom - top + 2 * p.padding + p.header,
      };
      state.rectangles[id] = { ...boxes[id] };
    }
  }
  state.display = boxes;
  state.conflicts = visibleConflicts(graph, boxes, visible, showSpacing);
}
const EPS = 0.01;
function separated(a: Rectangle, b: Rectangle, gap = 0) {
  return (
    a.x + a.width + gap <= b.x + EPS ||
    b.x + b.width + gap <= a.x + EPS ||
    a.y + a.height + gap <= b.y + EPS ||
    b.y + b.height + gap <= a.y + EPS
  );
}
export function visibleConflicts(
  graph: GraphDocument,
  boxes: Record<string, Rectangle>,
  visible: Set<string>,
  showSpacing = false,
): Conflict[] {
  const groups = Object.keys(graph.assemblies)
    .filter((i) => visible.has(i))
    .sort();
  const nodes = [...visible].filter((i) => !graph.assemblies[i]).sort();
  const result: Conflict[] = [],
    gap = graph.savedLayout.problem.gap ?? 0,
    header = graph.savedLayout.problem.header;
  for (const outer of groups) {
    const members = new Set(descendants(graph, outer)),
      r = boxes[outer];
    for (const n of nodes) {
      if (members.has(n)) continue;
      if (!separated(boxes[n], r))
        result.push({
          code: "exclusion",
          objects: [n, outer],
          message: "Nonmember overlaps assembly",
        });
      else if (showSpacing && !separated(boxes[n], r, gap))
        result.push({
          code: "clearance",
          objects: [n, outer],
          message: `Spacing advisory: less than ${gap} layout units between nonmember and assembly`,
        });
    }
    for (const inner of groups) {
      if (inner === outer || members.has(inner)) continue;
      const c = boxes[inner];
      if (
        r.x <= c.x + EPS &&
        r.y <= c.y + EPS &&
        c.x + c.width <= r.x + r.width + EPS &&
        c.y + c.height <= r.y + r.height + EPS
      )
        result.push({
          code: "exclusion",
          objects: [inner, outer],
          message: "Unrelated assembly fully enclosed",
        });
    }
  }
  const obstacles = [
    ...nodes.map((i) => [i, boxes[i]] as const),
    ...groups.map((i) => [i, { ...boxes[i], height: header }] as const),
  ].sort((a, b) => a[0].localeCompare(b[0]));
  for (let i = 0; i < obstacles.length; i++)
    for (let j = i + 1; j < obstacles.length; j++) {
      const [a, ra] = obstacles[i],
        [b, rb] = obstacles[j];
      if (!separated(ra, rb))
        result.push({
          code: "collision",
          objects: [a, b],
          message: "Node or assembly header overlaps another footprint",
        });
      else if (showSpacing && !separated(ra, rb, gap))
        result.push({
          code: "clearance",
          objects: [a, b],
          message: `Spacing advisory: less than ${gap} layout units between node/header footprints`,
        });
    }
  return result.sort(
    (a, b) => Number(a.code === "clearance") - Number(b.code === "clearance"),
  );
}
