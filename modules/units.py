import enum
import aenum


class Units:
    class Type(aenum.Enum):
        _init_ = 'value', '__doc__'

        USD = 'USD$', "United States' Dollars"
        AUD = 'AUD$' "Australian Dollars"
        kJ = 'kJ', "kilojoules; SI derived unit of Energy"
        m = 'm', "metres; SI base unit of Length"
        sqm = 'm2', "square metres; SI unit of Area"
        ft = 'ft', "feet; US/Imperial unit of Length"
        sqft = 'ft2', "square feet; US/Imperial unit of Area"

