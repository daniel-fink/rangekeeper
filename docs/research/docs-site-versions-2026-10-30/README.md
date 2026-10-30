# Docs site versions and lesson displays — 2026-10-30

This record supports [#191](https://github.com/daniel-fink/rangekeeper/issues/191).
It checks the versioned docs site with Zensical's fork of mike, and the lesson
displays on the static site, before the first publication. The
[publication procedure](../../contributing/walkthrough-branch.md#publish-the-site)
gives the current commands.

Source: `develop` at `5380502`, with the API reference change of
[#482](https://github.com/daniel-fink/rangekeeper/pull/482) and the display
change of the pull request that adds this record.

Environment: macOS 15 (Darwin 24.6.0), Apple silicon, Python 3.13.11,
Zensical 0.0.73, mike 2.2.0+zensical-0.1.0, mkdocstrings 1.0.8,
mkdocstrings-python 2.0.10, `uv sync --locked --all-extras --group docs --group versions`.
The lessons ran with `RK_DESIGN_MODE=fixture` and `RK_PATH_COUNT=4`.

## Isolation

The checks did not change `gh-pages`, did not push and did not publish.

1. A shallow clone of the feature branch went to a scratch folder outside the
   repository. In the clone, `git fetch --depth 1 origin gh-pages:rk-mike-check`
   copied the published branch to a scratch branch, and `git remote remove origin`
   removed the only remote.
2. `tools/docs/site.py build` staged the pages in the repository; the staged
   `_build/docs` was copied into the clone.
3. Each mike command in the clone had `--branch rk-mike-check`.
4. After the checks, `gh-pages` and `origin/gh-pages` in the repository were
   still at `052f759`, and the repository had no `rk-mike-check` branch.

## Results

| Check | Result |
| --- | --- |
| `site.py build` | Seven lessons ran from fresh kernels. The strict Zensical build reported no issues. 31 MB in `_build/site`, of which 6.5 MB is `walkthrough/output/` and 2.6 MB is `data/mixed_use_property/` |
| `mike deploy --branch rk-mike-check 1.0` | One commit, "Deployed … to 1.0 with Zensical 0.0.73 and mike 2.2.0+zensical-0.1.0". It added `1.0/` and `versions.json`. The earlier book's root files did not change |
| `mike deploy --branch rk-mike-check --title "0.8 (scratch copy of 1.0)" 0.8` | A second version, from the same pages, to check the version selector. `mike list` showed both versions |
| `mike serve --branch rk-mike-check -a 127.0.0.1:8766` | `/` served the earlier book's redirect to `intro.html`. `/versions.json` listed both versions. `/1.0/api/model.system/` returned 200 |
| Version selector | On `/1.0/walkthrough/02_front_door_back_door/`, the selector showed `1.0` and linked to `/1.0/` and `/0.8/` |
| Lesson 02 displays under `/1.0/` | The geometry viewer loaded the pinned source ("local source") and drew its canvas. Both equation diagrams drew their Plotly plots. The site's dark mode switch changed the diagrams to the dark style |
| Lesson 01 | Six HTML table outputs and the Table 1.1 image; no display iframes |
| `mike set-default --branch rk-mike-check 1.0` | The root `index.html` became a redirect to `1.0/`. The earlier book's other root files, for example `intro.html`, stayed |
| Local `site.py build` preview | The same three displays loaded from `http://127.0.0.1:8765/walkthrough/02_front_door_back_door/` |

## Limits

- The site is not published. GitHub Pages, its content types and its cache were
  not checked.
- `mike deploy` compares the local branch with `origin/<branch>`; it does not
  fetch. The check of that comparison used a branch with no remote counterpart.
- The `0.8` version is a copy of the 1.0 pages. The `/0.8/` site is
  [#72](https://github.com/daniel-fink/rangekeeper/issues/72).
- The lessons ran with fixture design data and four market paths, not the full
  data that a publication uses.
- The checks ran on macOS only.
