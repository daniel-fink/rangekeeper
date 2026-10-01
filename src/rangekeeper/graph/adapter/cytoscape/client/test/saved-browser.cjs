const { test } = require("node:test");
const assert = require("node:assert/strict"),
  fs = require("node:fs"),
  path = require("node:path");
test(
  "saved starting geometry supports dragging, visible resizing, conflicts and exact restore",
  { skip: !process.env.RK_SAVED_VIEWER_URL, timeout: 120000 },
  async () => {
    const { chromium } = require("playwright");
    const browser = await chromium.launch({
      executablePath:
        process.env.RK_CHROME ||
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
      headless: true,
    });
    try {
      const page = await browser.newPage({
          viewport: { width: 1500, height: 1100 },
        }),
        errors = [];
      page.on("pageerror", (e) => errors.push(e.message));
      await page.goto(process.env.RK_SAVED_VIEWER_URL);
      await page.waitForFunction(
        () => window.graphReview?.cy.nodes().length === 9,
      );
      const original = await page.evaluate(() =>
        JSON.stringify(graphReview.data),
      );
      const rendered = () =>
        page.evaluate(() =>
          Object.fromEntries(
            graphReview.cy
              .nodes()
              .filter((n) => !n.hasClass("hidden"))
              .map((n) => {
                const b = n.boundingBox({
                  includeLabels: true,
                  includeOverlays: false,
                });
                return [n.id(), { x: b.x1, y: b.y1, width: b.w, height: b.h }];
              }),
          ),
        );
      const assertBounds = async () => {
        const [actual, expected] = await Promise.all([
          rendered(),
          page.evaluate(() => graphReview.presentation.display),
        ]);
        for (const [id, r] of Object.entries(actual))
          for (const key of ["x", "y", "width", "height"])
            assert.ok(
              Math.abs(r[key] - expected[id][key]) < 0.02,
              `${id} ${key}`,
            );
      };
      const saved = await rendered();
      await assertBounds();
      assert.equal(
        await page.evaluate(() =>
          graphReview.cy.nodes().every((n) => n.grabbable()),
        ),
        true,
      );
      const ids = await page.evaluate(() => {
        const floor = Object.keys(graphReview.data.assemblies).find(
          (i) => graphReview.data.assemblies[i].name === "Shelf A",
        );
        return {
          floor,
          members: graphReview.data.assemblies[floor].entities,
          other: Object.keys(graphReview.data.assemblies).find(
            (i) => graphReview.data.assemblies[i].name === "Shelf B",
          ),
        };
      });
      const drag = async (id, dx, dy) => {
        const p = await page.evaluate((id) => {
          const n = graphReview.cy.getElementById(id);
          graphReview.cy.center(n);
          const r = graphReview.presentation.display[id],
            z = graphReview.cy.zoom(),
            pan = graphReview.cy.pan(),
            host = document.getElementById("cy").getBoundingClientRect();
          return {
            x:
              host.x +
              pan.x +
              (r.x + (graphReview.data.assemblies[id] ? 32 : r.width / 2)) * z,
            y:
              host.y +
              pan.y +
              (r.y +
                (graphReview.data.assemblies[id]
                  ? graphReview.data.savedLayout.problem.header / 2
                  : r.height / 2)) *
                z,
            z,
          };
        }, id);
        await page.mouse.move(p.x, p.y);
        await page.mouse.down();
        await page.mouse.move(p.x + dx * p.z, p.y + dy * p.z, { steps: 8 });
        await page.mouse.up();
        await page.waitForTimeout(120);
      };
      const positions = () =>
        page.evaluate(() => graphReview.presentation.rectangles);
      const approx = (a, b) => assert.ok(Math.abs(a - b) < 3, `${a} != ${b}`);
      await page.evaluate((id) => {
        graphReview.select(id);
        graphReview.focusOn(id);
      }, ids.floor);
      let before = await positions();
      await drag(ids.members[0], 70, 55);
      let after = await positions();
      approx(after[ids.members[0]].x - before[ids.members[0]].x, 70);
      approx(after[ids.members[0]].y - before[ids.members[0]].y, 55);
      await assertBounds();
      const one = ids.members[0],
        two = ids.members[1];
      before = await positions();
      await drag(
        one,
        before[two].x - before[one].x,
        before[two].y - before[one].y,
      );
      assert.ok(
        await page.evaluate(() =>
          graphReview.presentation.conflicts.some(
            (c) => c.code === "collision",
          ),
        ),
      );
      assert.ok(
        await page
          .locator("#presentation-conflicts")
          .innerText()
          .then((t) => t.includes("Adjusted presentation")),
      );
      await page.locator("#presentation-conflicts summary").click();
      await page.locator("#presentation-conflicts button").first().click();
      assert.ok(await page.evaluate(() => graphReview.selected));
      before = await positions();
      await drag(ids.floor, 40, 30);
      after = await positions();
      for (const id of ids.members) {
        approx(after[id].x - before[id].x, 40);
        approx(after[id].y - before[id].y, 30);
      }
      await assertBounds();
      await page.evaluate(
        (id) => graphReview.changeCollapse([id], true),
        ids.floor,
      );
      before = await positions();
      await drag(ids.floor, 60, 40);
      after = await positions();
      for (const id of ids.members) {
        approx(after[id].x - before[id].x, 60);
        approx(after[id].y - before[id].y, 40);
      }
      await page.evaluate(
        (id) => graphReview.changeCollapse([id], false),
        ids.floor,
      );
      await assertBounds();
      if (process.env.RK_BROWSER_OUTPUT) {
        fs.mkdirSync(process.env.RK_BROWSER_OUTPUT, { recursive: true });
        await page.screenshot({
          path: path.join(process.env.RK_BROWSER_OUTPUT, "adjusted.png"),
        });
      }
      await page.click("#restore");
      assert.deepEqual(await rendered(), saved);
      assert.equal(
        await page.evaluate(() => graphReview.presentation.conflicts.length),
        0,
      );
      await page.evaluate(() => {
        graphReview.cy.zoom(0.4);
      });
      before = await positions();
      const target = ids.other;
      await drag(
        one,
        before[target].x + 40 - before[one].x,
        before[target].y + 60 - before[one].y,
      );
      assert.ok(
        await page.evaluate(
          ([id, group]) =>
            graphReview.presentation.conflicts.some(
              (c) =>
                c.code === "exclusion" &&
                c.objects[0] === id &&
                c.objects[1] === group,
            ),
          [one, target],
        ),
      );
      await page.click("#restore");
      assert.deepEqual(await rendered(), saved);
      assert.equal(
        await page.evaluate(() => JSON.stringify(graphReview.data)),
        original,
      );
      await page.evaluate((id) => graphReview.focusOn(id), ids.floor);
      const ordinaryBefore = await positions();
      await page.evaluate((id) => graphReview.focusOn(id), one);
      const ordinaryAfter = await positions();
      for (const id of ids.members)
        assert.deepEqual(ordinaryAfter[id], ordinaryBefore[id]);
      assert.ok(
        ordinaryAfter[ids.floor].width < ordinaryBefore[ids.floor].width ||
          ordinaryAfter[ids.floor].height < ordinaryBefore[ids.floor].height,
      );
      await page.click("#restore");
      assert.deepEqual(await rendered(), saved);
      const checkboxes = page.locator("#filters input");
      if (await checkboxes.count()) {
        await checkboxes.first().uncheck();
        await page.click("#restore");
        assert.equal(await checkboxes.first().isChecked(), false);
        await checkboxes.first().check();
      }
      await page.setViewportSize({ width: 1100, height: 850 });
      assert.deepEqual(await rendered(), saved);
      await page.evaluate(() => graphReview.loadDataset(1));
      assert.equal(
        await page.locator("#spacing-advisories").isVisible(),
        false,
      );
      assert.equal(await page.locator("#relayout").isDisabled(), false);
      assert.equal(
        await page.locator("#presentation-conflicts").innerText(),
        "",
      );
      await page.evaluate(() => graphReview.loadDataset(2));
      before = await positions();
      await drag("A", 30, 20);
      after = await positions();
      approx(after.s.x - before.s.x, 30);
      approx(after.s.y - before.s.y, 20);
      await assertBounds();
      await page.evaluate(() => graphReview.changeCollapse(["A"], true));
      assert.equal(
        await page.evaluate(() =>
          graphReview.cy.getElementById("s").hasClass("hidden"),
        ),
        false,
      );
      before = await positions();
      await drag("A", 20, 10);
      after = await positions();
      approx(after.s.x - before.s.x, 20);
      approx(after.s.y - before.s.y, 10);
      await page.evaluate(() => graphReview.changeCollapse(["B"], true));
      assert.equal(
        await page.evaluate(() =>
          graphReview.cy.getElementById("s").hasClass("hidden"),
        ),
        true,
      );
      await page.click("#restore");
      await assertBounds();
      await page.evaluate(() => {
        graphReview.focusOn("A");
        graphReview.cy.zoom(1);
      });
      before = await positions();
      await drag(
        "s",
        before.a.x - before.s.x,
        before.a.y + before.a.height + 6 - before.s.y,
      );
      assert.equal(
        await page.locator("#spacing-advisories").isChecked(),
        false,
      );
      assert.equal(
        await page.evaluate(
          () => graphReview.cy.nodes(".presentation-conflict").length,
        ),
        0,
      );
      const closePositions = await positions();
      await page.locator("#spacing-advisories").check();
      assert.equal(
        await page.evaluate(
          () => graphReview.cy.nodes(".presentation-advisory").length,
        ),
        2,
      );
      assert.deepEqual(await positions(), closePositions);
      if (process.env.RK_BROWSER_OUTPUT)
        await page.screenshot({
          path: path.join(process.env.RK_BROWSER_OUTPUT, "spacing-amber.png"),
        });
      await page.locator("#spacing-advisories").uncheck();
      assert.equal(
        await page.evaluate(
          () => graphReview.cy.nodes(".presentation-advisory").length,
        ),
        0,
      );
      await drag("s", 0, -10);
      assert.equal(
        await page.evaluate(
          () => graphReview.cy.nodes(".presentation-conflict").length,
        ),
        2,
      );
      await page.locator("#spacing-advisories").check();
      assert.equal(
        await page.evaluate(
          () => graphReview.cy.nodes(".presentation-advisory").length,
        ),
        0,
      );
      await page.click("#restore");
      await page.evaluate(() => graphReview.loadDataset(0));
      assert.equal(
        await page.locator("#spacing-advisories").isChecked(),
        false,
      );
      assert.deepEqual(await rendered(), saved);
      assert.deepEqual(errors, []);
      if (process.env.RK_BROWSER_OUTPUT)
        fs.writeFileSync(
          path.join(process.env.RK_BROWSER_OUTPUT, "acceptance.json"),
          JSON.stringify(
            {
              objects: 9,
              actualPointerDragging: true,
              hiddenDescendantsMoved: true,
              sharedMemberMovedOnce: true,
              visibleOnlyBounds: true,
              conflicts: true,
              exactRestore: true,
              immutableDocument: true,

              pageErrors: errors,
            },
            null,
            2,
          ),
        );
    } finally {
      await browser.close();
    }
  },
);
