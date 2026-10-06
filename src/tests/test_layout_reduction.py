"""Geometric implication proofs and preservation of shared/diagnostic constraints."""

from dataclasses import replace

import pytest

from rangekeeper.adapters.cytoscape.layout import Assembly, Node, Problem
from rangekeeper.adapters.cytoscape.layout.reduction import collision_pairs


def test_shared_members_and_diagnostic_mode_keep_required_pairs():
    p = Problem(
        tuple(Node(i, i) for i in "abcd"),
        (
            Assembly("left", "Left", ("a", "b", "c")),
            Assembly("right", "Right", ("b", "c", "d")),
            Assembly("root", "Root", ("left", "right")),
        ),
    )
    pairs = set(collision_pairs(p))
    assert ("b", "c") in pairs  # Identical overlapping membership signatures.
    assert ("a", "d") not in pairs  # Separation follows from strict exclusion.
    assert ("left", "right") in pairs  # Overlapping frames still need separate headers.
    assert ("a", "root") not in pairs  # Containment keeps the root header above A.
    diagnostic = set(collision_pairs(p, strict=False))
    assert ("a", "d") in diagnostic and ("a", "right") in diagnostic
    # Padding alone must not excuse a larger required clearance.
    tight = set(collision_pairs(replace(p, padding=0, gap=20)))
    assert ("a", "root") in tight and ("left", "root") in tight


@pytest.mark.z3
def test_exclusion_and_containment_imply_separation_for_all_rectangles():
    import z3

    # Quantifier-free UNSAT proves the implication for arbitrary positive
    # rectangles and nonnegative clearance, not just one generated layout.
    ax, ay, aw, ah, bx, by, bw, bh, gx, gy, gw, gh, gap = z3.Ints(
        "ax ay aw ah bx by bw bh gx gy gw gh gap"
    )

    def apart(x, y, w, h, u, v, sw, sh):
        return z3.Or(
            x + w + gap <= u, u + sw + gap <= x, y + h + gap <= v, v + sh + gap <= y
        )

    solver = z3.Solver()
    solver.add(
        aw > 0,
        ah > 0,
        bw > 0,
        bh > 0,
        gw > 0,
        gh > 0,
        gap >= 0,
        bx >= gx,
        by >= gy,
        bx + bw <= gx + gw,
        by + bh <= gy + gh,
        apart(ax, ay, aw, ah, gx, gy, gw, gh),
        z3.Not(apart(ax, ay, aw, ah, bx, by, bw, bh)),
    )
    assert solver.check() == z3.unsat
    # The contained rectangle can be another node OR the group's header.


@pytest.mark.z3
def test_padding_at_least_clearance_separates_ancestor_header():
    import z3

    gy, header, padding, gap, child_y = z3.Ints("gy header padding gap child_y")
    solver = z3.Solver()
    solver.add(
        header > 0,
        padding >= gap,
        gap >= 0,
        child_y >= gy + header + padding,
        gy + header + gap > child_y,
    )
    assert solver.check() == z3.unsat
