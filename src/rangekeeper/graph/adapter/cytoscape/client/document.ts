/** Read-only display contract. IDs refer to canonical graph objects. */
export interface Point {
  x: number;
  y: number;
}
export interface NodeData {
  id: string;
  label: string;
  code: string;
  title?: string;
  kind: "entity" | "assembly";
  type: string;
  classificationCode?: string;
}
export interface EdgeData {
  id: string;
  source: string;
  target: string;
  label: string;
  type?: string;
  connector?: "domain" | "summary" | "membership";
  originalIds?: string[];
  displayOnly?: boolean;
  membershipPaths?: string[][];
}
export interface Element {
  data: NodeData | EdgeData;
  position?: Point;
}
export interface AssemblyData {
  name: string;
  entities: string[];
  relationships: string[];
}
export interface FactData {
  status: string;
  claims: string[];
  selected?: string;
  reconciliation?: string;
  method?: unknown;
}
export interface CharacteristicData {
  id?: string;
  name: string;
  value: unknown;
  definition?: string;
  fact?: FactData;
}
export interface Detail {
  id: string;
  name?: string;
  classification?: { id: string; code: string; name: string };
  fact?: FactData;
  measurements: CharacteristicData[];
  labels: CharacteristicData[];
  features: CharacteristicData[];
}
export interface ClaimData {
  id: string;
  kind: string;
  value: unknown;
  method?: unknown;
  sources: Array<{
    claim?: string;
    name?: string;
    reference?: unknown;
    checksum?: string;
  }>;
}
export interface ReviewItem {
  id: string;
  targets: string[];
  group: string;
  kind: string;
  scope: string;
  explanation: string;
  values: Record<string, unknown>;
  references: string[];
}
export interface GraphDocument {
  name: string;
  elements: Element[];
  assemblies: Record<string, AssemblyData>;
  details: Record<string, Detail>;
  claims: Record<string, ClaimData>;
  positions: Record<string, Point>;
  initialFocus?: string;
  anchors: string[];
  notes: string[];
  alignment?: { vertical: string[][] };
  diagnostics: { ambiguousParents: string[]; containmentCycles: string[] };
  reviewItems?: ReviewItem[];
}
export interface Projection {
  hiddenIds: string[];
  memberships: Record<string, string[]>;
  edges: EdgeData[];
}
export const isEdge = (data: NodeData | EdgeData): data is EdgeData =>
  "source" in data;
