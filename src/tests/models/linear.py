"""Readable known-data DCF composition using canonical Flow content."""

from rangekeeper.model.flux import Flow, MissingValueHandling

from dataclasses import dataclass
from datetime import timedelta

from rangekeeper.model.measure import Quantity
from rangekeeper.model.duration import Frequency, PeriodTiming, make_periods, offset
from rangekeeper.calculations import series, projection, financial


class Model:
    """Consumer calculation example; this is not the canonical rk.Model class."""

    def __init__(self, params: dict):
        units = params["units"]
        frequency = Frequency(params["frequency"])
        periods = make_periods(
            offset(params["start_date"], frequency=Frequency.YEAR),
            frequency=frequency,
            count=params["num_periods"] + 1,
        )
        self.pgi = projection.project(
            Quantity(magnitude=params["initial_pgi"], units=units),
            periods=periods,
            method=projection.ProjectionMethod.COMPOUND,
            rate=params["growth_rate"],
        )
        self.vacancy = self.pgi.scale(-params["vacancy_rate"])
        self.egi = series.aggregate((self.pgi, self.vacancy)).flow
        self.opex = self.pgi.scale(-params["opex_pgi_ratio"])
        self.noi = series.aggregate((self.egi, self.opex)).flow
        self.capex = self.pgi.scale(-params["capex_pgi_ratio"])
        projected_ncf = series.aggregate((self.noi, self.capex)).flow
        self.ncf = Flow(units=units, movements=projected_ncf.movements[:-1])
        self.disposition = Flow.from_periods(
            periods[-2:-1],
            (projected_ncf.movements[-1].magnitude / params["cap_rate"],),
            units=units,
        )
        self.ncf_disposition = series.aggregate(
            (self.ncf, self.disposition),
            join=series.AlignmentJoin.UNION,
            missing=MissingValueHandling.ZERO,
        ).flow
        # All proceeds share one valuation origin; terminal proceeds are discounted
        # over the full holding period instead of restarting at their first sample.
        self.pv_sums = financial.calculate_pv(
            self.ncf_disposition, rate=params["discount_rate"]
        )
        acquisition_period = make_periods(
            params["start_date"], frequency=Frequency.YEAR, count=1
        )
        self.acquisition = Flow.from_periods(
            acquisition_period, (-abs(params["acquisition_price"]),), units=units
        )
        self.investment_cashflows = series.aggregate(
            (self.acquisition, self.ncf_disposition),
            join=series.AlignmentJoin.UNION,
            missing=MissingValueHandling.ZERO,
        ).flow
        self.irr = financial.calculate_irr(
            self.investment_cashflows, timing=PeriodTiming.LAST
        )
