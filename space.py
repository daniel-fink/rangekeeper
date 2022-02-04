from __future__ import annotations
from typing import Dict, List, Union

import aenum


class Type:
    name: str
    category: str
    parent: Type
    children: [Type]

    def __init__(self,
                 name: str,
                 category: str,
                 parent: Type = None,
                 children: List[Type] = None):
        self.name = name
        self.category = category
        self.parent = parent
        self.children = children

    def __str__(self):
        return self.category + " " + self.name

    # @classmethod
    # def from_dict(
    #         cls,
    #         dict: Dict[(str, str), List[(str, str)]]):
    #     types = []
    #     for type, children in dict.items():
    #         type = next((type.category == type[1] for type in types), None)
    #         if type is None:
    #             for child_name in children_names:
    #
    #             type = Type(
    #                 name=type_name,
    #
    #         if any(type.name == type_name for type in types):


class Space:
    name: str
    type: Type
    attributes: Dict

    def __init__(
            self,
            name: str,
            type: Type,
            attributes: Dict = None):
        self.name = name
        self.type = type
        self.attributes = attributes


class Apartment(Space):
    def __init__(self,
                 name: str,
                 type: Type,
                 attributes: Dict = None):
        super().__init__(name, type, attributes)



class Apartment:
    def __init__(self,
                 apartment_type: aenum.Enum,
                 num_beds: int,
                 num_bath: int,
                 num_balcony: int,
                 gfa: float,
                 cfa_amenities: float,
                 cfa_shell: float):
        self.apartment_type = apartment_type
        self.num_beds = num_beds
        self.num_bath = num_bath
        self.num_balcony = num_balcony
        self.gfa = gfa
        self.cfa_amenities = cfa_amenities
        self.cfa_shell = cfa_shell

    class Type(aenum.Enum):
        _init_ = 'value __doc__'

        B1B1B0 = '1Bed1Bath0Balcony', '1-Bed 1-Bath Apartment without Balconies'
        B1B1B1 = '1Bed1Bath1Balcony', '1-Bed 1-Bath Apartment with 1 Balcony'
        B2B1B0 = '1Bed1Bath0Balcony', '2-Bed 1-Bath Apartment without Balconies'
        B2B1B1 = '2Bed1Bath1Balcony', '2-Bed 1-Bath Apartment with 1 Balcony'
        B2B1B2 = '2Bed1Bath2Balcony', '2-Bed 1-Bath Apartment with 2 Balconies'
        B2B2B0 = '2Bed2Bath0Balcony', '2-Bed 2-Bath Apartment without Balconies'
        B2B2B1 = '2Bed2Bath1Balcony', '2-Bed 2-Bath Apartment with 1 Balcony'
        B3B2B0 = '3Bed2Bath0Balcony', '3-Bed 2-Bath Apartment without Balconies'
        B3B2B1 = '3Bed2Bath1Balcony', '3-Bed 2-Bath Apartment with 1 Balcony'

    @staticmethod
    def from_type(apartment_type: Type):
        return {
            Apartment.Type.B1B1B0: Apartment(
                apartment_type=Apartment.Type.B1B1B0,
                num_beds=1,
                num_bath=1,
                num_balcony=0,
                gfa=69.5,
                cfa_amenities=27.9,
                cfa_shell=47.9),
            Apartment.Type.B1B1B1: Apartment(
                apartment_type=Apartment.Type.B1B1B1,
                num_beds=1,
                num_bath=1,
                num_balcony=1,
                gfa=62.3,
                cfa_amenities=27.9,
                cfa_shell=47.9),
            Apartment.Type.B2B1B0: Apartment(
                apartment_type=Apartment.Type.B2B1B0,
                num_beds=2,
                num_bath=1,
                num_balcony=0,
                gfa=88.0,
                cfa_amenities=37.4,
                cfa_shell=63.6),
            Apartment.Type.B2B1B1: Apartment(
                apartment_type=Apartment.Type.B2B1B1,
                num_beds=2,
                num_bath=1,
                num_balcony=1,
                gfa=80.8,
                cfa_amenities=37.4,
                cfa_shell=63.6),
            Apartment.Type.B2B1B2: Apartment(
                apartment_type=Apartment.Type.B2B1B2,
                num_beds=2,
                num_bath=1,
                num_balcony=2,
                gfa=79.4,
                cfa_amenities=37.4,
                cfa_shell=63.6),
            Apartment.Type.B2B2B0: Apartment(
                apartment_type=Apartment.Type.B2B2B0,
                num_beds=2,
                num_bath=1,
                num_balcony=0,
                gfa=93.7,
                cfa_amenities=37.4,
                cfa_shell=63.6),
            Apartment.Type.B2B2B1: Apartment(
                apartment_type=Apartment.Type.B2B2B1,
                num_beds=2,
                num_bath=2,
                num_balcony=1,
                gfa=86.6,
                cfa_amenities=37.4,
                cfa_shell=63.6),
            Apartment.Type.B3B2B0: Apartment(
                apartment_type=Apartment.Type.B3B2B0,
                num_beds=3,
                num_bath=2,
                num_balcony=0,
                gfa=113.3,
                cfa_amenities=48.0,
                cfa_shell=79.8),
            Apartment.Type.B3B2B1: Apartment(
                apartment_type=Apartment.Type.B3B2B1,
                num_beds=3,
                num_bath=2,
                num_balcony=1,
                gfa=105.1,
                cfa_amenities=48.0,
                cfa_shell=79.8)
            }[apartment_type]
