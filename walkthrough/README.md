# Rangekeeper walkthroughs

The seven notebook sources use the canonical Model architecture. Run them with
an installed RK wheel and the optional execution, calculation, dataframe, plotting
and notebook dependencies used in the recorded acceptance environment.

The five numerical notebooks use a visible routine scenario count of four during
acceptance. Set `RK_SCENARIO_COUNT=2000` to select the retained full comparison.
Design notebooks default explicitly to `RK_DESIGN_MODE=fixture`. Live mode needs
configured credentials and the pinned source; canonical mode needs a named envelope
file and interpretation. There is no silent service/fixture fallback or publication.

The source notebooks are the only authored implementation. To reproduce the site,
first execute them in fresh kernels from the same wheel, then use
`docs/research/full-migration/turn3/build_book.py` with the executed notebook folder.
The isolated book build disables another execution because those outputs have
already passed fresh-kernel checks. It does not use the old Jupyter cache.

See [the upgrade guide](../docs/LEGACY_UPGRADE_GUIDE.md) and
[Turn 3 acceptance](../docs/research/full-migration/turn3/BASELINE.md).
GitHub Pages publication is a separate action; rebuilding locally does not publish.
