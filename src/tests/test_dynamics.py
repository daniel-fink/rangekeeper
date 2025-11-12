from __future__ import annotations

# Pytests file.
# Note: gathers tests according to a naming convention.
# By default any file that is to contain tests must be named starting with 'test_',
# classes that hold tests must be named starting with 'Test',
# and any function in a file that should be treated as a test must also start with 'test_'.
# In addition, in order to enable pytest to find all modules,
# run tests via a 'python -m pytest tests/<test_file>.py' command from the root directory of this project

import datetime
import locale

import os
from typing import List

import matplotlib.pyplot as plt
import multiprocess as mp
import numpy as np

import pandas as pd
import pint

import rangekeeper as rk

# matplotlib.use('TkAgg')
plt.style.use("seaborn-v0_8")  # pretty matplotlib plots
plt.rcParams["figure.figsize"] = (12, 8)

locale.setlocale(locale.LC_ALL, "en_AU")
units = rk.measure.Index.registry
currency = rk.measure.register_currency(registry=units)

pint.set_application_registry(rk.measure.Index.registry)
model_params = {
    "start_date": datetime.date(2001, 1, 1),
    "num_periods": 10,
    "frequency": rk.duration.Type.YEAR,
    "acquisition_cost": -1000 * currency.units,
    "initial_income": 100 * currency.units,
    "growth_rate": 0.02,
    "vacancy_rate": 0.05,
    "opex_pgi_ratio": 0.35,
    "capex_pgi_ratio": 0.1,
    "discount_rate": 0.07,
    "exit_cap_rate": 0.05,
}


