# Pytests file.
# Note: gathers tests according to a naming convention.
# By default any file that is to contain tests must be named starting with 'test_',
# classes that hold tests must be named starting with 'Test',
# and any function in a file that should be treated as a test must also start with 'test_'.

import pytest
import pandas as pd
import numpy as np
import matplotlib
import matplotlib.pyplot as plt

import modules.distribution
import modules.flux
from modules.units import Units
from modules.periodicity import Periodicity

import models.linear, models.deterministic

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
            'vacancy_rate': 0.05,
            'opex_pgi_ratio': 0.35,
            'capex_pgi_ratio': 0.10,
            'cap_rate': 0.05,
            'discount_rate': 0.07
            }

        base = models.deterministic.Model(base_params)
        base.reversion.display()
        base.ncf.display()
        base.pv_ncf.display()#.to_markdown())
        base.pv_reversion.display()
        base.pv_sums.display()
