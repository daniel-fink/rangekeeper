from __future__ import annotations

import itertools
import math
from typing import Dict, Union, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pint
import rich
import yaml
import pyxirr

from . import projection, distribution, periodicity, span, measure


class Flow:
    name: str
    movements: pd.Series
    units: pint.Unit
    """
    A `Flow` is a pd.Series of 'movements' of material (funds, energy, mass, etc) that occur at specified dates.
    Note: the flow.movements Series index is a pd.DatetimeIndex, and its values are floats.
    """

    def __init__(
            self,
            movements: pd.Series,
            units: pint.Unit = None,
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
            self.units = measure.Index.registry.dimensionless
        elif isinstance(units, pint.Unit):
            self.units = units
        else:
            raise ValueError('Error: Units must be of type pint.Unit')

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
        print('Units: ' + str(self.units))
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
            units: pint.Unit,
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
            units: pint.Unit,
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
            units: pint.Unit = None,
            name: str = None) -> Flow:
        """
        Generate a Flow from a projection of a value, with an optional timing
        offset in the application of the projection to the value. (i.e., the
        projection factors/densities begin before or after the index does)

        Also accepts a Distribution as a value input, which will be randomly
        sampled.
        """

        if isinstance(value, float):
            value = value
        elif isinstance(value, distribution.Distribution):
            value = value.sample()

        if isinstance(proj, projection.Extrapolation):
            movements = value * proj.factors()

        elif isinstance(proj, projection.Distribution):
            movements = value * proj.interval_density()
        else:
            raise ValueError("Unsupported projection type")

        return cls(
            movements=movements,
            units=units,
            name=name)

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

    def trim_to_span(
            self,
            span: span.Span) -> Flow:
        """
        Returns a Flow with movements trimmed to the specified span
        """
        return self.__class__(
            movements=self.movements.copy(deep=True).truncate(
                before=span.start_date,
                after=span.end_date),
            units=self.units,
            name=self.name)

    def to_stream(
            self,
            period_type: periodicity.Type,
            name: str = None) -> Stream:
        """
        Returns a Stream with the flow as flow
        resampled at the specified periodicity
        :param period_type:
        :param name:
        """
        return Stream(
            name=name if name is not None else self.name,
            flows=[self],
            period_type=period_type)


