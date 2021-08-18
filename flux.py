import itertools
import pandas as pd
import numpy as np
import numpy_financial as npf
import pyxirr
from typing import Dict, Type

import modules.distribution
from modules.units import Units
from modules.periodicity import Periodicity


class Flow:
    """
    A `Flow` is a pd Series of 'movements' of material (funds, energy, mass, etc) that occur at specified dates.
    Note: the flow.movements Series index is a pd.DatetimeIndex, and its values are floats.
    """

    def __init__(self,
                 movements: pd.Series,
                 units: Units.Type,
                 name: str = None):
        self.movements = movements
        if name:
            self.name = name
            movements.name = name
        else:
            self.name = str(self.movements.name)
        self.units = units

    @staticmethod
    def from_periods(name: str,
                     periods: pd.PeriodIndex,
                     data: [float],
                     units: Units.Type):
        """
        Returns a Flow where movement dates are defined by the end-dates of the specified periods
        """

        if periods.size != len(data):
            raise ValueError("Error: count of periods and data must match")
        dates = [pd.Timestamp(period.to_timestamp(how='end').date()) for period in periods]
        series = pd.Series(data=data, index=dates, name=name, dtype=float)
        return Flow(movements=series, units=units)

    @staticmethod
    def from_dict(name: str,
                  movements: Dict[pd.Timestamp, float],
                  units: Units.Type):
        dates = movements.keys()
        series = pd.Series(data=list(movements.values()), index=dates, name=name, dtype=float)
        return Flow(movements=series, units=units)

    @staticmethod
    def from_total(name: str,
                   total: float,
                   index: pd.PeriodIndex,
                   distribution: Type[modules.distribution.Distribution],
                   #: Distribution, # TODO: Need to figure out how to work inheritance testing
                   units: Units.Type):
        if isinstance(distribution, modules.distribution.Uniform):
            movements = [total / index.size for i in range(index.size)]
            return Flow.from_periods(name=name, periods=index, data=movements, units=units)
        elif isinstance(distribution, modules.distribution.PERT):
            parameters = np.linspace(0, 1, num=(index.size + 1))
            movements = [(total * density) for density in distribution.interval_density(parameters)]
            return Flow.from_periods(name=name, periods=index, data=movements, units=units)
        else:
            raise NotImplementedError('Other types of distribution have not yet been implemented.')

    @staticmethod
    def from_initial(name: str,
                     initial: float,
                     index: pd.PeriodIndex,
                     distribution: Type[modules.distribution.Distribution],
                     units: Units.Type):
        if isinstance(distribution, modules.distribution.Uniform):
            movements = [initial for i in range(len(index))]
            return Flow.from_periods(name=name, periods=index, data=movements, units=units)
        elif isinstance(distribution, modules.distribution.Exponential):
            # parameters = [x / (index.size - 1) for x in range(index.size)]
            movements = [initial * factor for factor in
                         distribution.factor(parameters=np.linspace(0, 1, num=index.size))]
            return Flow.from_periods(name=name, periods=index, data=movements, units=units)

    def invert(self):
        """
        Returns a Flow with movement values inverted (multiplied by -1)
        """
        return Flow(
            movements=self.movements.copy(deep=True).multiply(-1),
            units=self.units,
            name=self.name)

    def sum(self):
        """
        Returns a Flow whose movements are summed to the last period
        :return:
        """
        return modules.flux.Flow.from_dict(
            name=self.name,
            movements={self.movements.index[-1]: self.movements.sum()},
            units=self.units)

    def xirr(self):
        return pyxirr.xirr(
            dates=[datetime.date() for datetime in list(self.movements.index.array)],
            amounts=self.movements.to_list())

    def xnpv(self, rate: float):
        return pyxirr.xnpv(
            rate=rate,
            dates=[datetime.date() for datetime in list(self.movements.index.array)],
            amounts=self.movements.to_list())

    def resample(self, periodicity_type: Periodicity.Type):
        """
        Returns a Flow with movements redistributed across specified frequency
        """

        movements = self.movements.copy(deep=True).resample(rule=periodicity_type.value).sum()
        return Flow(movements, self.units)

    def periodicity(self):
        return self.movements.index.freq

    def to_confluence(self,
                      periodicity_type: Periodicity.Type,
                      name: str = None):
        return modules.flux.Confluence(
            name=name if name is not None else self.name,
            affluents=[self],
            periodicity_type=periodicity_type)


