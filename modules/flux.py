import itertools
import pandas as pd
import numpy as np
import numpy_financial as npf
import pyxirr
from typing import Dict, Union

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

    def display(self):
        print('Name: ' + self.name)
        print('Units: ' + self.units.__doc__)
        print('Movements: ')
        print(self.movements.to_markdown())

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
                   total: Union[float, modules.distribution.Distribution],
                   index: pd.PeriodIndex,
                   distribution: modules.distribution.Distribution,
                   units: Units.Type):
        """
        Generate a Flow from a total amount, distributed over the period index
        according to a specified distribution curve.
        Also accepts a Distribution as a total amount input;
        which will be sampled in order to generate the Flow.

        :param name: The name of the Flow
        :param total: An amount (or Distribution to be sampled)
        :param index: A pd.PeriodIndex of dates
        :param distribution: A Distribution guiding how to distribute the amount over the index
        :param units: The Units of the Flow
        """

        if isinstance(total, float):
            total = total
        elif isinstance(total, modules.distribution.Distribution):
            total = total.sample(size=1)[0]

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
                     initial: Union[float, modules.distribution.Distribution],
                     index: pd.PeriodIndex,
                     distribution: modules.distribution.Distribution,
                     units: Units.Type):
        """
        Generate a Flow from an initial amount, distributed over the period index
        according to the factor of the specified Distribution (where initial factor = 1).
        Also accepts a Distribution as an initial amount input;
        which will be sampled in order to generate the first amount.

        :param name: The name of the Flow
        :param initial: An amount (or Distribution to be sampled)
        :param index: A pd.PeriodIndex of dates
        :param distribution: A Distribution guiding how to distribute the amount over the index
        :param units: The Units of the Flow
        """

        if isinstance(initial, float):
            initial = initial
        elif isinstance(initial, modules.distribution.Distribution):
            total = initial.sample(size=1)[0]

        if isinstance(distribution, modules.distribution.Uniform):
            movements = [initial for i in range(len(index))]
            return Flow.from_periods(name=name, periods=index, data=movements, units=units)
        elif isinstance(distribution, modules.distribution.Exponential):
            # parameters = [x / (index.size - 1) for x in range(index.size)]
            parameters = np.linspace(0, 1, num=index.size + 1)
            movements = [initial * factor for factor in
                         distribution.factor(parameters=np.delete(parameters, -1))]
            return Flow.from_periods(name=name, periods=index, data=movements, units=units)

    def invert(self):
        """
        Returns a Flow with movement values inverted (multiplied by -1)
        """
        return Flow(
            movements=self.movements.copy(deep=True).multiply(-1),
            units=self.units,
            name=self.name)

    def collapse(self):
        """
        Returns a Flow whose movements collapse (are summed) to the last period
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

    def to_aggregation(self,
                      periodicity_type: Periodicity.Type,
                      name: str = None):
        return modules.flux.Aggregation(
            name=name if name is not None else self.name,
            affluents=[self],
            periodicity_type=periodicity_type)


class Aggregation:
    """
    A `Aggregation` collects affluent (tributary/upstream) Flows
    and resamples them with a specified periodicity.
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
            raise Exception("Input Flows have dissimilar units. Cannot aggregate into Aggregation.")

        # Affluents:
        self._affluents = affluents
        """The set of input Flows that are aggregated in this Aggregation"""

        # Periodicity Type:
        self.periodicity_type = periodicity_type

        # Aggregation:
        affluents_dates = list(
            itertools.chain.from_iterable(list(affluent.movements.index.array) for affluent in self._affluents))
        self.start_date = min(affluents_dates)
        self.end_date = max(affluents_dates)
        resampled_affluents = [affluent.resample(periodicity_type=self.periodicity_type) for affluent in
                               self._affluents]

        self.aggregation = pd.concat([resampled.movements for resampled in resampled_affluents], axis=1).fillna(0)
        """
        A pd DataFrame of the Aggregation's affluent Flows resampled into the Aggregation's periodicity
        """

    def extract(self, flow_name: str):
        """
        Extract a Aggregation's resampled affluent as a Flow
        :param flow_name:
        :return:
        """
        return Flow(
            movements=self.aggregation[flow_name],
            units=self.units,
            name=flow_name
            )

    def sum(self, name: str = None):
        """
        Returns a Flow whose movements are the sum of the Aggregation's affluents by period
        :return: Flow
        """
        return modules.flux.Flow.from_periods(
            name=name if name is not None else self.name,
            periods=self.aggregation.index.to_period(),
            data=self.aggregation.sum(axis=1).to_list(),
            units=self.units)

    def collapse(self):
        """
        Returns a Aggregation with Flows' movements collapsed (summed) to the Aggregation's final period
        :return: Aggregation
        """
        affluents = [self.extract(flow_name=flow_name) for flow_name in list(self.aggregation.columns)]
        return modules.flux.Aggregation(
            name=self.name,
            affluents=[affluent.sum() for affluent in affluents],
            periodicity_type=self.periodicity_type)

    def append(self, affluents: [Flow]):
        # Check Units:
        if any(flow.units != self.units for flow in affluents):
            raise Exception("Input Flows have dissimilar units. Cannot aggregate into Aggregation.")

        # Append Affluents:
        self._affluents.extend(affluents)

        # Aggregation:
        affluents_dates = list(
            itertools.chain.from_iterable(list(flow.movements.index.array) for flow in self._affluents))
        self.start_date = min(affluents_dates)
        self.end_date = max(affluents_dates)
        resampled_affluents = [affluent.resample(periodicity_type=self.periodicity_type) for affluent in
                               self._affluents]

        self.aggregation = pd.concat([resampled.movements for resampled in resampled_affluents], axis=1).fillna(0)

    def resample(self, periodicity_type: Periodicity.Type):
        return modules.flux.Aggregation(
            name=self.name,
            affluents=self._affluents,
            periodicity_type=periodicity_type)

    @classmethod
    def merge(cls,
              aggregations,
              name: str,
              periodicity_type: Periodicity.Type):
        # Check Units:
        if any(aggregation.units != aggregations[0].units for aggregation in aggregations):
            raise Exception("Input Aggregations have dissimilar units. Cannot merge into Aggregation.")

        # Affluents:
        affluents = [affluent for aggregation in aggregations for affluent in aggregation._affluents]

        return Aggregation(
            name=name,
            affluents=affluents,
            periodicity_type=periodicity_type)
