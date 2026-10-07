# Rangekeeper walkthroughs

The seven notebook sources use the canonical Model architecture. Run them with
the wheel built from this checkout and its optional execution, calculation, table,
plotting and notebook dependencies. For example:

```sh
python -m pip install "./src[calculations,tables,workflow,execution,plotting,visualization]" nbclient nbformat nbconvert ipykernel
```

Run that install command from the repository root. Live design receive also needs
the `speckle` extra; fixture mode needs no SDK.

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
The static build also disables the unused Sphinx-Thebe extension through its
Sphinx configuration, which prevents duplicate JavaScript declarations. Colab
launch links remain available. Use the build dependencies in `walkthrough/uv.lock`.

See [the upgrade guide](../docs/LEGACY_UPGRADE_GUIDE.md) and
[verification guide](../docs/VERIFICATION.md).
GitHub Pages publication is a separate action; rebuilding locally does not publish.

Polars is the only dataframe dependency. The walkthrough lockfile resolves
Rangekeeper from `../src`, so it cannot silently select an older published API.
