const { test } = require("node:test"),
  assert = require("node:assert/strict");
const {
  initialPresentation,
  resizePresentation,
  movingRectangles,
  translate,
  visibleConflicts,
} = require("./load-presentation.js");
const r = (x, y, width = 60, height = 40) => ({ x, y, width, height });
function fixture() {
  const rectangles = {
    a: r(20, 50),
    b: r(100, 50),
    s: r(180, 50),
    A: r(10, 10, 240, 90),
    B: r(170, 0, 100, 110),
    R: r(0, -40, 290, 170),
  };
  const graph = {
    assemblies: {
      A: { entities: ["a", "b", "s"] },
      B: { entities: ["s"] },
      R: { entities: ["A"] },
    },
    savedLayout: {
      problem: {
        header: 30,
        padding: 10,
        gap: 0,
        assemblies: ["A", "B", "R"].map((id) => ({ id, min_width: 80 })),
      },
      geometry: { rectangles },
    },
  };
  return {
    graph,
    state: initialPresentation(graph),
    visible: new Set(Object.keys(rectangles)),
  };
}
test("node drag resizes nested boxes, no canonical mutation and exact reset", () => {
  const { graph, state, visible } = fixture(),
    snapshot = JSON.stringify(graph);
  resizePresentation(graph, state, visible, new Set());
  translate(state, movingRectangles(graph, state, "b"), 100, 80);
  resizePresentation(graph, state, visible, new Set());
  assert.equal(state.rectangles.b.x, 200);
  assert.equal(state.rectangles.A.height, 170);
  assert.ok(state.rectangles.R.height > 170);
  assert.equal(JSON.stringify(graph), snapshot);
  assert.deepEqual(
    initialPresentation(graph).rectangles,
    graph.savedLayout.geometry.rectangles,
  );
});
test("assembly translation includes hidden descendants and shared objects exactly once", () => {
  const { graph, state, visible } = fixture();
  graph.assemblies.R.entities.push("B");
  visible.delete("b");
  const original = movingRectangles(graph, state, "R");
  assert.equal(Object.keys(original).length, 6);
  translate(state, original, 20, 30);
  resizePresentation(graph, state, visible, new Set(["A"]));
  assert.equal(state.rectangles.b.x, 120);
  assert.equal(state.rectangles.s.x, 200);
  assert.equal(state.display.A.height, 30);
  visible.add("b");
  resizePresentation(graph, state, visible, new Set());
  assert.equal(state.rectangles.b.y, 80);
  assert.equal(state.rectangles.a.x, 40);
});
test("moving a shared member updates both boxes without moving their other contents", () => {
  const { graph, state, visible } = fixture();
  translate(state, movingRectangles(graph, state, "s"), 100, 100);
  resizePresentation(graph, state, visible, new Set());
  assert.equal(state.rectangles.a.x, 20);
  assert.equal(state.rectangles.b.x, 100);
  assert.equal(state.rectangles.A.width, 340);
  assert.equal(state.rectangles.B.x, 270);
});
test("visible-only bounds shrink, empty groups become headers, hidden positions survive", () => {
  const { graph, state, visible } = fixture();
  resizePresentation(graph, state, visible, new Set());
  visible.delete("s");
  resizePresentation(graph, state, visible, new Set());
  assert.equal(state.display.A.width, 160);
  assert.equal(state.display.B.height, 30);
  assert.equal(state.rectangles.s.x, 180);
  visible.delete("a");
  visible.delete("b");
  resizePresentation(graph, state, visible, new Set());
  assert.equal(state.display.A.height, 30);
  visible.add("s");
  resizePresentation(graph, state, visible, new Set());
  assert.equal(state.rectangles.s.x, 180);
});
test("conflicts are visible-only, transitive membership is valid, floats have tolerance", () => {
  const { graph, state, visible } = fixture();
  const conflicts = visibleConflicts(graph, state.rectangles, visible);
  assert.ok(
    !conflicts.some(
      (c) =>
        c.code === "exclusion" && c.objects[0] === "a" && c.objects[1] === "R",
    ),
  );
  state.rectangles.b = { ...state.rectangles.a, x: 20.001 };
  assert.ok(
    visibleConflicts(graph, state.rectangles, visible).some(
      (c) => c.code === "collision" && c.objects.join() === "a,b",
    ),
  );
  visible.delete("b");
  assert.ok(
    !visibleConflicts(graph, state.rectangles, visible).some((c) =>
      c.objects.includes("b"),
    ),
  );
});
test("dragged assembly dimensions stay stable until release, then fit visible members", () => {
  const { graph, state, visible } = fixture();
  const initial = { ...state.rectangles.A };
  translate(state, movingRectangles(graph, state, "A"), 40, 20);
  resizePresentation(graph, state, visible, new Set(), "A");
  assert.deepEqual(state.display.A, {
    ...initial,
    x: initial.x + 40,
    y: initial.y + 20,
  });
  assert.equal(state.rectangles.s.x, 220);
  resizePresentation(graph, state, visible, new Set());
  assert.equal(state.rectangles.s.x, 220);
  assert.equal(state.display.A.width, 240);
});
test("spacing is optional advisory; only actual overlap is an error", () => {
  const graph = {
    assemblies: {},
    savedLayout: { problem: { header: 28, gap: 12 } },
  };
  const visible = new Set(["a", "b"]);
  for (const x of [60, 65, 71.999]) {
    const boxes = { a: r(0, 0), b: r(x, 0) };
    assert.deepEqual(visibleConflicts(graph, boxes, visible), []);
    const findings = visibleConflicts(graph, boxes, visible, true);
    if (x < 71.99)
      assert.deepEqual(
        findings.map((f) => f.code),
        ["clearance"],
      );
  }
  assert.deepEqual(
    visibleConflicts(graph, { a: r(0, 0), b: r(72, 0) }, visible, true),
    [],
  );
  for (const optional of [false, true])
    assert.deepEqual(
      visibleConflicts(
        graph,
        { a: r(0, 0), b: r(59, 0) },
        visible,
        optional,
      ).map((f) => f.code),
      ["collision"],
    );
});
test("nearby nonmembers are advisory, intersections and unrelated enclosure stay red", () => {
  const graph = {
    assemblies: { A: { entities: [] }, B: { entities: [] } },
    savedLayout: { problem: { header: 28, gap: 12 } },
  };
  const visible = new Set(["n", "A"]);
  const boxes = { A: r(0, 0, 100, 100), n: r(105, 50, 20, 20) };
  assert.deepEqual(visibleConflicts(graph, boxes, visible), []);
  assert.deepEqual(
    visibleConflicts(graph, boxes, visible, true).map((f) => f.code),
    ["clearance"],
  );
  boxes.n.x = 99;
  assert.deepEqual(
    visibleConflicts(graph, boxes, visible).map((f) => f.code),
    ["exclusion"],
  );
  const enclosed = visibleConflicts(
    graph,
    { A: r(0, 0, 200, 200), B: r(40, 60, 100, 100) },
    new Set(["A", "B"]),
  );
  assert.deepEqual(
    enclosed.map((f) => f.code),
    ["exclusion"],
  );
});
