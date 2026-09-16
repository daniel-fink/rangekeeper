import type cytoscape from "cytoscape";
import type { GraphDocument, Projection, Point } from "./document";
import type { route, Port } from "./routing";
export interface Snapshot {
  focus: string[] | null;
  filters: string[];
  collapsed: string[];
  showMembership: boolean;
}
/** One owner for mutable display state. Canonical document data is never edited. */
export interface ViewerContext {
  datasets: GraphDocument[];
  data: GraphDocument;
  cy: cytoscape.Core;
  projection: Projection;
  inspected: string | null;
  focusIds: Set<string> | null;
  history: Snapshot[];
  collapsed: Set<string>;
  filters: Set<string>;
  mode: string;
  showMembership: boolean;
  fourPorts: boolean;
  compactPositions: Record<string, Point>;
  drag: {
    id: string;
    start: Point;
    members: Array<{ id: string; position: Point }>;
  } | null;
  syncing: boolean;
  updating: boolean;
  layoutMode: boolean;
  portChoices: Map<string, { sourcePort: Port; targetPort: Port }>;
  routes: Map<string, ReturnType<typeof route>>;
  metrics: {
    loadMs: number;
    layoutMs: number;
    selectionMs: number;
    filterMs: number;
  };
  HEADER: number;
  PAD: number;
  routingStyle: string;
  labelMeasure: CanvasRenderingContext2D;
  $: (
    id: string,
  ) => HTMLElement & Pick<HTMLInputElement, "value" | "checked" | "disabled">;
  make: <K extends keyof HTMLElementTagNameMap>(
    tag: K,
    text?: unknown,
    parent?: HTMLElement,
    cls?: string,
  ) => HTMLElementTagNameMap[K];
  label: (id: string) => string;
  memberships: (
    id: string,
  ) => Array<[string, GraphDocument["assemblies"][string]]>;
  visible: () => cytoscape.CollectionReturnValue;
  snapshot: () => Snapshot;
  pushHistory: () => void;
  updateCounts: () => void;
  connectionCentre: (node: cytoscape.NodeSingular) => Point;
  headerEndpoint: (
    node: cytoscape.NodeSingular,
    other: cytoscape.NodeSingular,
  ) => Point;
  endpoint: (edge: cytoscape.EdgeSingular, source: boolean) => string;
  connectionGeometry: (
    node: cytoscape.NodeSingular,
  ) => Point & { w: number; h: number; nodePosition: Point };
  updateConnections: () => void;
  syncBoxes: () => void;
  highlight: () => void;
  applyVisibility: () => void;
  changeCollapse: (ids: Iterable<string>, value: boolean) => void;
  fit: () => void;
  focusOn: (id: string) => void;
  reset: () => void;
  restore: () => void;
  valueText: (value: unknown) => string;
  evidence: (
    parent: HTMLElement,
    fact: GraphDocument["details"][string]["fact"],
  ) => void;
  nav: (parent: HTMLElement, text: string, id: string) => HTMLButtonElement;
  reveal: (id: string, assemblyId?: string) => void;
  renderSelection: () => void;
  select: (id: string, ...unused: unknown[]) => void;
  syncFilters: () => void;
  setupFilters: () => void;
  selectLinkedObject: () => void;
  loadDataset: (index: number) => void;
  relayout: () => Promise<void>;
  setMode: (mode: string) => void;
}
declare global {
  interface Window {
    spike: unknown;
    graphReview: unknown;
  }
}
