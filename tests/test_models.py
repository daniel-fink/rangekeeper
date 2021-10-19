# Pytests file.
# Note: gathers tests according to a naming convention.
# By default any file that is to contain tests must be named starting with 'test_',
# classes that hold tests must be named starting with 'Test',
# and any function in a file that should be treated as a test must also start with 'test_'.

import math
import pandas as pd
import numpy as np
import matplotlib
import matplotlib.pyplot as plt

import distribution
import flux
from units import Units
from periodicity import Periodicity

import models.linear, models.deterministic, models.probabilistic, models.flexible

matplotlib.use('TkAgg')
plt.style.use('seaborn')  # pretty matplotlib plots
plt.rcParams['figure.figsize'] = (12, 8)


class TestLinear:
    def test_linear_model(self):
        # models.linear.pgi.display()
        # models.linear.vacancy.display()
        # models.linear.egi.sum().display()
        # models.linear.opex.display()
        # models.linear.noi.sum().display()
        # models.linear.capex.display()
        # models.linear.ncf.sum().display()
        # models.linear.reversion.display()
        # models.linear.ncf.display()
        # models.linear.ncf_operating.display()
        models.linear.ncf_operating.display()
        print(models.linear.pv_ncf_operating['Discounted Net Cashflows'].sum())


class TestDeterministic:
    def test_deterministic_model(self):
        base_params = {
            'units': Units.Type.USD,
            'start_date': pd.Timestamp(2020, 1, 1),
            'num_periods': 10,
            'period_type': Periodicity.Type.year,
            'growth_rate': 0.02,
            'initial_pgi': 100.,
            'addl_pgi_per_period': 0.,
            'vacancy_rate': 0.05,
            'opex_pgi_ratio': 0.35,
            'capex_pgi_ratio': 0.10,
            'cap_rate': 0.05,
            'discount_rate': 0.07
            }

        # Run model with base parameters:
        base = models.deterministic.Model(base_params)

        base.pv_sums.display()
        assert base.pv_sums.movements[0] == 1000
        assert math.isclose(base.pv_sums.collapse().movements[0], 10000)

        # Adjust model to optimistic parameters:
        optimistic_params = base_params.copy()
        optimistic_params['initial_pgi'] = 110.
        optimistic_params['addl_pgi_per_period'] = 3.
        optimistic = models.deterministic.Model(optimistic_params)
        optimistic.pv_sums.display()
        assert math.isclose(a=optimistic.pv_sums.movements[9], b=1294.08, rel_tol=.01)

        # Adjust the model to pessimistic parameters:
        pessimistic_params = base_params.copy()
        pessimistic_params['initial_pgi'] = 90.
        pessimistic_params['addl_pgi_per_period'] = -3.
        pessimistic = models.deterministic.Model(pessimistic_params)
        pessimistic.pv_sums.display()
        assert math.isclose(a=pessimistic.pv_sums.movements[9], b=705.92, rel_tol=.01)

        # Calculate expected value of the property at any period:
        exp = flux.Flow(movements=pessimistic.pv_sums.movements * .5 + optimistic.pv_sums.movements * .5,
                                units=base_params['units'])
        assert math.isclose(exp.movements[6], 1000.)

        # Calculate the expected value with flexibility:
        exp_flex = pessimistic.pv_sums.movements[0] * .5 + optimistic.pv_sums.movements[9] * .5
        assert math.isclose(a=exp_flex, b=1083., rel_tol=.1)


class TestProbabilistic:
    def test_probabilistic_model(self):
        base_params = {
            'units': Units.Type.USD,
            'start_date': pd.Timestamp(2020, 1, 1),
            'num_periods': 10,
            'acquisition_price': 1000,
            'period_type': Periodicity.Type.year,
            'growth_rate': 0.02,
            'initial_pgi': 100.,
            'space_market_dist': distribution.PERT(peak=1., weighting=4.0, minimum=0.75, maximum=1.25),
            'vacancy_rate': 0.05,
            'opex_pgi_ratio': 0.35,
            'capex_pgi_ratio': 0.10,
            'cap_rate': 0.05,
            'discount_rate': 0.07
            }

        prob = models.probabilistic.Model(base_params)
        prob.pv_sums.display()
        prob.investment_cashflows.display()
        prob.investment_cashflows.sum().display()
        print("IRR: " + str(prob.irr))
        print("Average annual NCF: " + str(prob.ncf.sum().movements.mean()))


class TestFlexible:
    def test_flexible_model(self):
        base_params = {
            'units': Units.Type.USD,
            'start_date': pd.Timestamp(2020, 1, 1),
            'num_periods': 24,
            'acquisition_price': 1000,
            'period_type': Periodicity.Type.year,
            'growth_rate': 0.02,
            'initial_pgi': 100.,
            'space_market_dist': distribution.PERT(peak=1., weighting=4.0, minimum=0.5, maximum=1.75),
            'asset_market_dist': distribution.PERT(peak=0.06, weighting=4.0, minimum=0.03, maximum=0.09),
            'vacancy_rate': 0.05,
            'opex_pgi_ratio': 0.35,
            'capex_pgi_ratio': 0.10,
            'cap_rate': 0.05,
            'discount_rate': 0.07
            }

        flex = models.flexible.Model(base_params)
        flex.pgi_factor.display()
        flex.reversion.display()
        flex.pv_ncf_agg.display()

        flex.pv_sums.display()

        print("Reversion Date: " + str(flex.reversion_date))
        flex.investment_cashflows.display()
        flex.investment_cashflows.sum().display()
        print("IRR: " + str(flex.irr))
        print("NPV: " + str(flex.npv))
        print("Average annual NCF: " + str(flex.ncf.sum().movements.mean()))