class ExAnteInflexibleModel:
    def __init__(self, params: dict):
        self.params = params
        self.calc_span = rk.duration.Span.from_duration(
            name="Span to Calculate Reversion",
            date=self.params["start_date"],
            duration=self.params["frequency"],
            amount=self.params["num_periods"] + 1,
        )
        self.acq_span = rk.duration.Span.from_duration(
            name="Acquisition Span",
            date=rk.duration.offset(
                params["start_date"], amount=-1, duration=self.params["frequency"]
            ),
            duration=self.params["frequency"],
            amount=1,
        )
        self.span = self.calc_span.shift(
            name="Span", amount=-1, duration=self.params["frequency"], bound="end"
        )
        self.reversion_span = self.span.shift(
            name="Reversion Span",
            amount=9,
            duration=self.params["frequency"],
            bound="start",
        )

        self.acquisition = rk.flux.Flow.from_projection(
            name="Acquisition",
            value=self.params["acquisition_cost"],
            proj=rk.projection.Distribution(
                form=rk.distribution.Uniform(),
                sequence=self.acq_span.to_sequence(frequency=self.params["frequency"]),
            ),
            units=currency.units,
        )

        self.pgi = rk.flux.Flow.from_projection(
            name="Potential Gross Income",
            value=self.params["initial_income"],
            proj=rk.projection.Extrapolation(
                form=rk.extrapolation.Compounding(rate=self.params["growth_rate"]),
                sequence=self.calc_span.to_sequence(frequency=self.params["frequency"]),
            ),
            units=currency.units,
        )

        self.vacancy = rk.flux.Flow(
            name="Vacancy Allowance",
            movements=self.pgi.movements * -params["vacancy_rate"],
            units=currency.units,
        )
        self.egi = rk.flux.Stream(
            name="Effective Gross Income",
            flows=[self.pgi, self.vacancy],
            frequency=self.params["frequency"],
        ).sum()
        self.opex = rk.flux.Flow(
            name="Operating Expenses",
            movements=self.pgi.movements * params["opex_pgi_ratio"],
            units=currency.units,
        ).negate()
        self.noi = rk.flux.Stream(
            name="Net Operating Income",
            flows=[self.egi, self.opex],
            frequency=self.params["frequency"],
        ).sum()
        self.capex = rk.flux.Flow(
            name="Capital Expenditures",
            movements=self.pgi.movements * params["capex_pgi_ratio"],
            units=currency.units,
        ).negate()
        self.net_cfs = rk.flux.Stream(
            name="Net Annual Cashflows",
            flows=[self.noi, self.capex],
            frequency=self.params["frequency"],
        ).sum()

        self.reversions = rk.flux.Flow(
            name="Reversions",
            movements=self.net_cfs.movements.shift(periods=-1).dropna()
            / params["exit_cap_rate"],
            units=currency.units,
        ).trim_to_span(span=self.span)
        self.net_cfs = self.net_cfs.trim_to_span(span=self.span)

        self.pbtcfs = rk.flux.Stream(
            name="PBTCFs",
            flows=[
                self.net_cfs.trim_to_span(span=self.span),
                self.reversions.trim_to_span(span=self.reversion_span),
            ],
            frequency=self.params["frequency"],
        )

        pvs = []
        irrs = []
        for period in self.net_cfs.movements.index:
            cumulative_net_cfs = self.net_cfs.trim_to_span(
                span=rk.duration.Span(
                    name="Cumulative Net Cashflow Span",
                    start_date=self.params["start_date"],
                    end_date=period,
                )
            )
            reversion = rk.flux.Flow(
                movements=self.reversions.movements.loc[[period]], units=currency.units
            )
            cumulative_net_cfs_with_rev = rk.flux.Stream(
                name="Net Cashflow with Reversion",
                flows=[cumulative_net_cfs, reversion],
                frequency=self.params["frequency"],
            )
            pv = cumulative_net_cfs_with_rev.sum().pv(
                name="Present Value",
                frequency=self.params["frequency"],
                rate=self.params["discount_rate"],
            )
            pvs.append(pv.collapse().movements)

            incl_acq = rk.flux.Stream(
                name="Net Cashflow with Reversion and Acquisition",
                flows=[cumulative_net_cfs_with_rev.sum(), self.acquisition],
                frequency=self.params["frequency"],
            )

            irrs.append(round(incl_acq.sum().irr(), 4))

        self.pvs = rk.flux.Flow(
            name="Present Values", movements=pd.concat(pvs), units=currency.units
        )
        self.irrs = rk.flux.Flow(
            name="Internal Rates of Return",
            movements=pd.Series(irrs, index=self.pvs.movements.index),
            units=None,
        )


