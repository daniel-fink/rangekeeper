"""Simple local graph display."""

import json
from collections.abc import Mapping
from os import PathLike
from pathlib import Path

from rangekeeper.shared.optional import requires

with requires("visualisation"):
    from pyvis.network import Network

from rangekeeper.model.definitions import classification as find_classification
from rangekeeper.model.system import View
from rangekeeper.shared.errors import EncodingError


def graph_html(
    view: View,
    path: str | PathLike[str],
    *,
    height: str = "750px",
    width: str = "100%",
    options: Mapping[str, object] | None = None,
) -> Path:
    """Write an interactive PyVis rendering of a View and return its path."""
    if not isinstance(view, View):
        raise TypeError("view must be a View")
    for value, name in ((height, "height"), (width, "width")):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
    if options is not None and not isinstance(options, Mapping):
        raise TypeError("options must be a mapping or None")

    network = Network(
        height=height,
        width=width,
        directed=True,
        notebook=False,
        cdn_resources="in_line",
    )
    for entity in view.entities:
        classification = (
            find_classification(view.model.definitions, entity.classification)
            if entity.classification
            else None
        )
        taxonomy_code = None
        if classification is not None:
            taxonomy_code = str(classification.id)
        network.add_node(
            str(entity.id),
            label=entity.name or entity.code or str(entity.id),
            title=(
                str(entity.id)
                if classification is None
                else f"{entity.id}<br>{taxonomy_code}:{classification.code}"
            ),
            group=(
                None
                if classification is None
                else f"{taxonomy_code}:{classification.code}"
            ),
        )
    for relationship in view.relationships:
        network.add_edge(
            str(relationship.source),
            str(relationship.target),
            label=find_classification(
                view.model.definitions, relationship.classification
            ).code,
            title=find_classification(
                view.model.definitions, relationship.classification
            ).name,
        )
    if options is not None:
        try:
            network.set_options(json.dumps(dict(options), allow_nan=False))
        except (TypeError, ValueError) as error:
            raise EncodingError(f"invalid PyVis options: {error}") from error

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    network.write_html(str(target), open_browser=False, notebook=False)
    return target