class Stream:
    name: str
    flows: [Flow]
    period_type: periodicity.Type
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    frame: pd.DataFrame

    """
    A `Stream` collects flow (constituent) Flows
    and resamples them with a specified periodicity.
    """

    def __init__(
            self,
            name: str,
            flows: [Flow],
            period_type: periodicity.Type):

        # Name:
        self.name = name

        # Units:
        # if all(flow.units == flows[0].units for flow in flows):
        #     self.units = flows[0].units
        # else:
        #     raise Exception("Input Flows have dissimilar units. Cannot aggregate into Stream.")

        # Flows:
        self.flows = flows
        """The set of input Flows that are aggregated in this Stream"""

        self.units = {flow.name: flow.units for flow in self.flows}

        # Periodicity Type:
        self.period_type = period_type

        # Stream:
        flows_dates = list(
            itertools.chain.from_iterable(list(flow.movements.index.array) for flow in self.flows))
        self.start_date = min(flows_dates)
        self.end_date = max(flows_dates)

        index = periodicity.period_index(
            include_start=self.start_date,
            period_type=self.period_type,
            bound=self.end_date)
        _resampled_flows = [flow.to_periods(period_type=self.period_type) for flow in self.flows]
        self.frame = pd.concat(_resampled_flows, axis=1).fillna(0).sort_index()
        """
        A pd.DataFrame of the Stream's flow Flows accumulated into the Stream's periodicity
        """

    def __str__(self):
        return self.display()

    def duplicate(self) -> Stream:
        return self.__class__(
            name=self.name,
            flows=[flow.duplicate() for flow in self.flows],
            period_type=self.period_type)

    @classmethod
    def from_DataFrame(
            cls,
            name: str,
            data: pd.DataFrame,
            units: pint.Unit) -> Stream:
        flows = []
        for column in data.columns:
            series = data[column]
            flows.append(
                Flow(
                    movements=series,
                    units=units,
                    name=series.name))
        return cls(
            name=name,
            flows=flows,
            period_type=periodicity.from_value(data.index.freqstr))

    def display(
            self,
            decimals: int = 2):

        print('\n')
        print('Name: ' + self.name)
        print('Units: ')
        rich.print(self.units)
        print('Flows: ')

        floatfmt = "." + str(decimals) + "f"

        print(self.frame.to_markdown(
            tablefmt='github',
            floatfmt=floatfmt))

    def plot(
            self,
            flows: Dict[str, tuple] = None):
        """
        Plots the specified flows against each respective value range (min-max)

        :param flows: A dictionary of flows to plot, by name and value range (as a tuple)
        """
        if flows is None:
            flows = {flow.name: None for flow in self.flows}
        dates = list(self.frame.index.astype(str))

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

        primary_flow = list(flows.keys())[0]
        primary, = host.plot(dates,
                             self.frame[primary_flow],
                             color=plt.cm.viridis(0),
                             label=primary_flow)
        host.spines.left.set_linewidth(1)
        host.set_ylabel(primary_flow)
        host.yaxis.label.set_color(primary.get_color())
        host.spines.left.set_color(primary.get_color())
        host.tick_params(axis='y', colors=primary.get_color(), **tkw)
        host.minorticks_on()

        if flows[primary_flow] is not None:
            host.set_ylim([flows[primary_flow][0], flows[primary_flow][1]])

        datums.append(primary)
        axes.append(host)

        if len(flows) > 1:
            secondary_flow = list(flows.keys())[1]
            right = host.twinx()
            secondary, = right.plot(dates,
                                    self.frame[secondary_flow],
                                    color=plt.cm.viridis(1 / (len(flows) + 1)),
                                    label=secondary_flow)
            right.spines.right.set_visible(True)
            right.spines.right.set_linewidth(1)
            right.set_ylabel(secondary_flow)
            right.grid(False)
            right.yaxis.label.set_color(secondary.get_color())
            right.spines.right.set_color(secondary.get_color())
            right.tick_params(axis='y', colors=secondary.get_color(), **tkw)
            if flows[secondary_flow] is not None:
                right.set_ylim([flows[secondary_flow][0], flows[secondary_flow][1]])

            datums.append(secondary)
            axes.append(right)

            if len(flows) > 2:
                for i in range(2, len(flows)):
                    additional_flow = list(flows.keys())[i]
                    supplementary = host.twinx()
                    additional, = supplementary.plot(dates,
                                                     self.frame[additional_flow],
                                                     color=plt.cm.viridis(i / (len(flows) + 1)),
                                                     label=additional_flow)
                    supplementary.spines.right.set_position(('axes', 1 + (i - 1) / 5))
                    supplementary.spines.right.set_visible(True)
                    supplementary.spines.right.set_linewidth(1)
                    supplementary.set_ylabel(additional_flow)
                    supplementary.grid(False)
                    supplementary.yaxis.label.set_color(additional.get_color())
                    supplementary.spines.right.set_color(additional.get_color())
                    supplementary.tick_params(axis='y', colors=additional.get_color(), **tkw)
                    if flows[additional_flow] is not None:
                        supplementary.set_ylim(
                            [flows[additional_flow][0], flows[additional_flow][1]])

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
        Extract an Stream's resampled flow as a Flow
        :param flow_name:
        :return:
        """
        return Flow.from_periods(
            name=flow_name,
            data=list(self.frame[flow_name]),
            index=self.frame.index,
            units=self.units[flow_name])

    def sum(
            self,
            name: str = None) -> Flow:
        """
        Returns a Flow whose movements are the sum of the Stream's flows by period
        :return: Flow
        """
        # Check if all units are the same:
        if not len(list(set(list(self.units.values())))) == 1:
            rich.print(self.units)
            raise ValueError("Error: summation requires all flows' units to be the same.")

        return Flow.from_periods(
            name=name if name is not None else self.name,
            index=self.frame.index,  # .to_period(),
            data=self.frame.sum(axis=1).to_list(),
            units=next(iter(self.units.values())))

    def product(
            self,
            name: str = None,
            registry: pint.UnitRegistry = None,
            scope: Optional[dict] = None) -> Flow:
        """
        Returns a Flow whose movements are the product of the Stream's flows by period
        :return: Flow
        """

        # Produce resultant units:
        # singleton = ['1 * units.' + str(value) for value in self.units.values()]
        # singleton = eval(' * '.join(singleton), scope)
        registry = registry if registry is not None else pint.UnitRegistry()
        units = measure.multiply_units(
            units=list(self.units.values()),
            registry=registry)
        reduced_units = measure.remove_dimension(
            quantity=registry.Quantity(1, units),
            dimension='[time]',
            registry=registry)

        return Flow.from_periods(
            name=name if name is not None else self.name,
            index=self.frame.index,  # .to_period(),
            data=self.frame.prod(axis=1).to_list(),
            units=reduced_units.units)

    def collapse(self) -> Stream:
        """
        Returns an Stream with Flows' movements collapsed (summed) to the Stream's final period
        :return: Stream
        """
        flows = [self.extract(flow_name=flow_name) for flow_name in list(self.frame.columns)]
        return self.__class__(
            name=self.name,
            flows=[flow.collapse() for flow in flows],
            period_type=self.period_type)

    def append(
            self,
            flows: [Flow]) -> None:
        """
        Appends a list of Flows to the Stream
        :param flows:
        :type flows:
        :return:
        :rtype:
        """
        # if any(flow.units != self.units for flow in flows):
        #     raise Exception("Input Flows have dissimilar units. Cannot aggregate into Stream.")

        # Append Flows:
        self.flows.extend(flows)

        # Append Units:
        self.units.update({flow.name: flow.units for flow in flows})

        # Stream:
        flows_dates = list(
            itertools.chain.from_iterable(list(flow.movements.index.array) for flow in self.flows))
        self.start_date = min(flows_dates)
        self.end_date = max(flows_dates)

        index = periodicity.period_index(
            include_start=self.start_date,
            period_type=self.period_type,
            bound=self.end_date)
        _resampled_flows = [flow.to_periods(period_type=self.period_type) for flow in self.flows]
        self.frame = pd.concat(_resampled_flows, axis=1).fillna(0)

    def resample(
            self,
            period_type: periodicity.Type) -> Stream:
        return Stream(
            name=self.name,
            flows=self.flows,
            period_type=period_type)

    def trim_to_span(
            self,
            span: span.Span) -> Stream:
        """
        Returns an Stream with all flows trimmed to the specified Span
        :param span:
        :return:
        """
        return self.__class__(
            name=self.name,
            flows=[flow.duplicate().trim_to_span(span) for flow in self.flows],
            period_type=self.period_type)

    @classmethod
    def merge(
            cls,
            streams,
            name: str,
            period_type: periodicity.Type) -> Stream:
        # Check Units:
        if any(stream.units != streams[0].units for stream in streams):
            raise Exception("Input Streams have dissimilar units. Cannot merge into Stream.")

        # Aggregands:
        flows = [flow for stream in streams for flow in stream.flows]

        return cls(
            name=name,
            flows=flows,
            period_type=period_type)