class ExPostInflexibleModel:
    def __init__(self):
        pass

    def set_params(self, params: dict):
        self.params = params

    def set_market(self, market: rk.dynamics.market.Market):
        self.market = market

    def set_spans(self):
        self.calc_span = rk.duration.Span.from_duration(
            name="Span to Calculate Reversion",
            date=self.params["start_date"],
            duration=self.params["frequency"],
            amount=self.params["num_periods"] + 1,
        )
        self.acq_span = rk.duration.Span.from_duration(
            name="Acquisition Span",
            date=rk.duration.offset(
                self.params["start_date"], amount=-1, duration=self.params["frequency"]
            ),
            duration=self.params["frequency"],
            amount=1,
        )
        self.span = self.calc_span.extend(
            name="Span",
            amount=-1,
            duration=self.params["frequency"],
            bound="end",
        )
        self.reversion_span = self.span.extend(
            name="Reversion Span",
            amount=self.params["num_periods"] - 1,
            duration=self.params["frequency"],
            bound="start",
        )

    def set_flows(self):
        self.acquisition = rk.flux.Flow.from_projection(
            name="Acquisition",
            value=self.params["acquisition_cost"],
            proj=rk.projection.Distribution(
                form=rk.distribution.Uniform(),
                sequence=self.acq_span.to_sequence(frequency=self.params["frequency"]),
            ),
            units=currency.units,
        )

        pgi = rk.flux.Flow.from_projection(
            name="Potential Gross Income",
            value=self.params["initial_income"],
            proj=rk.projection.Extrapolation(
                form=rk.extrapolation.Compounding(rate=self.params["growth_rate"]),
                sequence=self.calc_span.to_sequence(frequency=self.params["frequency"]),
            ),
            units=currency.units,
        )

        self.pgi = rk.flux.Stream(
            name="Potential Gross Income",
            flows=[pgi, self.market.space_market_price_factors],
            frequency=self.params["frequency"],
        ).product(registry=rk.measure.Index.registry)

        self.vacancy = rk.flux.Flow(
            name="Vacancy Allowance",
            movements=self.pgi.movements * -self.params["vacancy_rate"],
            units=currency.units,
        )
        self.egi = rk.flux.Stream(
            name="Effective Gross Income",
            flows=[self.pgi, self.vacancy],
            frequency=self.params["frequency"],
        ).sum()
        self.opex = rk.flux.Flow(
            name="Operating Expenses",
            movements=self.pgi.movements * self.params["opex_pgi_ratio"],
            units=currency.units,
        ).negate()
        self.noi = rk.flux.Stream(
            name="Net Operating Income",
            flows=[self.egi, self.opex],
            frequency=self.params["frequency"],
        ).sum()
        self.capex = rk.flux.Flow(
            name="Capital Expenditures",
            movements=self.pgi.movements * self.params["capex_pgi_ratio"],
            units=currency.units,
        ).negate()
        self.net_cfs = rk.flux.Stream(
            name="Net Annual Cashflows",
            flows=[self.noi, self.capex],
            frequency=self.params["frequency"],
        ).sum()

        self.reversions = rk.flux.Flow(
            name="Reversions",
            movements=self.net_cfs.movements.shift(periods=-1).dropna()
            / self.market.implied_rev_cap_rate.movements,
            units=currency.units,
        ).trim_to_span(span=self.span)
        self.net_cfs = self.net_cfs.trim_to_span(span=self.span)

        self.pbtcfs = rk.flux.Stream(
            name="PBTCFs",
            flows=[
                self.net_cfs.trim_to_span(span=self.span),
                self.reversions.trim_to_span(span=self.reversion_span),
            ],
            frequency=self.params["frequency"],
        )

    def set_metrics(self):
        pvs = []
        irrs = []
        for period in self.net_cfs.movements.index:
            cumulative_net_cfs = self.net_cfs.trim_to_span(
                span=rk.duration.Span(
                    name="Cumulative Net Cashflow Span",
                    start_date=self.params["start_date"],
                    end_date=period,
                )
            )
            reversion = rk.flux.Flow(
                movements=self.reversions.movements.loc[[period]], units=currency.units
            )
            cumulative_net_cfs_with_rev = rk.flux.Stream(
                name="Net Cashflow with Reversion",
                flows=[cumulative_net_cfs, reversion],
                frequency=self.params["frequency"],
            )
            pv = cumulative_net_cfs_with_rev.sum().pv(
                name="Present Value",
                frequency=self.params["frequency"],
                rate=self.params["discount_rate"],
            )
            pvs.append(pv.collapse().movements)

            incl_acq = rk.flux.Stream(
                name="Net Cashflow with Reversion and Acquisition",
                flows=[cumulative_net_cfs_with_rev.sum(), self.acquisition],
                frequency=self.params["frequency"],
            )

            irrs.append(round(incl_acq.sum().irr(), 4))

        self.pvs = rk.flux.Flow(
            name="Present Values", movements=pd.concat(pvs), units=currency.units
        )
        self.irrs = rk.flux.Flow(
            name="Internal Rates of Return",
            movements=pd.Series(irrs, index=self.pvs.movements.index),
            units=None,
        )

    def generate(self):
        self.set_spans()
        self.set_flows()
        self.set_metrics()

    @classmethod
    def _from_args(cls, args: tuple) -> ExPostInflexibleModel:
        params, market = args
        model = cls()
        model.set_params(params=params)
        model.set_market(market=market)
        model.generate()
        return model

    @classmethod
    def from_markets(cls, params: dict, markets: [rk.dynamics.market.Market]):
        # print('Starting multiprocessing...\n')
        # print(f'Number of markets: {len(markets)}\n')

        pool = mp.Pool(os.cpu_count())
        # print('Initiated Multiprocessing Pool...\n')

        args = [(params, market) for market in markets]
        # print('Created args...\n')
        # print(f'Number of args: {len(args)}\n')

        result = pool.map(ExPostInflexibleModel._from_args, args)
        # print('Created result...\n')

        return result

        # while not result.ready():
        #     time.sleep(1)
        #     print('Waiting for results...\n')
        # if result.successful():
        #     return result
        # else:
        #     print('Error in multiprocessing: ')
        # return result.get()


