"""Write the 0.x samples with the published 1.0.0a1 package.

The documents have no policy, so they convert: the sale period is fixed. The samples
in ``rules/`` have a policy, which has no current form, so the tool refuses them. The
same package wrote them, with ``build_stop_gain_resale_policy``. From the repository
root, with the example of that release in a directory outside the repository:

    git archive v1.0.0a1 examples/rangekeeper_examples | tar -x -C <directory>
    PYTHONPATH=<directory>/examples uv run --isolated --no-project --python 3.13 \
        --with "rangekeeper[bundle,calculations,execution,yaml]==1.0.0a1" \
        python tools/upgrade/tests/samples/build.py
"""

from pathlib import Path

import rangekeeper
from rangekeeper.io import MemoryStore, bundle
from rangekeeper.io import json as json_codec
from rangekeeper.io import yaml as yaml_codec
from rangekeeper.run.execution.executor import Executor
from rangekeeper.run.validation import validate
from rangekeeper_examples import investment

HERE = Path(__file__).parent


def main() -> None:
    """Write the documents and the Bundle next to this script."""
    assert rangekeeper.__version__ == "1.0.0a1", rangekeeper.__version__
    model = investment.formulate(investment.author(dict(num_periods=2)))
    store = MemoryStore()
    store.put(model)
    specification = investment.specify(model, sale_period=2)
    run = Executor(store).execute(specification)
    validate(run, resolver=store).raise_if_invalid()
    output = store.load_model(run.record.outputs[0])
    json_codec.write(model, HERE / "model.json")
    json_codec.write(output, HERE / "output.json")
    json_codec.write(run, HERE / "run.json")
    yaml_codec.write(specification, HERE / "specification.yaml")
    bundle.write(HERE / "bundle", model, documents=[run], resolver=store)


if __name__ == "__main__":
    main()
