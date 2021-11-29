import pandas as pd
import scipy as sp
import numpy as np
from numba import jit
import typing

import distribution, flux, phase, periodicity, units


class RentalMarketDynamics:
    def __init__(self, params: dict):
        self.current_rent = params['initial_price_factor'] * params['cap_rate']

        """
        Initial Rent Value Distribution:
        This is a X distribution.
        Note that the random outcome is generated only once per history, here in the first year.
        There is only one "initial" rent level in a given history.
        The uncertainty is revealed in Year 1. Year 0 is fixed because it is observable already in the present.
        """

        initial_rent_dist = distribution.PERT(peak=self.current_rent,
                                              weighting=4.,
                                              minimum=self.current_rent - params['rent_error'],
                                              maximum=self.current_rent + params['rent_error'])
        self.initial_rent = initial_rent_dist.sample()
        self.initial_rent = 0.0511437

        """
        Uncertainty Distribution
        This is the realization of uncertainty in the long-run trend growth rate.
        Here we model this uncertainty with a X distribution.
        Note that the random outcome is generated only once per history.
        There is only one "long-term trend rate" in the rent growth in any given history.
        In a Monte Carlo simulation (such as you can do using a Data Table),
        a new random number would be automatically generated here for each of the (thousands of) "trials" you run.
        This is so for all of the random number generators in this workbook.
        """
        trend_dist = distribution.PERT(peak=params['trend_delta'],
                                       weighting=4.,
                                       minimum=params['trend_delta'] - params['trend_error'],
                                       maximum=params['trend_delta'] + params['trend_error'])
        self.trend_rate = trend_dist.sample()
        self.trend_rate = 0.00698263624

        """
        Trend:
        Note that the trend is geometric.
        This makes sense if this rent series will translate via a cap rate to a property asset value series,
        as asset values cannot be negative.
        """

        trend_dist = distribution.Exponential(rate=self.trend_rate,
                                              num_periods=params['phase'].duration(period_type=params['period_type'],
                                                                                   inclusive=True))
        self.trend = flux.Flow.from_initial(name='Trend',
                                            initial=self.initial_rent,
                                            index=params['phase'].to_index(params['period_type']),
                                            dist=trend_dist,
                                            units=units.Units.Type.scalar)

        """
        This is a normal (Gaussian) distribution.
        Note that volatility is realized (new random increment is generated) in EACH period,
        so that this "risk" outcome accumulates in the history of rent levels.
        But this is just the volatility in the innovations; if there is autoregression then that will also affect the annual volatility.
        Cycles will also affect the average volatility observed empirically across the scenario.
        volatility_per_period = .08
        """

        volatilities_duration = params['phase'].duration(period_type=params['period_type'], inclusive=True)
        volatilities = pd.Series(data=[sp.special.ndtri(distribution.Uniform().sample()) * params['volatility_per_period']
                                       for x in range(volatilities_duration)],
                                 # the ndtri() function replicates excel's NORMSINV().
                                 # See https://stackoverflow.com/questions/20626994/how-to-calculate-the-inverse-of-the-normal-cumulative-distribution-function-in-p/20627638
                                 index=periodicity.Periodicity.to_datestamps(params['phase'].to_index(params['period_type'])))

        self.volatility = flux.Flow(movements=volatilities,
                                    units=units.Units.Type.scalar,
                                    name='Volatility')

        @jit(nopython=True)
        def calculate_autoregression(parameter: float,
                                     volatility: [float]):
            ar_returns = []
            for i in range(len(volatility)):
                if i == 0:
                    ar_returns.append(volatility[0])
                else:
                    ar_returns.append(volatility[i] + (parameter * ar_returns[i - 1]))
            return ar_returns

        autoregression_return_data = calculate_autoregression(parameter=params['autoregression_param'],
                                                              volatility=self.volatility.movements.to_list())
        self.autoregressive_returns = flux.Flow(movements=pd.Series(data=autoregression_return_data,
                                                                    index=self.volatility.movements.index),
                                                units=units.Units.Type.scalar,
                                                name='Autoregressive Returns')

        """
        Cumulative Volatility:
        Accumulate the volatility generated in the previous column, also reflecting the mean reversion tendency.
        """

        @jit(nopython=True)
        def calculate_volatility_accumulation(trend_rate: float,
                                              trend: [float],
                                              mr_parameter: float,
                                              ar_returns: [float],
                                              ):
            accumulated_volatility = []
            for i in range(len(trend)):
                if i == 0:
                    accumulated_volatility.append(trend[0])
                else:
                    accumulated_volatility.append(
                        (accumulated_volatility[i - 1] * (1 + trend_rate + ar_returns[i])) +
                        (mr_parameter * (trend[i - 1] - accumulated_volatility[i - 1]))
                        )
            return accumulated_volatility

        cumulative_volatility_data = calculate_volatility_accumulation(trend_rate=self.trend_rate,
                                                                       trend=self.trend.movements.to_list(),
                                                                       mr_parameter=params['mean_reversion_param'],
                                                                       ar_returns=self.autoregressive_returns.movements.to_list())
        self.cumulative_volatility = flux.Flow(movements=pd.Series(data=cumulative_volatility_data,
                                                                   index=self.trend.movements.index),
                                               units=units.Units.Type.scalar,
                                               name='Cumulative')

        self.volatility_frame = flux.Aggregation(name="Volatility",
                                                 aggregands=[self.trend,
                                                             self.volatility,
                                                             self.autoregressive_returns,
                                                             self.cumulative_volatility],
                                                 periodicity=params['period_type'])