"""Collision constraints not already implied by containment and strict exclusion.

The checker deliberately retains every original test. Diagnostic mode cannot
rely on exclusion constraints, so it restores the affected collision pairs.
"""

from itertools import combinations

from rangekeeper.adapters.cytoscape.layout.model import Problem


def collision_pairs(problem: Problem, *, strict: bool = True):
    return _collision_pairs(problem, problem.descendant_index(), strict=strict)


def _collision_pairs(problem, descendants, *, strict=True):
    """Use topology prepared locally for this formulation operation."""
    nodes = {n.id for n in problem.nodes}
    groups = {a.id for a in problem.assemblies}
    ancestors = {
        i: frozenset(a for a in groups if i in descendants[a]) for i in nodes | groups
    }
    pairs = []
    for left, right in combinations(sorted(nodes | groups), 2):
        if left in nodes and right in nodes:
            # A containing assembly that excludes the other node separates them.
            if strict and ancestors[left] != ancestors[right]:
                continue
        elif left in groups and right in groups:
            # The descendant's entire header is below its ancestor's header.
            if problem.padding >= problem.gap and (
                left in ancestors[right] or right in ancestors[left]
            ):
                continue
        else:
            node, group = (left, right) if left in nodes else (right, left)
            if group in ancestors[node]:
                if problem.padding >= problem.gap:
                    continue
            elif strict:
                # Separation from the frame implies separation from its header.
                continue
        pairs.append((left, right))
    return tuple(pairs)
