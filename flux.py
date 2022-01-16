import itertools
import math

import pandas as pd
import numpy as np
import numpy_financial as npf
import matplotlib.pyplot as plt
import pyxirr
from typing import Dict, Union

import distribution
from units import Units
from periodicity import Periodicity


class Flow:
    """
    A `Flow` is a pd.Series of 'movements' of material (funds, energy, mass, etc) that occur at specified dates.
    Note: the flow.movements Series index is a pd.DatetimeIndex, and its values are floats.
    """

    def __init__(self,
                 movements: pd.Series,
                 units: Units.Type,
                 name: str = None):

        if not isinstance(movements.index, pd.DatetimeIndex):
            raise Exception("Error: Flow's movements' Index is not a pd.DatetimeIndex")

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

    def plot(self, normalize: bool = False, *args, **kwargs):
        self.movements.plot(*args, **kwargs)
        plt.legend(loc='best')
        plt.xlabel('Date')
        plt.ylabel(self.units.__doc__)
        if normalize:
            plt.ylim(bottom=0)
        plt.show(block=True)

    @staticmethod
    def from_periods(periods: pd.PeriodIndex,
                     data: [float],
                     units: Units.Type,
                     name: str = None):
        """
        Returns a Flow where movement dates are defined by the end-dates of the specified periods
        """

        if periods.size != len(data):
            raise ValueError("Error: count of periods and data must match")
        dates = [pd.Timestamp(period.to_timestamp(how='end').date()) for period in periods]
        series = pd.Series(data=data,
                           index=pd.Series(data=dates, name='dates'),
                           name=name,
                           dtype=float)
        return Flow(movements=series, units=units)

    @staticmethod
    def from_dict(movements: Dict[pd.Timestamp, float],
                  units: Units.Type,
                  name: str = None):
        """
        Returns a Flow where movements are defined by key-value pairs of pd.Timestamps and amounts.
        """

        dates = movements.keys()
        series = pd.Series(data=list(movements.values()), index=pd.Series(dates, name='dates'), name=name, dtype=float)
        return Flow(movements=series, units=units, name=name)

    @staticmethod
    def from_total(total: Union[float, distribution.Distribution],
                   index: pd.DatetimeIndex,
                   dist: distribution.Distribution,
                   units: Units.Type,
                   name: str = None):
        """
        Generate a Flow from a total amount, distributed over the period index
        according to a specified distribution curve.
        Also accepts a Distribution as a total amount input;
        which will be sampled in order to generate the Flow.

        :param name: The name of the Flow
        :param total: An amount (or Distribution to be sampled)
        :param index: A pd.DateTimeIndex of dates
        :param dist: A Distribution guiding how to distribute the amount over the index
        :param units: The Units of the Flow
        """

        if isinstance(total, float):
            total = total
        elif isinstance(total, distribution.Distribution):
            total = total.sample()

        if isinstance(dist, distribution.Uniform):
            movements = [total / index.size for i in range(index.size)]
            return Flow(name=name,
                        movements=pd.Series(data=movements,
                                            index=index,
                                            name=name,
                                            dtype=float),
                        units=units)
        elif isinstance(dist, distribution.PERT):
            parameters = np.linspace(0, 1, num=(index.size + 1))
            movements = [(total * density) for density in dist.interval_density(parameters)]
            return Flow(name=name,
                        movements=pd.Series(data=movements,
                                            index=index,
                                            name=name,
                                            dtype=float),
                        units=units)
        else:
            raise NotImplementedError('Other types of distribution have not yet been implemented.')

    @staticmethod
    def from_initial(initial: Union[float, distribution.Distribution],
                     index: pd.PeriodIndex,
                     dist: distribution.Distribution,
                     units: Units.Type,
                     name: str = None):
        """
        Generate a Flow from an initial amount, distributed over the period index
        according to the factor of the specified Distribution (where initial factor = 1).
        Also accepts a Distribution as an initial amount input;
        which will be sampled in order to generate the first amount.

        :param name: The name of the Flow
        :param initial: An amount (or Distribution to be sampled)
        :param index: A pd.PeriodIndex of dates
        :param dist: A Distribution guiding how to distribute the amount over the index
        :param units: The Units of the Flow
        """

        if isinstance(initial, float):
            initial = initial
        elif isinstance(initial, distribution.Distribution):
            initial = initial.sample()

        if isinstance(dist, distribution.Uniform):
            movements = [initial for i in range(len(index))]
            return Flow.from_periods(name=name, periods=index, data=movements, units=units)
        elif isinstance(dist, distribution.Exponential):
            movements = [initial * factor for factor in dist.factor()]
            return Flow.from_periods(name=name, periods=index, data=movements, units=units)

    def invert(self):
        """
        Returns a Flow with movement values inverted (multiplied by -1)
        """
        return Flow(movements=self.movements.copy(deep=True).multiply(-1),
                    units=self.units,
                    name=self.name)

    def collapse(self):
        """
        Returns a Flow whose movements collapse (are summed) to the last period
        :return:
        """
        return Flow.from_dict(name=self.name,
                              movements={self.movements.index[-1]: self.movements.sum()},
                              units=self.units)

    def pv(self,
           periodicity: Periodicity.Type,
           discount_rate: float,
           name: str = None):
        """
        Returns a Flow with values discounted to the present (i.e. before its first period) by a specified rate
        """
        resampled = self.resample(periodicity)
        frame = resampled.movements.to_frame()
        frame.insert(0, 'index', range(resampled.movements.index.size))
        frame['Discounted Flow'] = frame.apply(
            lambda movement: movement[self.name] / math.pow((1 + discount_rate), movement['index'] + 1), axis=1)
        if name is None:
            name = 'Discounted ' + self.name
        return Flow(movements=frame['Discounted Flow'],
                    units=self.units,
                    name=name)

    def xirr(self):
        return pyxirr.xirr(dates=[datetime.date() for datetime in list(self.movements.index.array)],
                           amounts=self.movements.to_list())

    def xnpv(self, rate: float):
        return pyxirr.xnpv(rate=rate,
                           dates=[datetime.date() for datetime in list(self.movements.index.array)],
                           amounts=self.movements.to_list())

    def resample(self, periodicity: Periodicity.Type):
        """
        Returns a Flow with movements summed to specified frequency of dates
        """
        return Flow(movements=self.movements.copy(deep=True).resample(rule=periodicity.value).sum(),
                    units=self.units,
                    name=self.name)

    def to_periods(self, periodicity: Periodicity.Type):
        """
        Returns a pd.Series (of index pd.PeriodIndex) with movements summed to specified periodicity
        """
        return self.resample(periodicity=periodicity).movements \
            .to_period(freq=periodicity.value, copy=True) \
            .rename_axis('periods') \
            .groupby(level='periods') \
            .sum()

    def periodicity(self):
        return self.movements.index.freq

    def to_aggregation(self,
                       periodicity: Periodicity.Type,
                       name: str = None):
        return Aggregation(name=name if name is not None else self.name,
                           aggregands=[self],
                           periodicity=periodicity)


