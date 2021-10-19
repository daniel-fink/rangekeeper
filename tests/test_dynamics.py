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

import dynamics

matplotlib.use('TkAgg')
plt.style.use('seaborn')  # pretty matplotlib plots
plt.rcParams['figure.figsize'] = (12, 8)


class TestDynamics:
    def test_dynamics(self):
        dynamics.trend.display()