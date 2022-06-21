from __future__ import annotations

import enum
import math
from typing import List, Dict, Union, Tuple
from collections import namedtuple

import pandas as pd
from aenum import Enum
import rich


class Characteristic(Enum):
    _init_ = 'value'

    use = 'Use'
    tenure = 'Tenure'
    phase = 'Phase'
    type = 'Type'


class Type:
    name: str
    code: str
    supertype: Type
    subtypes: [Type]

    def __init__(
            self,
            name: str,
            code: str = None,
            supertype: Type = None):
        self.name = name
        self.code = code
        self.supertype = supertype
        self.subtypes = []

        if supertype is not None:
            supertype.subtypes.append(self)

    def __str__(self):
        code = ' :' + self.code if self.code is not None else ''
        return self.name + code

    def add_subtypes(
            self,
            subtypes: [Type]):
        for subtype in subtypes:
            self.subtypes.append(subtype)
            subtype.supertype = self

    def ancestors(self) -> [Type]:
        ancestors = []
        supertype = self.supertype
        while supertype is not None:
            ancestors.append(supertype)
            supertype = supertype.supertype
        return ancestors

    def primogenitor(self) -> Type:
        return self.ancestors()[-1]

    def display(self):
        print(' > '.join([ancestor.__str__() for ancestor in self.ancestors()]))


class Interval(pd.Interval):
    def __init__(
            self,
            right: float,
            left: float = 0.):
        super().__init__(
            left=left,
            right=right)

    def __str__(self):
        return f'({self.left}, {self.right})'

    def split(
            self,
            proportion: float) -> tuple[Interval, Interval]:
        if proportion < 0 or proportion > 1:
            raise ValueError('Error: proportion must be between 0 and 1')

        split_point = self.left + (proportion * self.length)
        left_interval = self.__class__(
            right=split_point,
            left=self.left)
        right_interval = self.__class__(
            right=self.right,
            left=split_point)
        return left_interval, right_interval

    def subdivide(
            self,
            values: Union[int, List[float]]) -> List[Interval]:
        if isinstance(values, int):
            if values < 0:
                raise ValueError('Error: divisors must be greater than 0')
            lengths = [self.length / values for i in range(values)]
        elif all(isinstance(fraction, float) for fraction in values):
            if math.isclose(sum(values), 1) and all(0 < fraction < 1 for fraction in values):
                lengths = [self.length * fraction for fraction in values]
            else:
                raise ValueError('Error: Sum of divisors must complete unit interval')
        else:
            raise TypeError('Error: values must be either number of divisors or split proportions')

        parameters = [self.left + sum(lengths[:i]) for i in range(1, len(lengths) + 1)]
        parameters.insert(0, self.left)
        results = []
        for i in range(len(parameters) - 1):
            results.append(
                self.__class__(
                    left=parameters[i],
                    right=parameters[i + 1]))
        return results


class Segment:
    bounds: Interval
    parent: Segment
    children: List[Segment]
    characteristics: Dict[Characteristic, str]

    def __init__(
            self,
            bounds: Interval,
            characteristics: Dict[Characteristic, str] = None,
            parent: Segment = None):
        self.bounds = bounds
        self.characteristics = {} if characteristics is None else characteristics
        self.parent = parent
        self.children = []

        if parent is not None:
            parent.children.append(self)

    def to_frame(self):
        frame = pd.DataFrame(
            data=[list(self.characteristics.values())],
            index=pd.IntervalIndex(data=[self.bounds]),
            columns=[characteristic.value for characteristic in self.characteristics.keys()])
        frame['Amount'] = self.bounds.length
        frame['Proportion(Parent)'] = "{:.0%}".format(self.bounds.length / self.parent.bounds.length)

        return frame

    def display(self):
        print('\n')
        floatfmt = "." + str(2) + "f"
        print(self.to_frame().to_markdown(
            tablefmt='github',
            floatfmt=floatfmt))

    def display_children(
            self,
            pivot: Characteristic = None,
            decimals: int = 2,
            ):
        if len(self.children) == 0:
            raise ValueError("Error: Segment has no children")

        frame = pd.concat([child.to_frame() for child in self.children])
        if pivot is not None:
            frame = frame.pivot_table(
                index=pivot.value,
                columns=['Amount', 'Use', 'Proportion(Parent)'])

        floatfmt = "." + str(decimals) + "f"

        print('\n Children')
        print(frame.to_markdown(
            tablefmt='github',
            floatfmt=floatfmt))

        print('\n Total')
        print(self.to_frame().to_markdown(
            tablefmt='github',
            floatfmt=floatfmt))

    # def display_hierarchy(self):

    def split(self, proportion: float) -> tuple[Segment, Segment]:
        split_lower, split_upper = self.bounds.split(proportion)
        lower = Segment(
            bounds=split_lower,
            parent=self)
        upper = Segment(
            bounds=split_upper,
            parent=self)
        return (lower, upper)

    def subdivide(
            self,
            divisions: List[Tuple[Dict[Characteristic, str], float]]) -> List[Segment]:
        result = []
        intervals = self.bounds.subdivide([division[1] for division in divisions])
        for division, interval in zip([division[0] for division in divisions], intervals):
            result.append(Segment(
                bounds=interval,
                characteristics=division,
                parent=self))
        return result
