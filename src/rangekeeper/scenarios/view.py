"""Typed Market access over canonical Values in one immutable Model revision."""

from dataclasses import dataclass
from ..model import Model, Value
from ..model.scenario import ScenarioRealization


@dataclass(frozen=True)
class Market:
    """Read-only view of one recorded market scenario, without duplicated content.

    Named properties resolve canonical Values, whose ``flow`` holds the data.
    The selected realization must belong to the supplied Model revision. Missing
    components raise KeyError (for example, independent paths have no cycles).
    Access never samples, calculates, solves or writes to storage.
    """

    model: Model
    realization: ScenarioRealization

    def __post_init__(self) -> None:
        records = self.model.provenance.scenarios if self.model.provenance else ()
        if self.realization not in (records or ()):
            raise ValueError("Market realization must belong to the Model revision")
        if not self.realization.outputs:
            raise ValueError(
                "Market requires realized outputs; realize captured inputs first"
            )

    def resolve_input(self, name: str) -> Value:
        """Resolve a captured input by its local name; absent names raise KeyError."""
        return self._resolve(name, self.realization.inputs)

    def resolve_output(self, name: str) -> Value:
        """Resolve a realized path by its local name; absent names raise KeyError."""
        return self._resolve(name, self.realization.outputs)

    def _resolve(self, name, bindings):
        matches = [v for v in bindings if v.name == name]
        if len(matches) != 1:
            raise KeyError(name)
        return self.model.value(matches[0].value)

    def value(self, name: str) -> Value:
        """Resolve one declared name; ambiguous or absent names fail with KeyError."""
        return self._resolve(
            name, (*self.realization.inputs, *self.realization.outputs)
        )

    @property
    def trend(self) -> Value:
        """Recorded rental trend before volatility or cycles."""
        return self.resolve_output("trend")

    @property
    def cumulative_volatility(self) -> Value:
        """Rental level after accumulated returns and mean reversion; not an increment."""
        return self.resolve_output("cumulative_volatility")

    @property
    def autoregressive_returns(self) -> Value:
        """Return innovations after autoregression, before level accumulation."""
        return self.resolve_output("autoregressive_returns")

    @property
    def space_cycle(self) -> Value:
        """Cycle variation around zero; the rental multiplier is one plus this Value."""
        return self.resolve_output("space_cycle")

    @property
    def asset_cycle(self) -> Value:
        """Cycle variation subtracted from the long-run capitalization rate."""
        return self.resolve_output("asset_cycle")

    @property
    def space_market(self) -> Value:
        """Rental level with volatility and the space-cycle multiplier applied."""
        return self.resolve_output("space_market")

    @property
    def asset_market(self) -> Value:
        """Capitalization rates after applying the asset cycle."""
        return self.resolve_output("asset_market")

    @property
    def asset_true_value(self) -> Value:
        """Normalized asset values before deal noise and the Black Swan effect."""
        return self.resolve_output("asset_true_value")

    @property
    def space_market_price_factors(self) -> Value:
        """Dimensionless rental multipliers relative to the declared initial rental level."""
        return self.resolve_output("space_market_price_factors")

    @property
    def noise(self) -> Value:
        """Recorded deal-level noise variation around zero; not accumulated returns."""
        return self.resolve_output("noise_effect")

    @property
    def black_swan(self) -> Value:
        """Recorded once-per-scenario shock effect, with amplitude already applied."""
        return self.resolve_output("shock_effect")

    @property
    def noisy_value(self) -> Value:
        """Normalized asset values after deal noise, before the Black Swan effect."""
        return self.resolve_output("noisy_value")

    @property
    def historical_value(self) -> Value:
        """Complete simulated asset-value path, including noise and shock effects."""
        return self.resolve_output("historical_value")

    @property
    def implied_reversion_cap_rates(self) -> Value:
        """Next-period income divided by current value; available only with that income."""
        return self.resolve_output("implied_reversion_cap_rates")

    @property
    def returns(self) -> Value:
        """Forward value changes; observation availability follows the later input."""
        return self.resolve_output("returns")
