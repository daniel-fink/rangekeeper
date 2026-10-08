"""Static review SVGs, deliberately independent of the production viewer.

The input footprints include text. Text is clipped within those footprints so the
render cannot invent unmeasured collisions. Ellipses explicitly signal clipping.
"""

from rangekeeper.adapters.cytoscape.layout.result import ResultMode
import re
from html import escape
from xml.etree import ElementTree

from rangekeeper.adapters.cytoscape.layout.check import check, _check
from rangekeeper.adapters.cytoscape.layout.model import Problem, Rect
from rangekeeper.adapters.cytoscape.layout.result import Result

PALETTE = ("#2563eb", "#b45309", "#7c3aed", "#047857", "#be185d", "#0e7490")


def _text(label: str, box: Rect, color: str = "#14243a"):
    # The nested SVG clips real font rendering to the declared object footprint.
    available = box.width - 16
    if available < 8 or box.height < 16:
        return ""
    count = available // 8
    label = label if len(label) <= count else label[: max(0, count - 1)] + "…"
    return (
        f'<svg x="{box.x}" y="{box.y}" width="{box.width}" height="{box.height}" overflow="hidden">'
        f'<text x="8" y="{box.height // 2 + 4}" fill="{color}" font-family="monospace" '
        f'font-size="12">{escape(label)}</text></svg>'
    )


def svg(
    problem: Problem,
    result: Result,
    *,
    node_colors: dict[str, str] | None = None,
) -> str:
    node_colors = node_colors or {}
    if any(
        re.fullmatch(r"#[0-9a-fA-F]{6}", color) is None
        for color in node_colors.values()
    ):
        raise ValueError("Node colors must be six-digit hex colors")
    if not result.rectangles:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="80"><text x="16" y="40">No layout returned</text></svg>'
    descendants_by_id = problem.descendant_index()
    findings = _check(problem, result.rectangles, descendants_by_id)
    if any(f.code != "exclusion" or result.mode == ResultMode.STRICT for f in findings):
        raise ValueError("Cannot render an unchecked layout")
    width = max(r.right for r in result.rectangles.values()) + 40
    height = max(r.bottom for r in result.rectangles.values()) + 40
    parts = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="-20 -20 {width} {height}" role="img" aria-label="Assembly layout">'
        ),
        '<rect x="-20" y="-20" width="100%" height="100%" fill="white"/>',
    ]
    # Draw large containing frames first; object IDs are preserved as attributes.
    assemblies = sorted(
        problem.assemblies, key=lambda a: (-len(descendants_by_id[a.id]), a.id)
    )
    colors = {
        a.id: PALETTE[i % len(PALETTE)]
        for i, a in enumerate(sorted(problem.assemblies, key=lambda a: a.id))
    }
    conflicts = {f.objects[0] for f in findings if f.code == "exclusion"}
    for a in assemblies:
        r = result.rectangles[a.id]
        color = "#dc2626" if a.id in conflicts else colors[a.id]
        parts.extend(
            [
                (
                    f'<rect data-object="{escape(a.id, quote=True)}" data-kind="assembly" x="{r.x}" y="{r.y}" '
                    f'width="{r.width}" height="{r.height}" fill="{color}" fill-opacity="0.05" '
                    f'stroke="{color}" stroke-width="1"/>'
                ),
                (
                    f'<rect x="{r.x}" y="{r.y}" width="{r.width}" height="{problem.header}" '
                    f'fill="{color}" fill-opacity="0.15"/>'
                ),
                _text(a.label, Rect(r.x, r.y, r.width, problem.header), color),
            ]
        )
    conflicts = {f.objects[0] for f in findings if f.code == "exclusion"}
    for n in problem.nodes:
        r = result.rectangles[n.id]
        color = "#dc2626" if n.id in conflicts else "#334155"
        memberships = [
            a.label for a in problem.assemblies if n.id in descendants_by_id[a.id]
        ]
        parts.extend(
            [
                f"<g><title>{escape(n.label + '; member of: ' + ', '.join(memberships))}</title>",
                (
                    f'<rect data-object="{escape(n.id, quote=True)}" data-kind="node" x="{r.x}" y="{r.y}" '
                    f'width="{r.width}" height="{r.height}" rx="4" fill="{node_colors.get(n.id, "#ffffff")}" stroke="{color}" stroke-width="1"/>'
                ),
                _text(n.label, r),
                "</g>",
            ]
        )
    parts.append("</svg>")
    output = "".join(parts)
    # Parse the actual exported object rectangles back, then run the checker again.
    # Production browser geometry will need an equivalent check at integration.
    verify_svg(problem, output, result.rectangles)
    return output


def verify_svg(problem: Problem, source: str, expected: dict[str, Rect]):
    found = {}
    for element in ElementTree.fromstring(source).iter():
        identifier = element.get("data-object")
        if identifier is None:
            continue
        if identifier in found:
            raise ValueError("Duplicate visual object")
        found[identifier] = Rect(
            *(int(element.attrib[k]) for k in ("x", "y", "width", "height"))
        )
    if found != expected:
        raise ValueError("Rendered coordinates differ from checked geometry")
    return check(problem, found)
