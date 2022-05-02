from __future__ import annotations

import itertools
import math
from typing import Dict, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyxirr

try:
    import projection
    import distribution
    import periodicity
    from phase import Phase
    import measure
    from measure import Measure

except:
    import modules.rangekeeper.projection as projection
    import modules.rangekeeper.distribution as distribution
    import modules.rangekeeper.periodicity as periodicity
    from modules.rangekeeper.phase import Phase
    import modules.rangekeeper.measure as measure
    from modules.rangekeeper.measure import Measure


class Flow:
    name: str
    movements: pd.Series
    units: Measure
    """
    A `Flow` is a pd.Series of 'movements' of material (funds, energy, mass, etc) that occur at specified dates.
    Note: the flow.movements Series index is a pd.DatetimeIndex, and its values are floats.
    """

    def __init__(
            self,
            movements: pd.Series,
            units: Measure = None,
            name: str = None):
        """
        Initializes a Flow. If units are not provided, a scalar (dimensionless) unit is assumed.

        :param movements:
        :type movements:
        :param units:
        :type units:
        :param name:
        :type name:
        """

        if not isinstance(movements.index, pd.DatetimeIndex):
            raise Exception("Error: Flow's movements' Index is not a pd.DatetimeIndex")

        self.movements = movements
        if name:
            self.name = name
            movements.name = name
        else:
            self.name = str(self.movements.name)

        if units is None:
            self.units = measure.scalar
        else:
            self.units = units

    def __str__(self):
        return self.display()

    def duplicate(self) -> Flow:
        return self.__class__(
            movements=self.movements.copy(deep=True),
            units=self.units,
            name=self.name)

    def display(
            self,
            decimals: int = 2):

        print('\n')
        print('Name: ' + self.name)
        print('Units: ' + self.units.name)
        print('Movements: ')

        floatfmt = "." + str(decimals) + "f"

        print(self.movements.to_markdown(
            tablefmt='github',
            floatfmt=floatfmt))

    def plot(
            self,
            normalize: bool = False,
            *args, **kwargs):
        self.movements.plot(*args, **kwargs)
        plt.legend(loc='best')
        plt.xlabel('Date')
        plt.ylabel(self.units.__doc__)
        if normalize:
            plt.ylim(bottom=0)
        plt.show(block=True)

    @classmethod
    def from_periods(
            cls,
            index: pd.PeriodIndex,
            data: [float],
            units: Measure,
            name: str = None) -> Flow:
        """
        Returns a Flow where movement dates are defined by the end-dates of the specified periods
        """

        if index.size != len(data):
            raise ValueError("Error: count of periods and data must match")
        dates = [pd.Timestamp(period.to_timestamp(how='end').date()) for period in index]
        series = pd.Series(
            data=data,
            index=pd.Series(data=dates, name='dates'),
            name=name,
            dtype=float)
        return cls(
            movements=series,
            units=units,
            name=name)

    @classmethod
    def from_dict(
            cls,
            movements: Dict[pd.Timestamp, float],
            units: Measure,
            name: str = None) -> Flow:
        """
        Returns a Flow where movements are defined by key-value pairs of pd.Timestamps and amounts.
        """

        dates = movements.keys()
        series = pd.Series(
            data=list(movements.values()),
            index=pd.Series(dates, name='dates'),
            name=name,
            dtype=float)
        return cls(
            movements=series,
            units=units,
            name=name)

    @classmethod
    def from_projection(
            cls,
            value: Union[float, distribution.Distribution],
            proj: projection,
            index: pd.PeriodIndex,
            units: Measure,
            name: str = None) -> Flow:
        """
        Generate a Flow from a projection of a value.
        Also accepts a Distribution as a total input which will be sampled in
        order to generate the Flow.
        :param value:
        :type value:
        :param proj:
        :type proj:
        :param index:
        :type index:
        :param units:
        :type units:
        :param name:
        :type name:
        :return:
        :rtype:
        """

        if isinstance(value, float):
            value = value
        elif isinstance(value, distribution.Distribution):
            value = value.sample()

        date_index = periodicity.to_datestamps(
            period_index=index,
            end=True)

        if isinstance(proj, projection.Extrapolation):
            movements = [(value * factor) for factor in proj.factor(index.size)]
        elif isinstance(proj, projection.Interpolation):
            parameters = np.linspace(0, 1, num=(index.size + 1))
            movements = [(value * density) for density in proj.interval_density(parameters)]
        else:
            raise ValueError("Unsupported projection type")

        return cls.from_periods(
            name=name,
            index=index,
            data=movements,
            units=units)

    # @classmethod
    # def from_distributed_total(
    #         cls,
    #         total: Union[float, distribution.Distribution],
    #         index: pd.PeriodIndex,
    #         dist: distribution.Distribution,
    #         units: Measure,
    #         name: str = None) -> Flow:
    #     """
    #     Generate a Flow from a total amount, distributed over the period index
    #     according to a specified distribution curve.
    #     Also accepts a Distribution as a total input which will be sampled
    #     in order to generate the Flow.
    #
    #     :param name: The name of the Flow
    #     :param total: An amount (or Distribution to be sampled)
    #     :param index: A pd.PeriodIndex of periods
    #     :param dist: A Distribution guiding how to distribute the amount over the index
    #     :param units: The Units of the Flow
    #     """
    #
    #     if isinstance(total, float):
    #         total = total
    #     elif isinstance(total, distribution.Distribution):
    #         total = total.sample()
    #
    #     date_index = periodicity.to_datestamps(
    #         period_index=index,
    #         end=True)
    #
    #     if isinstance(dist, distribution.Uniform):
    #         movements = [total / index.size for i in range(index.size)]
    #         return cls.(
    #             name=name,
    #             movements=pd.Series(
    #                 data=movements,
    #                 index=date_index,
    #                 name=name,
    #                 dtype=float),
    #             units=units)
    #     elif isinstance(dist, distribution.PERT):
    #         parameters = np.linspace(0, 1, num=(index.size + 1))
    #         movements = [(total * density) for density in dist.interval_density(parameters)]
    #         return cls(
    #             name=name,
    #             movements=pd.Series(
    #                 data=movements,
    #                 index=date_index,
    #                 name=name,
    #                 dtype=float),
    #             units=units)
    #     else:
    #         raise NotImplementedError('Other types of escalations have not yet been implemented.')
    #
    # @classmethod
    # def from_extrapolated_initial(
    #         cls,
    #         initial: Union[float, distribution.Distribution],
    #         index: pd.PeriodIndex,
    #         extrapolation: projection.Extrapolation,
    #         units: Measure,
    #         name: str = None) -> Flow:
    #     """
    #     Generate a Flow from an initial amount, extrapolated over the period index
    #     according to the factor of the specified Distribution (where initial factor = 1).
    #     Also accepts a Distribution as an initial amount input which will be
    #     sampled in order to generate the first amount.
    #
    #     :param name: The name of the Flow
    #     :param initial: An amount (or Distribution to be sampled)
    #     :param index: A pd.PeriodIndex of dates
    #     :param extrapolation: An Extrapolation guiding how to project the initial over the index
    #     :param units: The Units of the Flow
    #     """
    #
    #     if isinstance(initial, float):
    #         initial = initial
    #     elif isinstance(initial, distribution.Distribution):
    #         initial = initial.sample()
    #
    #     if isinstance(extrapolation, projection.Linear):
    #         movements = [initial * factor for factor in extrapolation.factor()]
    #         return cls.from_periods(
    #             name=name,
    #             index=index,
    #             data=movements,
    #             units=units)
    #     elif isinstance(extrapolation, projection.Exponential):
    #         movements = [initial * factor for factor in extrapolation.factor()]
    #         return cls.from_periods(
    #             name=name,
    #             index=index,
    #             data=movements,
    #             units=units)

    def invert(self) -> Flow:
        """
        Returns a Flow with movement values inverted (multiplied by -1)
        """
        return self.__class__(
            movements=self.movements.copy(deep=True).multiply(-1),
            units=self.units,
            name=self.name)

    def collapse(self) -> Flow:
        """
        Returns a Flow whose movements collapse (are summed) to the last period
        :return:
        """
        return self.__class__.from_dict(
            name=self.name,
            movements={self.movements.index[-1]: self.movements.sum()},
            units=self.units)

    def pv(
            self,
            period_type: periodicity.Type,
            discount_rate: float,
            name: str = None) -> Flow:
        """
        Returns a Flow with values discounted to the present (i.e. before its first period) by a specified rate
        """
        resampled = self.resample(period_type)
        frame = resampled.movements.to_frame()
        frame.insert(0, 'index', range(resampled.movements.index.size))
        frame['Discounted Flow'] = frame.apply(
            lambda movement: movement[self.name] / math.pow((1 + discount_rate), movement['index'] + 1), axis=1)
        if name is None:
            name = 'Discounted ' + self.name
        return self.__class__(
            movements=frame['Discounted Flow'],
            units=self.units,
            name=name)

    def xirr(self) -> float:
        return pyxirr.xirr(
            dates=[datetime.date() for datetime in list(self.movements.index.array)],
            amounts=self.movements.to_list())

    def xnpv(
            self,
            rate: float) -> float:
        return pyxirr.xnpv(
            rate=rate,
            dates=[datetime.date() for datetime in list(self.movements.index.array)],
            amounts=self.movements.to_list())

    def resample(
            self,
            period_type: periodicity.Type) -> Flow:
        """
        Returns a Flow with movements summed to specified frequency of dates
        """
        return self.__class__(
            movements=self.movements.copy(deep=True).resample(rule=period_type.value).sum(),
            units=self.units,
            name=self.name)

    def to_periods(
            self,
            period_type: periodicity.Type) -> pd.Series:
        """
        Returns a pd.Series (of index pd.PeriodIndex) with movements summed to specified periodicity
        """
        return self \
            .resample(period_type=period_type) \
            .movements.to_period(freq=period_type.value, copy=True) \
            .rename_axis('periods') \
            .groupby(level='periods') \
            .sum()

    def get_frequency(self) -> str:
        return self.movements.index.freq

    def trim_to_phase(
            self,
            phase: Phase) -> Flow:
        """
        Returns a Flow with movements trimmed to the specified phase
        """
        return self.__class__(
            movements=self.movements.copy(deep=True).truncate(
                before=phase.start_date,
                after=phase.end_date),
            units=self.units,
            name=self.name)

    def to_confluence(
            self,
            period_type: periodicity.Type,
            name: str = None) -> Confluence:
        """
        Returns a Confluence with the flow as affluent
        resampled at the specified periodicity
        :param period_type:
        :param name:
        """
        return Confluence(
            name=name if name is not None else self.name,
            affluents=[self],
            period_type=period_type)


