from __future__ import annotations

import enum
import math
from typing import List, Dict, Union, Tuple
from collections import namedtuple
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


class Interval:
    lower: float
    upper: float

    def __str__(self):
        return f'({self.lower}, {self.upper})'

    def __init__(
            self,
            upper: float,
            lower: float = 0.):
        self.lower = lower
        self.upper = upper

    def length(self) -> float:
        return self.upper - self.lower

    def midpoint(self):
        return (self.length() / 2) + self.lower

    def split(
            self,
            proportion: float) -> tuple[Interval, Interval]:
        if proportion < 0 or proportion > 1:
            raise ValueError('Error: proportion must be between 0 and 1')

        split_point = self.lower + (proportion * self.length())
        lower_interval = self.__class__(
            upper=split_point,
            lower=self.lower)
        upper_interval = self.__class__(
            upper=self.upper,
            lower=split_point)
        return lower_interval, upper_interval

    def subdivide(
            self,
            values: Union[int, List[float]]) -> List[Interval]:
        if isinstance(values, int):
            if values < 0:
                raise ValueError('Error: divisors must be greater than 0')
            lengths = [self.length() / values for i in range(values)]
        elif all(isinstance(fraction, float) for fraction in values):
            if math.isclose(sum(values), 1) and all(0 < fraction < 1 for fraction in values):
                lengths = [self.length() * fraction for fraction in values]
            else:
                raise ValueError('Error: Sum of divisors must complete unit interval')
        else:
            raise TypeError('Error: values must be either number of divisors or split proportions')

        uppers = [self.lower + sum(lengths[:i]) for i in range(1, len(lengths) + 1)]
        uppers.insert(0, self.lower)
        results = []
        for i in range(len(uppers) - 1):
            results.append(
                self.__class__(
                    lower=uppers[i],
                    upper=uppers[i + 1]))
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

    def display(self):
        print('\n')
        print('Characteristics: ')
        rich.print(self.characteristics)
        print('Bounds: ' + self.bounds.__str__())

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
            divisions: Dict[List[Tuple[Characteristic, str]], float]) -> List[Segment]:
        result = []
        intervals = self.bounds.subdivide()
        for division, interval in zip(divisions.keys(), intervals):
            result.append(Segment(
                bounds=interval,
                characteristics=division,
                parent=self))
        return result
