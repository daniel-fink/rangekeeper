"""Readable known-data DCF composition using canonical Flow content."""

from dataclasses import dataclass
from datetime import timedelta
from rangekeeper.model.flow import Flow, from_periods
from rangekeeper.model.measure import Quantity
from rangekeeper.temporal import make_periods, offset
from rangekeeper.calculations import series, projection, financial


class Model:
    """Consumer calculation example; this is not the canonical rk.Model class."""

    def __init__(self, params: dict):
        units = params["units"]
        frequency = params["frequency"]
        periods = make_periods(
            offset(params["start_date"], frequency="year"),
            frequency=frequency,
            count=params["num_periods"] + 1,
        )
        self.pgi = projection.project(
            Quantity(magnitude=params["initial_pgi"], units=units),
            periods=periods,
            method="compound",
            rate=params["growth_rate"],
        )
        self.vacancy = series.scale(self.pgi, -params["vacancy_rate"])
        self.egi = series.sum_flows((self.pgi, self.vacancy)).flow
        self.opex = series.scale(self.pgi, -params["opex_pgi_ratio"])
        self.noi = series.sum_flows((self.egi, self.opex)).flow
        self.capex = series.scale(self.pgi, -params["capex_pgi_ratio"])
        projected_ncf = series.sum_flows((self.noi, self.capex)).flow
        self.ncf = Flow(
            units=units, movements=projected_ncf.movements[:-1]
        )
        self.disposition = from_periods(
            periods[-2:-1],
            (projected_ncf.movements[-1].magnitude / params["cap_rate"],),
            units=units,
        )
        self.ncf_disposition = series.sum_flows(
            (self.ncf, self.disposition), join="union", missing="zero"
        ).flow
        # All proceeds share one valuation origin; terminal proceeds are discounted
        # over the full holding period instead of restarting at their first sample.
        self.pv_sums = financial.calculate_pv(
            self.ncf_disposition, rate=params["discount_rate"]
        )
        acquisition_period = make_periods(
            params["start_date"], frequency="year", count=1
        )
        self.acquisition = from_periods(
            acquisition_period, (-abs(params["acquisition_price"]),), units=units
        )
        self.investment_cashflows = series.sum_flows(
            (self.acquisition, self.ncf_disposition), join="union", missing="zero"
        ).flow
        self.irr = financial.calculate_irr(self.investment_cashflows, timing="last_day")