class Confluence:
    name: str
    _affluents: [Flow]
    period_type: periodicity.Type
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    current: pd.DataFrame

    """
    A `Confluence` collects affluent (constituent) Flows
    and resamples them with a specified periodicity.
    """

    def __init__(
            self,
            name: str,
            affluents: [Flow],
            period_type: periodicity.Type):

        # Name:
        self.name = name

        # Units:
        if all(flow.units == affluents[0].units for flow in affluents):
            self.units = affluents[0].units
        else:
            raise Exception("Input Flows have dissimilar units. Cannot aggregate into Confluence.")

        # Aggregands:
        self._affluents = affluents
        """The set of input Flows that are aggregated in this Confluence"""

        # Periodicity Type:
        self.period_type = period_type

        # Confluence:
        affluents_dates = list(
            itertools.chain.from_iterable(list(affluent.movements.index.array) for affluent in self._affluents))
        self.start_date = min(affluents_dates)
        self.end_date = max(affluents_dates)

        index = periodicity.period_index(
            include_start=self.start_date,
            period_type=self.period_type,
            bound=self.end_date)
        _resampled_affluents = [affluent.to_periods(period_type=self.period_type) for affluent in self._affluents]
        self.current = pd.concat(_resampled_affluents, axis=1).fillna(0)
        """
        A pd.DataFrame of the Confluence's affluent Flows accumulated into the Confluence's periodicity
        """

    def __str__(self):
        return self.display()

    def duplicate(self) -> Confluence:
        return self.__class__(
            name=self.name,
            affluents=[affluent.duplicate() for affluent in self._affluents],
            period_type=self.period_type)

    @classmethod
    def from_DataFrame(
            cls,
            name: str,
            data: pd.DataFrame,
            units: Measure) -> Confluence:
        affluents = []
        for column in data.columns:
            series = data[column]
            affluents.append(
                Flow(
                    movements=series,
                    units=units,
                    name=series.name))
        return cls(
            name=name,
            affluents=affluents,
            period_type=periodicity.from_value(data.index.freqstr))

    def display(
            self,
            decimals: int = 2):

        print('\n')
        print('Name: ' + self.name)
        print('Units: ' + self.units.name)
        print('Flows: ')

        floatfmt = "." + str(decimals) + "f"

        print(self.current.to_markdown(
            tablefmt='github',
            floatfmt=floatfmt))

    def plot(
            self,
            affluents: Dict[str, tuple] = None):
        """
        Plots the specified affluents against each respective value range (min-max)

        :param affluents: A dictionary of affluents to plot, by name and value range (as a tuple)
        """
        if affluents is None:
            affluents = {affluent.name: None for affluent in self._affluents}
        dates = list(self.current.index.astype(str))

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

        primary_affluent = list(affluents.keys())[0]
        primary, = host.plot(dates,
                             self.current[primary_affluent],
                             color=plt.cm.viridis(0),
                             label=primary_affluent)
        host.spines.left.set_linewidth(1)
        host.set_ylabel(primary_affluent)
        host.yaxis.label.set_color(primary.get_color())
        host.spines.left.set_color(primary.get_color())
        host.tick_params(axis='y', colors=primary.get_color(), **tkw)
        host.minorticks_on()

        if affluents[primary_affluent] is not None:
            host.set_ylim([affluents[primary_affluent][0], affluents[primary_affluent][1]])

        datums.append(primary)
        axes.append(host)

        if len(affluents) > 1:
            secondary_affluent = list(affluents.keys())[1]
            right = host.twinx()
            secondary, = right.plot(dates,
                                    self.current[secondary_affluent],
                                    color=plt.cm.viridis(1 / (len(affluents) + 1)),
                                    label=secondary_affluent)
            right.spines.right.set_visible(True)
            right.spines.right.set_linewidth(1)
            right.set_ylabel(secondary_affluent)
            right.grid(False)
            right.yaxis.label.set_color(secondary.get_color())
            right.spines.right.set_color(secondary.get_color())
            right.tick_params(axis='y', colors=secondary.get_color(), **tkw)
            if affluents[secondary_affluent] is not None:
                right.set_ylim([affluents[secondary_affluent][0], affluents[secondary_affluent][1]])

            datums.append(secondary)
            axes.append(right)

            if len(affluents) > 2:
                for i in range(2, len(affluents)):
                    additional_affluent = list(affluents.keys())[i]
                    supplementary = host.twinx()
                    additional, = supplementary.plot(dates,
                                                     self.current[additional_affluent],
                                                     color=plt.cm.viridis(i / (len(affluents) + 1)),
                                                     label=additional_affluent)
                    supplementary.spines.right.set_position(('axes', 1 + (i - 1) / 5))
                    supplementary.spines.right.set_visible(True)
                    supplementary.spines.right.set_linewidth(1)
                    supplementary.set_ylabel(additional_affluent)
                    supplementary.grid(False)
                    supplementary.yaxis.label.set_color(additional.get_color())
                    supplementary.spines.right.set_color(additional.get_color())
                    supplementary.tick_params(axis='y', colors=additional.get_color(), **tkw)
                    if affluents[additional_affluent] is not None:
                        supplementary.set_ylim(
                            [affluents[additional_affluent][0], affluents[additional_affluent][1]])

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

    def extract(
            self,
            flow_name: str) -> Flow:
        """
        Extract an Confluence's resampled affluent as a Flow
        :param flow_name:
        :return:
        """
        return Flow.from_periods(
            name=flow_name,
            data=list(self.current[flow_name]),
            index=self.current.index,
            units=self.units)

    def sum(
            self,
            name: str = None) -> Flow:
        """
        Returns a Flow whose movements are the sum of the Confluence's affluents by period
        :return: Flow
        """
        return Flow.from_periods(
            name=name if name is not None else self.name,
            index=self.current.index,  # .to_period(),
            data=self.current.sum(axis=1).to_list(),
            units=self.units)

    def product(
            self,
            name: str = None) -> Flow:
        """
        Returns a Flow whose movements are the product of the Confluence's affluents by period
        :return: Flow
        """
        return Flow.from_periods(
            name=name if name is not None else self.name,
            index=self.current.index,  # .to_period(),
            data=self.current.prod(axis=1).to_list(),
            units=self.units)

    def collapse(self) -> Confluence:
        """
        Returns an Confluence with Flows' movements collapsed (summed) to the Confluence's final period
        :return: Confluence
        """
        affluents = [self.extract(flow_name=flow_name) for flow_name in list(self.current.columns)]
        return self.__class__(
            name=self.name,
            affluents=[affluent.collapse() for affluent in affluents],
            period_type=self.period_type)

    def append(
            self,
            affluents: [Flow]) -> None:
        """
        Appends a list of Flows to the Confluence
        :param affluents:
        :type affluents:
        :return:
        :rtype:
        """
        # Check Units:
        if any(flow.units != self.units for flow in affluents):
            raise Exception("Input Flows have dissimilar units. Cannot aggregate into Confluence.")

        # Append Affluents:
        self._affluents.extend(affluents)

        # Confluence:
        affluents_dates = list(
            itertools.chain.from_iterable(list(affluent.movements.index.array) for affluent in self._affluents))
        self.start_date = min(affluents_dates)
        self.end_date = max(affluents_dates)

        index = periodicity.period_index(
            include_start=self.start_date,
            period_type=self.period_type,
            bound=self.end_date)
        _resampled_affluents = [affluent.to_periods(period_type=self.period_type) for affluent in self._affluents]
        self.current = pd.concat(_resampled_affluents, axis=1).fillna(0)

    def resample(
            self,
            period_type: periodicity.Type) -> Confluence:
        return Confluence(
            name=self.name,
            affluents=self._affluents,
            period_type=period_type)

    def trim_to_phase(
            self,
            phase: Phase) -> Confluence:
        """
        Returns an Confluence with all affluents trimmed to the specified Phase
        :param phase:
        :return:
        """
        return self.__class__(
            name=self.name,
            affluents=[affluent.duplicate().trim_to_phase(phase) for affluent in self._affluents],
            period_type=self.period_type)

    @classmethod
    def merge(
            cls,
            confluences,
            name: str,
            period_type: periodicity.Type) -> Confluence:
        # Check Units:
        if any(confluence.units != confluences[0].units for confluence in confluences):
            raise Exception("Input Confluences have dissimilar units. Cannot merge into Confluence.")

        # Aggregands:
        affluents = [affluent for confluence in confluences for affluent in confluence._affluents]

        return cls(
            name=name,
            affluents=affluents,
            period_type=period_type)