class Confluence:
    """
    A `Confluence` aggregates (sums) affluent (tributary/upstream) Flows over specified periods.
    """

    def __init__(self,
                 name: str,
                 affluents: [Flow],
                 periodicity_type: Periodicity.Type):

        # Name:
        self.name = name

        # Units:
        if all(flow.units == affluents[0].units for flow in affluents):
            self.units = affluents[0].units
        else:
            raise Exception("Input Flows have dissimilar units. Cannot aggregate into Confluence.")

        # Affluents:
        self._affluents = affluents
        """The set of input Flows that are aggregated in this Confluence"""

        # Periodicity Type:
        self.periodicity_type = periodicity_type

        # Confluence:
        affluents_dates = list(
            itertools.chain.from_iterable(list(affluent.movements.index.array) for affluent in self._affluents))
        self.start_date = min(affluents_dates)
        self.end_date = max(affluents_dates)
        resampled_affluents = [affluent.resample(periodicity_type=self.periodicity_type) for affluent in
                               self._affluents]

        self.confluence = pd.concat([resampled.movements for resampled in resampled_affluents], axis=1).fillna(0)
        """
        A pd DataFrame of the Confluence's affluent Flows resampled into the Confluence's periodicity
        """

    def extract(self, flow_name: str):
        """
        Extract a Confluence's resampled affluent as a Flow
        :param flow_name:
        :return:
        """
        return Flow(
            movements=self.confluence[flow_name],
            units=self.units,
            name=flow_name
            )

    def sum(self, name: str = None):
        """
        Returns a Flow whose movements are the sum of the Confluence's affluents by period
        :return: Flow
        """
        return modules.flux.Flow.from_periods(
            name=name if name is not None else self.name,
            periods=self.confluence.index.to_period(),
            data=self.confluence.sum(axis=1).to_list(),
            units=self.units)

    def collapse(self):
        """
        Returns a Confluence with Flows' movements summed to the Confluence's final period
        :return: Confluence
        """
        affluents = [self.extract(flow_name=flow_name) for flow_name in list(self.confluence.columns)]
        return modules.flux.Confluence(
            name=self.name,
            affluents=[affluent.sum() for affluent in affluents],
            periodicity_type=self.periodicity_type)

    def append(self, affluents: [Flow]):
        # Check Units:
        if any(flow.units != self.units for flow in affluents):
            raise Exception("Input Flows have dissimilar units. Cannot aggregate into Confluence.")

        # Append Affluents:
        self._affluents.extend(affluents)

        # Confluence:
        affluents_dates = list(itertools.chain.from_iterable(list(flow.movements.index.array) for flow in self._affluents))
        self.start_date = min(affluents_dates)
        self.end_date = max(affluents_dates)
        resampled_affluents = [affluent.resample(periodicity_type=self.periodicity_type) for affluent in
                               self._affluents]

        self.confluence = pd.concat([resampled.movements for resampled in resampled_affluents], axis=1).fillna(0)

    def resample(self, periodicity_type: Periodicity.Type):
        return modules.flux.Confluence(
            name=self.name,
            affluents=self._affluents,
            periodicity_type=periodicity_type)

    @classmethod
    def merge(cls,
              confluences,
              name: str,
              periodicity_type: Periodicity.Type):
        # Check Units:
        if any(confluence.units != confluences[0].units for confluence in confluences):
            raise Exception("Input Confluences have dissimilar units. Cannot merge into Confluence.")

        # Affluents:
        affluents = [affluent for confluence in confluences for affluent in confluence._affluents]

        return Confluence(
            name=name,
            affluents=affluents,
            periodicity_type=periodicity_type)