class TestDynamics:
    frequency = rk.duration.Type.YEAR
    span = rk.duration.Span.from_duration(
        name="Span",
        date=pd.Timestamp(2000, 1, 1),
        duration=frequency,
        amount=25,
    )
    sequence = span.to_sequence(frequency=frequency)

    cap_rate = 0.05
    growth_rate = -0.002537905
    initial_value = 0.050747414
    trend = rk.dynamics.trend.Trend(
        sequence=sequence,
        cap_rate=cap_rate,
        initial_value=initial_value,
        growth_rate=growth_rate,
    )

    def test_trend(self):
        assert TestDynamics.trend.initial_price_factor == 1.0
        TestDynamics.trend.display(decimals=8)

    volatility_per_period = 0.1
    autoregression_param = 0.2
    mean_reversion_param = 0.3

    volatility = rk.dynamics.volatility.Volatility(
        sequence=sequence,
        trend=trend,
        volatility_per_period=volatility_per_period,
        autoregression_param=autoregression_param,
        mean_reversion_param=mean_reversion_param,
    )

    def test_volatility(self):
        TestDynamics.volatility.autoregressive_returns.display(decimals=8)
        TestDynamics.volatility.volatility.display(decimals=8)

    space_cycle_period = 15.1
    space_cycle_phase = 14.3
    space_cycle_amplitude = 0.5
    asset_cycle_period = 16.1
    asset_cycle_phase = 15.6
    asset_cycle_amplitude = 0.02
    space_cycle_asymmetric_parameter = 0.7
    asset_cycle_asymmetric_parameter = 0.7

    cyclicality = rk.dynamics.cyclicality.Cyclicality.from_params(
        sequence=sequence,
        space_cycle_period=space_cycle_period,
        space_cycle_phase=space_cycle_phase,
        space_cycle_amplitude=space_cycle_amplitude,
        asset_cycle_period=asset_cycle_period,
        asset_cycle_phase=asset_cycle_phase,
        asset_cycle_amplitude=asset_cycle_amplitude,
        space_cycle_asymmetric_parameter=space_cycle_asymmetric_parameter,
        asset_cycle_asymmetric_parameter=asset_cycle_asymmetric_parameter,
    )

    def test_cyclicality(self):
        rk.flux.Stream(
            name="Cycles",
            flows=[
                TestDynamics.cyclicality.space_waveform,
                TestDynamics.cyclicality.asset_waveform,
            ],
            frequency=TestDynamics.frequency,
        ).plot(
            flows={
                "Space Cycle Waveform": (0, 1.6),
                "Asset Cycle Waveform": (-0.025, 0.025),
            }
        )

    noise_residual = 0.05
    noise_dist = rk.distribution.Symmetric(
        type=rk.distribution.Type.TRIANGULAR, mean=0.0, residual=noise_residual
    )

    noise = rk.dynamics.noise.Noise(sequence=sequence, noise_dist=noise_dist)

    def test_noise(self):
        print(TestDynamics.sequence.size)
        TestDynamics.noise.generate().display(decimals=8)

    black_swan_likelihood = 0.05
    black_swan_diss_rate = mean_reversion_param
    black_swan_probability = rk.distribution.Uniform()
    black_swan_impact = -0.25
    black_swan = rk.dynamics.black_swan.BlackSwan(
        sequence=sequence,
        likelihood=black_swan_likelihood,
        dissipation_rate=black_swan_diss_rate,
        probability=black_swan_probability,
        impact=black_swan_impact,
    )

    def test_black_swan(self):
        TestDynamics.black_swan.generate().display(decimals=8)

    market = rk.dynamics.market.Market(
        sequence=sequence,
        trend=trend,
        volatility=volatility,
        cyclicality=cyclicality,
        noise=noise,
        black_swan=black_swan,
    )

    iterations = 100
    growth_rate_dist = rk.distribution.Symmetric(
        type=rk.distribution.Type.TRIANGULAR, mean=-0.0005, residual=0.005
    )
    initial_value_dist = rk.distribution.Symmetric(
        type=rk.distribution.Type.TRIANGULAR, mean=0.05, residual=0.005
    )

    trends = rk.dynamics.trend.Trend.from_likelihoods(
        sequence=sequence,
        cap_rate=cap_rate,
        growth_rate_dist=growth_rate_dist,
        initial_value_dist=initial_value_dist,
        iterations=iterations,
    )
    volatilities = rk.dynamics.volatility.Volatility.from_trends(
        sequence=sequence,
        trends=trends,
        volatility_per_period=volatility_per_period,
        autoregression_param=autoregression_param,
        mean_reversion_param=mean_reversion_param,
    )
    cyclicalities = rk.dynamics.cyclicality.Cyclicality.from_likelihoods(
        sequence=sequence,
        space_cycle_phase_prop_dist=rk.distribution.Uniform(),
        space_cycle_period_dist=rk.distribution.Symmetric(
            type=rk.distribution.Type.UNIFORM, mean=15, residual=5
        ),
        space_cycle_height_dist=rk.distribution.Symmetric(
            type=rk.distribution.Type.UNIFORM, mean=0.5, residual=0
        ),
        asset_cycle_phase_diff_prop_dist=rk.distribution.Symmetric(
            type=rk.distribution.Type.UNIFORM, mean=0, residual=0.2
        ),
        asset_cycle_period_diff_dist=rk.distribution.Symmetric(
            type=rk.distribution.Type.UNIFORM, mean=0, residual=1
        ),
        asset_cycle_amplitude_dist=rk.distribution.Symmetric(
            type=rk.distribution.Type.UNIFORM, mean=0.02, residual=0.0
        ),
        space_cycle_asymmetric_parameter_dist=rk.distribution.Symmetric(
            type=rk.distribution.Type.UNIFORM, mean=0.75, residual=0.0
        ),
        asset_cycle_asymmetric_parameter_dist=rk.distribution.Symmetric(
            type=rk.distribution.Type.UNIFORM, mean=0.75, residual=0.0
        ),
        iterations=iterations,
    )
    noise = rk.dynamics.noise.Noise(
        sequence=sequence,
        noise_dist=rk.distribution.Symmetric(
            type=rk.distribution.Type.TRIANGULAR, mean=0.0, residual=0.1
        ),
    )
    black_swan = rk.dynamics.black_swan.BlackSwan(
        sequence=sequence,
        likelihood=0.05,
        dissipation_rate=mean_reversion_param,
        probability=rk.distribution.Uniform(),
        impact=-0.25,
    )
    markets = rk.dynamics.market.Market.from_likelihoods(
        sequence=sequence,
        trends=trends,
        volatilities=volatilities,
        cyclicalities=cyclicalities,
        noise=noise,
        black_swan=black_swan,
    )

    def test_likelihoods(self):
        assert len(TestDynamics.trends) == TestDynamics.iterations
        print(
            "Avg Growth Rate: {}".format(
                np.mean([market.trend.growth_rate for market in TestDynamics.markets])
                * 100
            )
        )
        print(
            "Max Growth Rate: {}".format(
                np.max([market.trend.growth_rate for market in TestDynamics.markets])
                * 100
            )
        )
        print(
            "Min Growth Rate: {}".format(
                np.min([market.trend.growth_rate for market in TestDynamics.markets])
                * 100
            )
        )

    # def test_statistics(self):
    # exanteinflex_model = ExAnteInflexibleModel(
    #     params=model_params)
    #
    # expostinflex_models = ExPostInflexibleModel.from_markets(
    #     params=model_params,
    #     markets=TestDynamics.markets)
    #
    # assert len(expostinflex_models) == TestDynamics.iterations
    # print(len(expostinflex_models))
    #
    # inflex_diffs = np.array(
    #     [(expostinflex_model.pvs.movements[-1] - exanteinflex_model.pvs.movements[-1])
    #      for expostinflex_model
    #      in expostinflex_models])
    # print('Inflex Stats: \n')
    # print('Inflex Diffs Mean: {}'.format(np.mean(inflex_diffs)))
    # print('Inflex Diffs Std: {}'.format(np.std(inflex_diffs)))
    # print('Inflex Diffs Max: {}'.format(np.max(inflex_diffs)))
    # print('Inflex Diffs Min: {}'.format(np.min(inflex_diffs)))
    # print('Inflex Diffs Median: {}'.format(np.median(inflex_diffs)))
    # print('Inflex Diffs Skew: {}'.format(ss.skew(inflex_diffs)))
    # print('Inflex Diffs Kurtosis: {}'.format(ss.kurtosis(inflex_diffs)))
    # print('Inflex Diffs t-stat: {}'.format(
    #     np.mean(inflex_diffs) /
    #     (np.std(inflex_diffs) / np.sqrt(len(inflex_diffs)))
    #     ))
    # print('Inflex Diffs t-stat from scipy: {}'.format(
    #     ss.ttest_1samp(inflex_diffs, 0)))

    def test_dynamic_modelling(self):
        model = ExPostInflexibleModel()
        model.set_params(model_params)
        model.set_market(TestDynamics.market)
        model.generate()

        print(type(model))
        print(model.params)
        print(model.irrs)

        new_params = model_params.copy()
        new_params["num_periods"] = 4
        model.set_params(new_params)
        model.generate()
        print(model.params)
        print(model.irrs)

    def test_policy(self):
        # flexible_params = model_params.copy()
        # flexible_params['num_periods'] = 25

        model = ExPostInflexibleModel()
        model.set_params(model_params)
        model.set_market(TestDynamics.market)
        # model.generate()

        def exceed_pricing_factor(state: rk.flux.Flow) -> [bool]:
            threshold = 1.5
            result = []
            for i in range(state.movements.index.size):
                if any(result):
                    result.append(False)
                else:
                    if state.movements[i] > threshold:
                        result.append(True)
                    else:
                        result.append(False)
            return result

        def adjust_hold_period(model: object, decisions: List[bool]) -> object:
            if len(decisions) != model.market.sequence.size:
                raise ValueError(
                    "Count of Decisions (outcomes of condition tests) must equal count of model periods. Decisions: {0}; Model Periods: {1}".format(
                        len(decisions), model.reversions.movements.size
                    )
                )
            else:
                try:
                    idx = decisions.index(True)
                except ValueError:
                    idx = len(decisions)
                policy_params = model.params.copy()
                policy_params["num_periods"] = idx

                model.set_params(policy_params)
                model.generate()
                return model

        # policy = rk.policy.Policy(
        #     state=model.market.space_market_price_factors,
        #     model=model,
        #     condition=exceed_pricing_factor,
        #     action=adjust_hold_period)
        #
        # result = policy.execute()
        # print(result.irrs)
        # action=action)
