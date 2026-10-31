"""Presentation helpers shared by the walkthrough notebooks."""

from .data import data_path, load_base_plan, load_property
from .plot import (
    plot_cash_flows,
    plot_flows,
    plot_paths,
    plot_target_curve,
    show_equations,
    show_geometry,
    show_timeline,
)

__all__ = [
    "data_path",
    "load_base_plan",
    "load_property",
    "plot_cash_flows",
    "plot_flows",
    "plot_paths",
    "plot_target_curve",
    "show_equations",
    "show_geometry",
    "show_timeline",
]
