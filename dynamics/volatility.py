import pandas as pd
import scipy as sp
from numba import jit

try:
    import distribution
    import dynamics.trend
    import flux
except:
    import modules.rangekeeper.distribution
    import modules.rangekeeper.dynamics.trend
    import modules.rangekeeper.flux


class Volatility:
    def __init__(
            self,
            trend: dynamics.trend.Trend,
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
            data=[sp.special.ndtri(distribution.Uniform(lower=0, range=1).sample()) * params['volatility_per_period']
                  for x in range(trend.trend.movements.index.size)],
            # the ndtri() function replicates excel's NORMSINV().
            # See https://stackoverflow.com/questions/20626994/how-to-calculate-the-inverse-of-the-normal-cumulative-distribution-function-in-p/20627638
            index=trend.trend.movements.index)

        self.volatility = flux.Flow(
            movements=volatilities,
            name='Volatility')

        @jit(nopython=True)
        def calculate_autoregression(
                parameter: float,
                volatility: [float]):
            ar_returns = []
            for i in range(len(volatility)):
                if i == 0:
                    ar_returns.append(volatility[0])
                else:
                    ar_returns.append(volatility[i] + (parameter * ar_returns[i - 1]))
            return ar_returns

        autoregression_return_data = calculate_autoregression(
            parameter=params['autoregression_param'],
            volatility=self.volatility.movements.to_list())
        self.autoregressive_returns = flux.Flow(
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
                trend: [float],
                mr_parameter: float,
                ar_returns: [float]):
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

        cumulative_volatility_data = calculate_volatility_accumulation(
            trend_rate=trend.trend_rate,
            trend=trend.trend.movements.to_list(),
            mr_parameter=params['mean_reversion_param'],
            ar_returns=self.autoregressive_returns.movements.to_list())
        self.cumulative_volatility = flux.Flow(
            movements=pd.Series(
                data=cumulative_volatility_data,
                index=trend.trend.movements.index),
            name='Cumulative Volatility')
