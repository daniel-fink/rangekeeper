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

import models.linear

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
        # models.linear.ncf_operating.display()
        print(models.linear.pv_ncf_operating['Discounted Net Cashflows'].sum())

        # size = models.linear.pgi.movements.index.size
        # print(size)
        # print(np.linspace(0, 1, num=size + 1))
