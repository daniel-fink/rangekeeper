from __future__ import annotations

import locale
import os

import itertools
import math
from typing import Dict, Union, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pint
import json
import pyxirr

import rangekeeper as rk


def _format_series(
        series: pd.Series,
        units: pint.Unit,
        decimals: int = 2):
    if units.dimensionality == '[currency]':
        formatted = pd.Series(
            data=[str(locale.currency(value, grouping=True)) for value in series],
            index=pd.Series(series.index, name='date'),
            name=series.name)
    else:
        floatfmt = "{:." + str(decimals) + "f}"
        formatted = pd.Series(
            data=[str(floatfmt.format(value)) for value in series],
            index=pd.Series(series.index, name='date'),
            name=series.name)

    return formatted


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
            units: Optional[pint.Unit] = None,
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

        if movements.dtype != float:
            try:
                movements = movements.astype(float)
            except Exception as e:
                raise Exception("Error: Flow's movements' dtype cannot be cast to float: {0}".format(str(e)))
        self.movements = movements
        if name:
            self.name = name
            movements.name = name
        else:
            self.name = str(self.movements.name)

        if units is None:
            self.units = rk.measure.Index.registry.dimensionless
        elif isinstance(units, pint.Unit):
            self.units = units
        else:
            raise ValueError('Error: Units must be of type pint.Unit')

    def __str__(self):
        return str(_format_series(
            series=self.movements,
            units=self.units))

    def _repr_html_(self):
        return _format_series(
            series=self.movements,
            units=self.units).to_markdown(
            stralign="right",
            numalign="right",
            tablefmt='html')

    def duplicate(
            self,
            name: str = None) -> Flow:
        return self.__class__(
            movements=self.movements.copy(deep=True),
            units=self.units,
            name=self.name if name is None else name)

    # def _format(
    #         self,
    #         decimals: int = 2):

    def display(
            self,
            tablefmt: str = 'github',
            decimals: int = 2):
        linebreak = os.linesep
        name = 'Name: ' + self.name
        units = 'Units: ' + str(self.units)
        movements = 'Movements: ' + linebreak + _format_series(
            series=self.movements,
            units=self.units,
            decimals=decimals).to_markdown(
            stralign="right",
            numalign="right",
            tablefmt=tablefmt,
            floatfmt='.' + str(decimals) + 'f')

        print(linebreak.join([name, units, movements, os.linesep]))
        # print(self._format(decimals=decimals) + os.linesep)

    def plot(
            self,
            bounds: Optional[Tuple[float, float]] = None,
            normalize: bool = False,
            *args, **kwargs):
        self.movements.plot(*args, **kwargs)
        plt.legend(loc='best')
        plt.xlabel('Date')
        plt.ylabel(self.units.__doc__)
        if bounds is not None:
            plt.ylim(bottom=bounds[0], top=bounds[1])
        if normalize:
            plt.ylim(bottom=0)
        plt.show(block=True)

    @classmethod
    def from_periods(
            cls,
            index: pd.PeriodIndex,
            data: [float],
            units: Optional[pint.Unit] = None,
            name: str = None) -> Flow:
        """
        Returns a Flow where movement dates are defined by the end-dates of the specified periods
        """

        if index.size != len(data):
            raise ValueError("Error: count of periods and data must match")
        dates = [pd.Timestamp(period.to_timestamp(how='end').date()) for period in index]
        series = pd.Series(
            data=data,
            index=pd.Series(data=dates, name='date'),
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
            index=pd.Series(dates, name='date'),
            name=name,
            dtype=float)
        return cls(
            movements=series,
            units=units,
            name=name)

    @classmethod
    def from_projection(
            cls,
            value: Union[float, pint.Quantity, rk.distribution.Form],
            proj: rk.projection,
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
        elif isinstance(value, pint.Quantity):
            value = value.magnitude
        elif isinstance(value, rk.distribution.Form):
            value = value.sample()[0]

        if isinstance(proj, rk.projection.Extrapolation):
            if proj.form.type == rk.extrapolation.Type.STRAIGHT_LINE or proj.form.type == rk.extrapolation.Type.RECURRING:
                movements = value + proj.terms()
            elif proj.form.type == rk.extrapolation.Type.COMPOUNDING:
                movements = value * proj.terms()
            else:
                raise ValueError("Unsupported extrapolation form")

        elif isinstance(proj, rk.projection.Distribution):
            movements = value * proj.interval_density()
        else:
            raise ValueError("Unsupported projection type: {0}".format(type(proj)))

        # movements = movements[proj.bounds[0].to_timestamp(how='start'):proj.bounds[1].to_timestamp(how='end')]  # Fix for >yearly periodicities
        # TODO: Fix for issues with >yearly periodicities inducing movements at the end of multi-year periods beyond the end of the projection

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

    def total(self) -> np.float64:
        return self.collapse().movements[0]

    def pv(
            self,
            period_type: rk.periodicity.Type,
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
            period_type: rk.periodicity.Type) -> Flow:
        """
        Returns a Flow with movements summed to specified frequency of dates
        """
        return rk.flux.Flow(
            movements=self.movements.copy(deep=True).resample(rule=period_type.value).sum(),
            units=self.units,
            name=self.name)

    def to_periods(
            self,
            period_type: rk.periodicity.Type) -> pd.Series:
        """
        Returns a pd.Series (of index pd.PeriodIndex) with movements summed to specified periodicity
        """
        return self \
            .resample(period_type=period_type) \
            .movements.to_period(freq=period_type.value, copy=True) \
            .rename_axis('period') \
            .groupby(level='period') \
            .sum()

    def get_frequency(self) -> str:
        return self.movements.index.freq

    def trim_to_span(
            self,
            span: rk.span.Span,
            name: str = None) -> Flow:
        """
        Returns a Flow with movements trimmed to the specified span
        """
        return self.__class__(
            movements=self.movements.copy(deep=True).truncate(
                before=span.start_date,
                after=span.end_date),
            units=self.units,
            name=self.name if name is None else name)

    def to_stream(
            self,
            period_type: rk.periodicity.Type,
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
    period_type: rk.periodicity.Type
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
            period_type: rk.periodicity.Type):

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

        index = rk.periodicity.period_index(
            include_start=self.start_date,
            period_type=self.period_type,
            bound=self.end_date)
        self._resampled_flows = [flow.to_periods(period_type=self.period_type) for flow in self.flows]
        self.frame = pd.concat(self._resampled_flows, axis=1).fillna(0).sort_index()
        """
        A pd.DataFrame of the Stream's flow Flows accumulated into the Stream's periodicity
        """

    def __str__(self):
        return str(self._format_flows())

    def _repr_html_(self):
        return self._format_flows().to_markdown(
            stralign="right",
            numalign="right",
            tablefmt='html',
            floatfmt=".2f")

    def _format_flows(
            self,
            decimals: int = 2) -> pd.DataFrame:

        formatted_flows = []
        for flow in self.flows:
            series = flow.to_periods(period_type=self.period_type)
            formatted_flows.append(_format_series(
                series=series,
                units=flow.units,
                decimals=decimals))
        # formatted_flows = [flow._format_movements(decimals=decimals) for flow in self._resampled_flows]
        frame = pd.concat(formatted_flows, axis=1).fillna(0).sort_index()
        return frame

    def display(
            self,
            tablefmt: str = 'github',
            decimals: int = 2):

        floatfmt = "." + str(decimals) + "f"

        linebreak = os.linesep
        name = 'Name: ' + self.name
        units = 'Units: ' + json.dumps({flow.name: flow.units.__str__() for flow in self.flows}, indent=4)
        flows = 'Flows: ' + linebreak + self._format_flows(decimals=decimals).to_markdown(
            tablefmt=tablefmt,
            stralign="right",
            numalign="right",
            floatfmt=floatfmt)

        print(linebreak.join([name, units, flows, os.linesep]))

    # def display(
    #         self,
    #         decimals: int = 2):
    #     format = self._format(decimals=decimals)
    #     print(format + os.linesep)

    def __iadd__(self, other):
        flows = self.flows
        if isinstance(other, Flow):
            flows.append(other)
        elif isinstance(other, Stream):
            flows.extend(other.flows)
        else:
            raise Exception("Cannot add type " + type(other).__name__ + " to Stream.")
        return self.__class__(
            name=self.name,
            flows=flows,
            period_type=self.period_type)

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
            period_type=rk.periodicity.from_value(data.index.freqstr))

    def plot(
            self,
            flows: Dict[str, tuple] = None,
            normalize: bool = False,
            ):
        """
        Plots the specified flows against each respective value range (min-max)

        :param flows: A dictionary of flows to plot, by name and value range (as a tuple)
        """

        flows = flows if flows is not None else {flow.name: (flow.min(), flow.max()) for flow in self._resampled_flows}
        dates = list(self.frame.index.astype(str))

        fig, host = plt.subplots(nrows=1, ncols=1)
        tkw = dict(size=4, width=1)

        datums = []
        axes = []

        host.set_xlabel('Date')
        # host.set_xticklabels(host.get_xticks(), rotation=90)
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

        primary_flow_name = list(flows.keys())[0]
        primary, = host.plot(dates,
                             self.frame[primary_flow_name],
                             color=plt.cm.viridis(0),
                             label=primary_flow_name)
        host.spines.left.set_linewidth(1)
        host.set_ylabel(primary_flow_name)
        host.yaxis.label.set_color(primary.get_color())
        host.spines.left.set_color(primary.get_color())
        host.tick_params(axis='y', colors=primary.get_color(), **tkw)

        datums.append(primary)
        axes.append(host)
        # host.minorticks_on()

        if normalize:
            for i in range(1, len(flows)):
                additional_flow_name = list(flows.keys())[i]
                additional, = host.plot(
                    dates,
                    self.frame[additional_flow_name],
                    color=plt.cm.viridis(1 / (len(flows) + 1)),
                    label=additional_flow_name)
                datums.append(additional)

        else:
            host.set_ylim([flows[primary_flow_name][0], flows[primary_flow_name][1]])

            if len(flows) > 1:
                secondary_flow_name = list(flows.keys())[1]
                right = host.twinx()
                secondary, = right.plot(dates,
                                        self.frame[secondary_flow_name],
                                        color=plt.cm.viridis(1 / (len(flows) + 1)),
                                        label=secondary_flow_name)
                right.spines.right.set_visible(True)
                right.spines.right.set_linewidth(1)
                right.set_ylabel(secondary_flow_name)
                right.grid(False)
                right.yaxis.label.set_color(secondary.get_color())
                right.spines.right.set_color(secondary.get_color())
                right.tick_params(axis='y', colors=secondary.get_color(), **tkw)
                # if flows[secondary_flow] is not None:
                right.set_ylim(bottom=flows[secondary_flow_name][0], top=flows[secondary_flow_name][1])

                datums.append(secondary)
                axes.append(right)

                if len(flows) > 2:
                    for i in range(2, len(flows)):
                        additional_flow_name = list(flows.keys())[i]
                        supplementary = host.twinx()
                        additional, = supplementary.plot(dates,
                                                         self.frame[additional_flow_name],
                                                         color=plt.cm.viridis(i / (len(flows) + 1)),
                                                         label=additional_flow_name)
                        supplementary.spines.right.set_position(('axes', 1 + (i - 1) / 7.5))
                        supplementary.spines.right.set_visible(True)
                        supplementary.spines.right.set_linewidth(1)
                        supplementary.set_ylabel(additional_flow_name)
                        supplementary.grid(False)
                        supplementary.yaxis.label.set_color(additional.get_color())
                        supplementary.spines.right.set_color(additional.get_color())
                        supplementary.tick_params(axis='y', colors=additional.get_color(), **tkw)
                        if flows[additional_flow_name] is not None:
                            supplementary.set_ylim(
                                [flows[additional_flow_name][0], flows[additional_flow_name][1]])

                        datums.append(additional)
                        axes.append(supplementary)

        labels = [datum.get_label() for datum in datums]
        legend = axes[-1].legend(
            datums,
            labels,
            loc='best',
            title=self.name,
            title_fontsize=8,
            fontsize=7,
            facecolor="white",
            frameon=True,
            framealpha=1,
            borderpad=.75,
            edgecolor='grey')
        fig.autofmt_xdate(rotation=90)
        plt.minorticks_on()
        # plt.tight_layout()
        plt.show(block=True)

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
            raise ValueError("Error: summation requires all flows' units to be the same. Units: {0}".format(
                json.dumps(
                    {flow.name: flow.units.__str__() for flow in self.flows}, indent=4)))

        return Flow.from_periods(
            name=name if name is not None else self.name + ' (sum)',
            index=self.frame.index,
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
        registry = registry if registry is not None else rk.measure.Index.registry
        units = rk.measure.multiply_units(
            units=list(self.units.values()),
            registry=registry)
        reduced_units = rk.measure.remove_dimension(
            quantity=registry.Quantity(1, units),
            dimension='[time]',
            registry=registry).units

        return Flow.from_periods(
            name=name if name is not None else self.name + ' (product)',
            index=self.frame.index,  # .to_period(),
            data=self.frame.prod(axis=1).to_list(),
            units=reduced_units)

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

    def total(self) -> np.float64:
        return self.sum().collapse().movements.iloc[0]

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

        index = rk.periodicity.period_index(
            include_start=self.start_date,
            period_type=self.period_type,
            bound=self.end_date)
        _resampled_flows = [flow.to_periods(period_type=self.period_type) for flow in self.flows]
        self.frame = pd.concat(_resampled_flows, axis=1).fillna(0)

    def resample(
            self,
            period_type: rk.periodicity.Type) -> Stream:
        return Stream(
            name=self.name,
            flows=self.flows,
            period_type=period_type)

    def trim_to_span(
            self,
            span: rk.span.Span) -> Stream:
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
            period_type: rk.periodicity.Type) -> Stream:
        # Check Units:
        if any(stream.units != streams[0].units for stream in streams):
            raise Exception("Input Streams have dissimilar units. Cannot merge into Stream.")

        # Aggregands:
        flows = [flow for stream in streams for flow in stream.flows]

        return cls(
            name=name,
            flows=flows,
            period_type=period_type)
