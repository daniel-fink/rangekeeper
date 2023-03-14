import pandas as pd
import scipy as sp
from numba import jit
import numba

import rangekeeper as rk


class Volatility:
    def __init__(
            self,
            trend: rk.extrapolation.Compounding,
            initial_rent: float,
            sequence: pd.PeriodIndex,
            params: dict):
        """
        This is a normal (Gaussian) distribution.
        Note that volatility is realized (new random increment is generated) in EACH period,
        so that this "risk" outcome accumulates in the history of rent levels.
        But this is just the volatility in the innovations; if there is autoregression then that will also affect the annual volatility.
        Cycles will also affect the average volatility observed empirically across the scenario.
        volatility_per_period = .08
        """

        volatilities = pd.Series(
            data=[sp.special.ndtri(rk.distribution.Uniform(lower=0, range=1).sample()) * params['volatility_per_period']
                  for x in range(sequence.size)],
            # the ndtri() function replicates excel's NORMSINV().
            # See https://stackoverflow.com/questions/20626994/how-to-calculate-the-inverse-of-the-normal-cumulative-distribution-function-in-p/20627638
            index=rk.periodicity.to_datestamps(period_index=sequence))
        # print(volatilities)

        self.volatility = rk.flux.Flow(
            movements=volatilities,
            name='Volatility')

        @jit(nopython=True)
        def calculate_autoregression(
                parameter: float,
                volatility: numba.typed.List):
            ar_returns = numba.typed.List()
            for i in range(len(volatility)):
                if i == 0:
                    ar_returns.append(volatility[0])
                else:
                    ar_returns.append(volatility[i] + (parameter * ar_returns[i - 1]))
            return ar_returns

        volatility = numba.typed.List()
        [volatility.append(x) for x in self.volatility.movements.to_list()]

        autoregression_return_data = calculate_autoregression(
            parameter=params['autoregression_param'],
            volatility=volatility)
        self.autoregressive_returns = rk.flux.Flow(
            movements=pd.Series(
                data=autoregression_return_data,
                index=self.volatility.movements.index),
            name='Autoregressive Returns')

        """
        Cumulative Volatility:
        Accumulate the volatility generated in the previous column, also reflecting the mean reversion tendency.
        """

        @jit(nopython=True)
        def calculate_volatility_accumulation(
                trend_rate: float,
                trend_values: numba.typed.List,
                mr_parameter: float,
                ar_returns: numba.typed.List):
            accumulated_volatility = numba.typed.List()
            for i in range(len(trend_values)):
                if i == 0:
                    accumulated_volatility.append(trend_values[0])
                else:
                    accumulated_volatility.append(
                        (accumulated_volatility[i - 1] * (1 + trend_rate + ar_returns[i])) +
                        (mr_parameter * (trend_values[i - 1] - accumulated_volatility[i - 1]))
                        )
            return accumulated_volatility

        trend_values = numba.typed.List()
        trend_flow = rk.flux.Flow.from_projection(
            name='Market Trend',
            value=initial_rent,
            proj=rk.projection.Extrapolation(
                form=trend,
                sequence=sequence))
        [trend_values.append(x) for x in trend_flow.movements.to_list()]

        ar_returns = numba.typed.List()
        [ar_returns.append(x) for x in self.autoregressive_returns.movements.to_list()]

        cumulative_volatility_data = calculate_volatility_accumulation(
            trend_rate=trend.rate,
            trend_values=trend_values,
            mr_parameter=params['mean_reversion_param'],
            ar_returns=ar_returns)
        self.cumulative_volatility = rk.flux.Flow(
            movements=pd.Series(
                data=cumulative_volatility_data,
                index=rk.periodicity.to_datestamps(period_index=sequence)),
            name='Cumulative Volatility')
