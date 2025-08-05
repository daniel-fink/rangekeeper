from typing import Tuple, Union, Optional
import decimal

import babel.core
import numpy as np
import matplotlib
import pandas as pd
from babel import numbers, dates


def to_decimal(
    value,
    places: int = 2,
    mode: str = "ROUND_HALF_EVEN",
) -> decimal.Decimal:
    """
    Formats a number as a decimal string.
    :param value:
    :param places:
    :param mode:
    :return:
    """
    places = decimal.Decimal(10) ** -places
    with decimal.localcontext(decimal.Context(rounding=mode)):
        return decimal.Decimal(str(value)).quantize(places)


def to_decimals(
    series: pd.Series,
    places: int = 2,
    mode: str = "ROUND_HALF_EVEN",
) -> pd.Series:
    """
    Formats a pd.Series' values to decimal strings.
    :param series:
    :param places:
    :param mode:
    :return:
    """
    return series.map(
        lambda value: to_decimal(
            value=value,
            places=places,
            mode=mode,
        ),
        na_action="ignore",
    ).astype("string")


def to_thousands(value) -> decimal.Decimal:
    """
    Formats a number to a string with thousands separators.
    :param value:
    :return:
    """
    places = decimal.Decimal(10) ** 3
    with decimal.localcontext(decimal.Context(rounding=decimal.ROUND_HALF_EVEN)):
        return decimal.Decimal(str(value)).quantize(places)


def to_thousandss(series: pd.Series) -> pd.Series:
    """
    Formats a pd.Series' values to thousands' strings with thousands separators.
    :param series:
    :return:
    """
    return series.map(lambda value: to_thousands(value), na_action="ignore").astype(
        "string"
    )


def to_currency(
    value,
    currency: str = "USD",
    locale: str = "en_US",
    decimals: bool = True,
    compact: bool = False,
) -> str:
    """
    Formats a number as a currency string.
    :param compact:
    :param value:
    :param currency:
    :param locale:
    :param decimals:
    :return:
    """
    number = to_decimal(value, 2)
    if compact:
        return numbers.format_compact_currency(
            number=number,
            currency=currency,
            locale=locale,
        )

    result = numbers.format_currency(
        number=number,
        currency=currency,
        locale=locale,
        decimal_quantization=False,
    )
    if not decimals:
        return result.split(".")[0]
    return result


def to_currencys(
    series: pd.Series,
    currency: str = "USD",
    locale: str = "en_US",
    decimals: bool = True,
    compact: bool = False,
) -> pd.Series:
    """
    Formats a pd.Series' values to currency strings.
    Defaults to USD
    :param series:
    :param currency:
    :param locale:
    :param decimals:
    :param compact:
    :return:
    """
    return series.map(
        lambda value: to_currency(
            value=value,
            currency=currency,
            locale=locale,
            decimals=decimals,
            compact=compact,
        ),
        na_action="ignore",
    ).astype("string")


def to_percentage(
    value,
    decimal_places: int = 2,
) -> str:
    """
    Formats a number as a percentage string.
    :param value:
    :param decimal_places:
    :return:
    """
    number = to_decimal(value * 100, decimal_places)
    return (
        numbers.format_decimal(
            number=number,
            locale="",
            decimal_quantization=False,
        )
        + "%"
    )


def to_percentages(
    series: pd.Series,
    decimal_places: int = 2,
) -> pd.Series:
    """
    Formats a pd.Series' values to percentage strings.
    :param series:
    :param decimal_places:
    :return:
    """
    return series.map(
        lambda value: to_percentage(
            value=value,
            decimal_places=decimal_places,
        ),
        na_action="ignore",
    ).astype("string")


def to_locale(
    value,
    locale: Optional[Union[str, babel.core.Locale]] = "en_US",
    decimal_places: int = 2,
) -> str:
    number = to_decimal(
        value,
        decimal_places,
    )
    return numbers.format_decimal(
        number=number,
        locale=locale,
        decimal_quantization=False,
    )


def to_locales(
    series: pd.Series,
    locale: str = "en_US",
    decimal_places: int = 2,
) -> pd.Series:
    return series.map(
        lambda value: to_locale(
            value=value,
            locale=locale,
            decimal_places=decimal_places,
        ),
        na_action="ignore",
    ).astype("string")


def _to_color(
    value: float,
    cmap,
    range: Tuple[float, float] = (0, 1),
    missing: str = "#ffffff",
) -> str:
    if pd.isna(value):
        return missing
    return str(matplotlib.colors.to_hex(cmap(np.interp(value, range, (0, 1)))))


_to_color_vect = np.vectorize(_to_color, excluded=["cmap", "range"])


def to_color(
    value: float,
    cmap: str = "RdYlGn",
    range: Tuple[float, float] = (0, 1),
    missing: str = "#ffffff",
) -> str:
    """
    Converts a float value to a hexcolor string using a matplotlib colormap.
    :param value:
    :param cmap:
    :param range:
    :param missing:
    :return:
    """
    colormap = matplotlib.colormaps[cmap]
    return _to_color_vect(value=value, cmap=colormap, range=range)


