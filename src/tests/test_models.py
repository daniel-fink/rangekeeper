# Pytests file.
# Note: gathers tests according to a naming convention.
# By default any file that is to contain tests must be named starting with 'test_',
# classes that hold tests must be named starting with 'Test',
# and any function in a file that should be treated as a test must also start with 'test_'.
import datetime
import locale
import math

import matplotlib.pyplot as plt
import pandas as pd

import rangekeeper as rk
import tests

# matplotlib.use('TkAgg')
plt.style.use("seaborn-v0_8")  # pretty matplotlib plots
plt.rcParams["figure.figsize"] = (12, 8)

locale.setlocale(locale.LC_ALL, "en_AU")
units = rk.measure.Index.registry
currency = rk.measure.register_currency(registry=units)


class TestLinear:
    def test_linear_model(self):
        base_params = {
            "units": currency.units,
            "start_date": datetime.date(2020, 1, 1),
            "num_periods": 10,
            "acquisition_price": 1000,
            "frequency": rk.duration.Type.YEAR,
            "growth_rate": 0.02,
            "initial_pgi": 100.0,
            "vacancy_rate": 0.05,
            "opex_pgi_ratio": 0.35,
            "capex_pgi_ratio": 0.10,
            "cap_rate": 0.05,
            "discount_rate": 0.07,
        }

        linear = tests.models.linear.Model(base_params)

        linear.ncf_disposition.display()
        print(linear.operation_span)
        linear.pv_sums.display()

        linear.investment_cashflows.display()
        linear.investment_cashflows.sum().display()
        print("IRR: " + str(linear.irr))
        # print("NPV @ Discount Rate: " + str(linear.))

        assert math.isclose(
            a=linear.disposition.movements.iloc[-1], b=1218.99, rel_tol=0.01
        )


class TestDeterministic:
    def test_deterministic_model(self):
        base_params = {
            "units": currency.units,
            "start_date": datetime.date(2020, 1, 1),
            "num_periods": 10,
            "frequency": rk.duration.Type.YEAR,
            "growth_rate": 0.02,
            "initial_pgi": 100.0,
            "addl_pgi_per_period": 0.0,
            "vacancy_rate": 0.05,
            "opex_pgi_ratio": 0.35,
            "capex_pgi_ratio": 0.10,
            "cap_rate": 0.05,
            "discount_rate": 0.07,
        }

        # Run model with base parameters:
        base = tests.models.deterministic.Model(base_params)

        base.pv_sums.display()
        assert base.pv_sums.movements.iloc[0] == 1000
        assert math.isclose(base.pv_sums.collapse().movements.iloc[0], 10000)

        # Adjust model to optimistic parameters:
        optimistic_params = base_params.copy()
        optimistic_params["initial_pgi"] = 110.0
        optimistic_params["addl_pgi_per_period"] = 3.0
        optimistic = tests.models.deterministic.Model(optimistic_params)
        assert math.isclose(
            a=optimistic.pv_sums.movements.iloc[9], b=1294.08, rel_tol=0.01
        )

        # Adjust the model to pessimistic parameters:
        pessimistic_params = base_params.copy()
        pessimistic_params["initial_pgi"] = 90.0
        pessimistic_params["addl_pgi_per_period"] = -3.0
        pessimistic = tests.models.deterministic.Model(pessimistic_params)
        pessimistic.pv_sums.display()
        assert math.isclose(
            a=pessimistic.pv_sums.movements.iloc[9], b=705.92, rel_tol=0.01
        )

        # Calculate expected value of the property at any period:
        exp = rk.flux.Flow(
            movements=pessimistic.pv_sums.movements * 0.5
            + optimistic.pv_sums.movements * 0.5,
            units=base_params["units"],
        )
        assert math.isclose(exp.movements.iloc[6], 1000.0)

        # Calculate the expected value with flexibility:
        exp_flex = (
            pessimistic.pv_sums.movements.iloc[0] * 0.5
            + optimistic.pv_sums.movements.iloc[9] * 0.5
        )
        assert math.isclose(a=exp_flex, b=1083.0, rel_tol=0.1)


class TestProbabilistic:
    def test_probabilistic_model(self):
        base_params = {
            "units": currency.units,
            "start_date": datetime.date(2020, 1, 1),
            "num_periods": 10,
            "acquisition_price": 1000,
            "frequency": rk.duration.Type.YEAR,
            "growth_rate": 0.02,
            "initial_pgi": 100.0,
            "space_market_dist": rk.distribution.PERT(
                peak=1.0, weighting=4.0, minimum=0.75, maximum=1.25
            ),
            "vacancy_rate": 0.05,
            "opex_pgi_ratio": 0.35,
            "capex_pgi_ratio": 0.10,
            "cap_rate": 0.05,
            "discount_rate": 0.07,
        }

        prob = tests.models.probabilistic.Model(base_params)
        prob.pv_sums.display()
        prob.investment_cashflows.display()
        prob.investment_cashflows.sum().display()
        print("IRR: " + str(prob.irr))
        print("Average annual NCF: " + str(prob.ncf.sum().movements.mean()))


class TestFlexible:
    def test_flexible_model(self):
        base_params = {
            "units": currency.units,
            "start_date": datetime.date(2020, 1, 1),
            "num_periods": 24,
            "acquisition_price": 1000,
            "frequency": rk.duration.Type.YEAR,
            "growth_rate": 0.02,
            "initial_pgi": 100.0,
            "space_market_dist": rk.distribution.PERT(
                peak=1.0, weighting=4.0, minimum=0.5, maximum=1.75
            ),
            "asset_market_dist": rk.distribution.PERT(
                peak=0.06, weighting=4.0, minimum=0.03, maximum=0.09
            ),
            "vacancy_rate": 0.05,
            "opex_pgi_ratio": 0.35,
            "capex_pgi_ratio": 0.10,
            "cap_rate": 0.05,
            "discount_rate": 0.07,
        }

        flex = tests.models.flexible.Model(base_params)
        flex.pgi_factor.display()
        flex.disposition.display()
        flex.pv_ncf_agg.display()

        flex.pv_sums.display()

        print("Reversion Date: " + str(flex.disposition_date))
        flex.investment_cashflows.display()
        flex.investment_cashflows.sum().display()
        print("IRR: " + str(flex.irr))
        print("NPV: " + str(flex.npv))
        print("Average annual NCF: " + str(flex.ncf.sum().movements.mean()))
