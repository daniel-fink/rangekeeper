from __future__ import annotations

import enum
from typing import List, Dict
from collections import namedtuple
from aenum import Enum


class Characteristic(Enum):
    _init_ = 'value'

    use = 'Use'
    tenure = 'Tenure'
    phase = 'Phase'
    type = 'Type'


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
        Split = namedtuple('Split', 'lower upper')
        return Split(lower_interval, upper_interval)

    def subdivide(
            self,
            divisors: int) -> List[Interval]:
        if divisors < 0:
            raise ValueError('Error: divisors must be greater than 0')

        length = self.length() / divisors

        result = []
        for i in range(divisors):
            lower = self.lower + (i * length)
            upper = lower + length

            result.append(self.__class__(
                upper=upper,
                lower=lower))
        return result


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
        if characteristics is None:
            self.characteristics = {}
        else:
            self.characteristics = characteristics
        self.parent = parent
        self.children = []

        if parent is not None:
            parent.children.append(self)

    def split(self, proportion: float) -> tuple[Segment, Segment]:
        split = self.bounds.split(proportion)
        lower = Segment(
            bounds=split.lower,
            parent=self)
        upper = Segment(
            bounds=split.upper,
            parent=self)
        Split = namedtuple('Split', 'lower upper')
        return Split(lower, upper)

    def aggregate_ancestor_characteristics(self) -> Dict[Characteristic, str]:
        parent = self.parent
        characteristics = {}
        while parent is not None:
            for characteristic, value in parent.characteristics.items():
                characteristics[characteristic] = value
            parent = parent.parent
        return characteristics