def to_scaled_colors(
    series: pd.Series,
    range: Tuple[float, float] = None,
    cmap: str = "RdYlGn",
    diverging: bool = False,
    missing: str = "#ffffff",
) -> pd.Series:
    range = (series.min(), series.max()) if range is None else range
    if diverging:
        extreme = max(abs(range[0]), abs(range[1]))
        range = (-extreme, extreme)
    colormap = matplotlib.colormaps[cmap]

    return _to_color_vect(value=series, cmap=colormap, range=range, missing=missing)


def distinct_colors(
    count: int,
    cmap: str = "RdYlGn",
):
    range = np.linspace(0, 1, count)
    colormap = matplotlib.colormaps[cmap]
    return _to_color_vect(value=range, cmap=colormap)


def to_distinct_colors(
    series: pd.Series,
    cmap: str = "RdYlGn",
    name: str = "color",
):
    distincts = pd.Series(series.unique()).sort_values()
    colors = pd.Series(
        data=distinct_colors(count=len(distincts), cmap=cmap), index=distincts
    )
    return series.map(colors).rename(name)


def na_to_empty(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fills NA values in a DataFrame's 'string' or 'object' Series with an empty string.
    Returns a new DataFrame with those Series having 'string' dtype.
    :param values:
    :return:
    """
    for column in df.columns:
        if df[column].dtype in ("string", "object"):
            df[column] = df[column].fillna(value="", inplace=False).astype("string")
    return df


def _to_nonnullable(series: pd.Series):
    if series.dtype == "Int64":
        return series.astype("int")
    elif series.dtype == "Float64":
        return series.astype("float")
    elif series.dtype == "string":
        return series.astype("object")
    else:
        return series


def to_nonnullables(data, verbose: bool = True):
    if isinstance(data, pd.Series):
        try:
            return _to_nonnullable(series=data)
        except Exception as e:
            if verbose:
                print('Error: {0}. Reverting to "object" dtype.'.format(e))
            return data.astype("object")
    elif isinstance(data, pd.DataFrame):
        for column in data.columns:
            try:
                data[column] = _to_nonnullable(series=data[column])
            except Exception as e:
                if verbose:
                    print(
                        'Error for column {0}: {1}. Reverting to "object" dtype.'.format(
                            column, e
                        )
                    )
                data[column] = data[column].astype("object")
        return data
    else:
        raise TypeError(
            "Data must be a Pandas Series or DataFrame, not {0}.".format(type(data))
        )


def to_timestampstrings(
    series: pd.Series,
    format: str = "short",
    locale: str = "en_US",
):
    if "datetime" in str(series.dtype):
        return series.apply(
            lambda value: dates.format_datetime(
                datetime=value,
                format=format,
                locale=locale,
            )
        )
    else:
        raise TypeError(
            "Series must have a datetime dtype, not {0}.".format(series.dtype)
        )


def to_datestrings(
    series: pd.Series,
    format: str = "medium",
    locale: str = "en_US",
):
    if "datetime" in str(series.dtype):
        return series.apply(
            lambda value: (
                None
                if pd.isna(value)
                else dates.format_date(date=value, format=format, locale=locale)
            )
        )
    else:
        raise TypeError(
            "Series must have a datetime dtype, not {0}.".format(series.dtype)
        )


def column_names(
    df: pd.DataFrame,
    option: Optional[str],
    add_prefix: Optional[str] = None,
    add_suffix: Optional[str] = None,
):
    """
    Function to format all column names in a GeoPandas GeoDataFrame,
    by replacing spaces with underscores and converting to lowercase

    :param df:
    :param option: 'lowercase', 'uppercase', 'sentence case', 'title case'
    :param add_suffix:
    :param add_prefix:
    :return: Pandas DataFrame or GeoPandas GeoDataFrame, depending on input
    """

    if option == "lower":
        df = df.set_axis(
            [column.lower() for column in df.columns], axis="columns", copy=True
        )
    elif option == "upper":
        df = df.set_axis(
            [
                column.upper() if column != "geometry" else column
                for column in df.columns
            ],
            axis="columns",
            copy=True,
        )
    elif option == "capitalize":
        df = df.set_axis(
            [
                column.capitalize() if column != "geometry" else column
                for column in df.columns
            ],
            axis="columns",
            copy=True,
        )
    elif option == "title":
        df = df.set_axis(
            [
                column.title() if column != "geometry" else column
                for column in df.columns
            ],
            axis="columns",
            copy=True,
        )
    elif option is None:
        pass
    else:
        raise ValueError("Invalid option")

    if add_prefix:
        df.columns = df.columns.map(
            lambda name: add_prefix + name if name != "geometry" else name
        )
    if add_suffix:
        df.columns = df.columns.map(
            lambda name: name + add_suffix if name != "geometry" else name
        )

    df.columns = df.columns.map(
        lambda name: name.replace(" ", "_") if name != "geometry" else name
    )

    return df
