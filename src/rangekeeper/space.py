# from __future__ import annotations
# from typing import Dict, List, Union, Optional
# from decimal import Decimal
# from pint import Quantity
#
# import rangekeeper as rk
#
#
# class Space(rk.graph.Entity):
#     def __init__(
#             self,
#             name: str,
#             type: str,
#             measurements: Dict[rk.measure.Measure, Quantity] = None,
#             events: List[rk.graph.Event] = None,
#             attributes: Dict = None):
#         super().__init__(
#             name=name,
#             type=type)
#         self.measurements = measurements
#         self.events=events
#         self.attributes = attributes
#
#
# class Apartment(Space):
#     num_bed: int
#     num_bath: Decimal
#     num_balcony: int
#
#     def __init__(
#             self,
#             name: str,
#             type: str,
#             num_bed: int,
#             num_bath: Union[int, Decimal],
#             num_balcony: Optional[int] = None,
#             measurements: Dict[rk.measure.Measure, Quantity] = None,
#             attributes: Dict = None):
#         super().__init__(name, type, measurements, attributes)
#         self.num_bed = num_bed
#         self.num_bath = num_bath
#         self.num_balcony = num_balcony