class Aggregation:
    """
    A `Aggregation` collects aggregand (constituent) Flows
    and resamples them with a specified periodicity.
    """

    def __init__(self,
                 name: str,
                 aggregands: [Flow],
                 periodicity: Periodicity.Type):

        # Name:
        self.name = name

        # Units:
        if all(flow.units == aggregands[0].units for flow in aggregands):
            self.units = aggregands[0].units
        else:
            raise Exception("Input Flows have dissimilar units. Cannot aggregate into Aggregation.")

        # Affluents:
        self._aggregands = aggregands
        """The set of input Flows that are aggregated in this Aggregation"""

        # Periodicity Type:
        self.periodicity = periodicity

        # Aggregation:
        aggregands_dates = list(
            itertools.chain.from_iterable(list(aggregand.movements.index.array) for aggregand in self._aggregands))
        self.start_date = min(aggregands_dates)
        self.end_date = max(aggregands_dates)

        # self.resampled_aggregands = [aggregand.resample(periodicity=self.periodicity) for aggregand in self._aggregands]
        # self.aggregation = pd.concat([resampled.movements for resampled in self.resampled_aggregands], axis=1).fillna(0)

        index = Periodicity.period_index(include_start=self.start_date,
                                         periodicity=self.periodicity,
                                         bound=self.end_date)
        _resampled_aggregands = [aggregand.to_periods(periodicity=self.periodicity) for aggregand in self._aggregands]
        self.aggregation = pd.concat(_resampled_aggregands, axis=1).fillna(0)
        """
        A pd DataFrame of the Aggregation's aggregand Flows accumulated into the Aggregation's periodicity
        """

    @staticmethod
    def from_DataFrame(name: str,
                       data: pd.DataFrame,
                       units: Units.Type):
        aggregands = []
        for column in data.columns:
            series = data[column]
            aggregands.append(Flow(movements=series, units=units, name=series.name))
        return Aggregation(name=name,
                           aggregands=aggregands,
                           periodicity=Periodicity.from_value(data.index.freqstr))

    def display(self):
        print('Name: ' + self.name)
        print('Units: ' + self.units.__doc__)
        print('Flows: ')
        print(self.aggregation.to_markdown())

    def plot(self,
             aggregands: Dict[str, tuple] = None):
        """
        Plots the specified aggregands against each respective value range (min-max)

        :param aggregands: A dictionary of aggregands to plot, by name and value range (as a tuple)
        """
        if aggregands is None:
            aggregands = {aggregand.name: None for aggregand in self._aggregands}
        dates = list(self.aggregation.index.astype(str))

        fig, host = plt.subplots(nrows=1, ncols=1)
        tkw = dict(size=4, width=1)

        datums = []
        axes = []

        host.set_xlabel('Date')
        host.set_xticklabels(host.get_xticks(), rotation=90)
        host.set_facecolor('white')
        host.grid(axis='x',
                  color='gainsboro',
                  which='major',
                  linewidth=1)
        host.grid(axis='y',
                  color='gainsboro',
                  which='major',
                  linewidth=1)
        host.grid(axis='y',
                  color='whitesmoke',
                  which='minor',
                  linestyle='-.',
                  linewidth=0.5)

        primary_aggregand = list(aggregands.keys())[0]
        primary, = host.plot(dates,
                             self.aggregation[primary_aggregand],
                             color=plt.cm.viridis(0),
                             label=primary_aggregand)
        host.spines.left.set_linewidth(1)
        host.set_ylabel(primary_aggregand)
        host.yaxis.label.set_color(primary.get_color())
        host.spines.left.set_color(primary.get_color())
        host.tick_params(axis='y', colors=primary.get_color(), **tkw)
        host.minorticks_on()

        if aggregands[primary_aggregand] is not None:
            host.set_ylim([aggregands[primary_aggregand][0], aggregands[primary_aggregand][1]])

        datums.append(primary)
        axes.append(host)

        if len(aggregands) > 1:
            secondary_aggregand = list(aggregands.keys())[1]
            right = host.twinx()
            secondary, = right.plot(dates,
                                    self.aggregation[secondary_aggregand],
                                    color=plt.cm.viridis(1 / (len(aggregands) + 1)),
                                    label=secondary_aggregand)
            right.spines.right.set_visible(True)
            right.spines.right.set_linewidth(1)
            right.set_ylabel(secondary_aggregand)
            right.grid(False)
            right.yaxis.label.set_color(secondary.get_color())
            right.spines.right.set_color(secondary.get_color())
            right.tick_params(axis='y', colors=secondary.get_color(), **tkw)
            if aggregands[secondary_aggregand] is not None:
                right.set_ylim([aggregands[secondary_aggregand][0], aggregands[secondary_aggregand][1]])

            datums.append(secondary)
            axes.append(right)

            if len(aggregands) > 2:
                for i in range(2, len(aggregands)):
                    additional_aggregand = list(aggregands.keys())[i]
                    supplementary = host.twinx()
                    additional, = supplementary.plot(dates,
                                                     self.aggregation[additional_aggregand],
                                                     color=plt.cm.viridis(i / (len(aggregands) + 1)),
                                                     label=additional_aggregand)
                    supplementary.spines.right.set_position(('axes', 1 + (i - 1) / 5))
                    supplementary.spines.right.set_visible(True)
                    supplementary.spines.right.set_linewidth(1)
                    supplementary.set_ylabel(additional_aggregand)
                    supplementary.grid(False)
                    supplementary.yaxis.label.set_color(additional.get_color())
                    supplementary.spines.right.set_color(additional.get_color())
                    supplementary.tick_params(axis='y', colors=additional.get_color(), **tkw)
                    if aggregands[additional_aggregand] is not None:
                        supplementary.set_ylim([aggregands[additional_aggregand][0], aggregands[additional_aggregand][1]])

                    datums.append(additional)
                    axes.append(supplementary)

        labels = [datum.get_label() for datum in datums]
        legend = axes[-1].legend(datums,
                                 labels,
                                 loc='best',
                                 title=self.name,
                                 facecolor="white",
                                 frameon=True,
                                 framealpha=1,
                                 borderpad=.75,
                                 edgecolor='grey')
        plt.minorticks_on()
        plt.tight_layout()

    def extract(self, flow_name: str):
        """
        Extract a Aggregation's resampled aggregand as a Flow
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
        Returns a Flow whose movements are the sum of the Aggregation's aggregands by period
        :return: Flow
        """
        return Flow.from_periods(name=name if name is not None else self.name,
                                 periods=self.aggregation.index,  # .to_period(),
                                 data=self.aggregation.sum(axis=1).to_list(),
                                 units=self.units)

    def collapse(self):
        """
        Returns a Aggregation with Flows' movements collapsed (summed) to the Aggregation's final period
        :return: Aggregation
        """
        aggregands = [self.extract(flow_name=flow_name) for flow_name in list(self.aggregation.columns)]
        return Aggregation(
            name=self.name,
            aggregands=[aggregand.collapse() for aggregand in aggregands],
            periodicity=self.periodicity)

    def append(self, aggregands: [Flow]):
        # Check Units:
        if any(flow.units != self.units for flow in aggregands):
            raise Exception("Input Flows have dissimilar units. Cannot aggregate into Aggregation.")

        # Append Affluents:
        self._aggregands.extend(aggregands)

        # Aggregation:
        aggregands_dates = list(
            itertools.chain.from_iterable(list(flow.movements.index.array) for flow in self._aggregands))
        self.start_date = min(aggregands_dates)
        self.end_date = max(aggregands_dates)
        resampled_aggregands = [aggregand.resample(periodicity=self.periodicity) for aggregand in
                                self._aggregands]

        self.aggregation = pd.concat([resampled.movements for resampled in resampled_aggregands], axis=1).fillna(0)

    def resample(self, periodicity: Periodicity.Type):
        return Aggregation(
            name=self.name,
            aggregands=self._aggregands,
            periodicity=periodicity)

    @classmethod
    def merge(cls,
              aggregations,
              name: str,
              periodicity: Periodicity.Type):
        # Check Units:
        if any(aggregation.units != aggregations[0].units for aggregation in aggregations):
            raise Exception("Input Aggregations have dissimilar units. Cannot merge into Aggregation.")

        # Aggregands:
        aggregands = [aggregand for aggregation in aggregations for aggregand in aggregation._aggregands]

        return Aggregation(
            name=name,
            aggregands=aggregands,
            periodicity=periodicity)
