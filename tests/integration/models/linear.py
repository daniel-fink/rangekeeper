"""Readable known-data DCF composition using canonical Flow content."""

from rangekeeper import profile
from rangekeeper.duration import Frequency, Periods, PeriodTiming, offset
from rangekeeper.finance import financial
from rangekeeper.flow import AlignmentJoin, Flow, MissingValueHandling
from rangekeeper.quantity import Quantity
from tests.streams import lines


class Model:
    """Consumer calculation example; this is not the canonical rk.Model class."""

    def __init__(self, params: dict):
        units = params["units"]
        frequency = Frequency(params["frequency"])
        periods = Periods(
            start=offset(value=params["start_date"], frequency=Frequency.YEAR),
            frequency=frequency,
            count=params["num_periods"] + 1,
        )
        self.pgi = Flow.from_profile(
            profile=profile.Compounding(
                rate=Quantity(magnitude=params["growth_rate"], units="pa")
            ),
            periods=periods,
            initial=Quantity(magnitude=params["initial_pgi"], units=units),
        )
        self.vacancy = self.pgi.scale(-params["vacancy_rate"])
        self.egi = lines((self.pgi, self.vacancy)).aggregate().flow
        self.opex = self.pgi.scale(-params["opex_pgi_ratio"])
        self.noi = lines((self.egi, self.opex)).aggregate().flow
        self.capex = self.pgi.scale(-params["capex_pgi_ratio"])
        projected_ncf = lines((self.noi, self.capex)).aggregate().flow
        self.ncf = Flow(units=units, movements=projected_ncf.movements[:-1])
        self.disposition = Flow.from_periods(
            periods[-2:-1],
            (projected_ncf.movements[-1].number / params["cap_rate"],),
            units=units,
        )
        self.ncf_disposition = (
            lines(
                (self.ncf, self.disposition),
                join=AlignmentJoin.UNION,
                missing=MissingValueHandling.ZERO,
            )
            .aggregate()
            .flow
        )
        # All proceeds share one valuation origin; terminal proceeds are discounted
        # over the full holding period instead of restarting at their first sample.
        self.pv_sums = financial.calculate_pv(
            self.ncf_disposition, rate=params["discount_rate"]
        )
        acquisition_period = Periods(
            start=params["start_date"], frequency=Frequency.YEAR, count=1
        )
        self.acquisition = Flow.from_periods(
            acquisition_period, (-abs(params["acquisition_price"]),), units=units
        )
        self.investment_cashflows = (
            lines(
                (self.acquisition, self.ncf_disposition),
                join=AlignmentJoin.UNION,
                missing=MissingValueHandling.ZERO,
            )
            .aggregate()
            .flow
        )
        self.irr = financial.calculate_irr(
            self.investment_cashflows, timing=PeriodTiming.LAST
        )
