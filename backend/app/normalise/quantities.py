"""Quantities in text, converted to both metric and imperial with pint.

Only a closed vocabulary counts as a unit. Words that are also something else ("pound" is money,
"in" is a preposition, "t" and "MT" are too many things) are never read as units: a missed
conversion costs nothing, a wrong one puts a false figure in front of the reader.
"""

import math
import re
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache

import pint

from app.normalise.numbers import NUMBER, canonical, parse_number


class UnitSystem(StrEnum):
    METRIC = "metric"
    IMPERIAL = "imperial"


@dataclass(frozen=True)
class Unit:
    pint_name: str
    label: str
    system: UnitSystem


_M, _I = UnitSystem.METRIC, UnitSystem.IMPERIAL
KG, G = Unit("kilogram", "kg", _M), Unit("gram", "g", _M)
LB, OZ = Unit("pound", "lb", _I), Unit("ounce", "oz", _I)
KM, M, CM, MM = (Unit("kilometer", "km", _M), Unit("meter", "m", _M),
                 Unit("centimeter", "cm", _M), Unit("millimeter", "mm", _M))
MI, FT, INCH, YD = (Unit("mile", "mi", _I), Unit("foot", "ft", _I),
                    Unit("inch", "in", _I), Unit("yard", "yd", _I))
TONNE = Unit("tonne", "t", _M)
L, ML, GAL = Unit("liter", "L", _M), Unit("milliliter", "mL", _M), Unit("gallon", "gal", _I)
DEG_C, DEG_F = Unit("degC", "°C", _M), Unit("degF", "°F", _I)
M2, HA = Unit("meter**2", "m²", _M), Unit("hectare", "ha", _M)
FT2, ACRE = Unit("foot**2", "sq ft", _I), Unit("acre", "acre", _I)
KMH, MPH = Unit("kilometer/hour", "km/h", _M), Unit("mile/hour", "mph", _I)

# Case-sensitive symbols: "M" is million and "G" is 5G, so only these exact spellings count.
SYMBOLS: dict[str, Unit] = {
    "kg": KG, "kgs": KG, "g": G, "lb": LB, "lbs": LB, "oz": OZ,
    "km": KM, "m": M, "cm": CM, "mm": MM, "mi": MI, "ft": FT, "yd": YD,
    "L": L, "l": L, "ml": ML, "mL": ML, "gal": GAL,
    "°C": DEG_C, "° C": DEG_C, "°F": DEG_F, "° F": DEG_F,
    "m²": M2, "m2": M2, "sqm": M2, "ha": HA, "ft²": FT2, "sq ft": FT2, "sqft": FT2,
    "km/h": KMH, "kph": KMH, "mph": MPH,
}
# Whole words, any case.
WORDS: dict[str, Unit] = {
    "kilogram": KG, "kilograms": KG, "gram": G, "grams": G, "ounce": OZ, "ounces": OZ,
    "tonne": TONNE, "tonnes": TONNE,
    "kilometre": KM, "kilometres": KM, "kilometer": KM, "kilometers": KM,
    "metre": M, "metres": M, "meter": M, "meters": M,
    "centimetre": CM, "centimetres": CM, "centimeter": CM, "centimeters": CM,
    "mile": MI, "miles": MI, "foot": FT, "feet": FT, "inch": INCH, "inches": INCH,
    "yard": YD, "yards": YD, "litre": L, "litres": L, "liter": L, "liters": L,
    "gallon": GAL, "gallons": GAL, "acre": ACRE, "acres": ACRE, "hectare": HA, "hectares": HA,
    "square feet": FT2, "square metres": M2, "square meters": M2,
    "degrees celsius": DEG_C, "degrees fahrenheit": DEG_F,
}

# Per dimension and system, the display units from largest to smallest; the first that keeps
# the value at 1 or above wins, so 0.5 km shows as 500 m rather than 0.5 km.
TARGETS: dict[str, dict[UnitSystem, list[Unit]]] = {
    "[mass]": {_M: [KG, G], _I: [LB, OZ]},
    "[length]": {_M: [KM, M, CM], _I: [MI, FT, INCH]},
    "[length] ** 3": {_M: [L, ML], _I: [GAL]},
    "[temperature]": {_M: [DEG_C], _I: [DEG_F]},
    "[length] ** 2": {_M: [HA, M2], _I: [ACRE, FT2]},
    "[length] / [time]": {_M: [KMH], _I: [MPH]},
}
# Below this a large unit reads badly ("0.4 km"), so a smaller one is used instead.
MIN_DISPLAY_VALUE = 1.0
# A conversion shows three significant figures, but never rounds a figure of this size or more
# coarser than whole units: 2,721,742 lb must not display as 2,720,000.
SIGNIFICANT_FIGURES = 3
WHOLE_UNITS_FROM = 100


def _alternation(units: list[str]) -> str:
    return "|".join(re.escape(u) for u in sorted(units, key=len, reverse=True))


# A one-letter unit must stand apart from its number: "RM5m" and "$2m" are millions, not metres.
_SHORT = [s for s in SYMBOLS if len(s) == 1]
_LONG = [s for s in SYMBOLS if len(s) > 1]
_QUANTITY = re.compile(
    # A leading minus counts only as a sign, not as the hyphen in "INV-2026" or "10-12 kg".
    rf"(?:(?<![\w\-−])(?P<sign>[-−]))?(?P<number>{NUMBER})"
    rf"(?:\s?(?P<unit>(?i:{_alternation(list(WORDS))})|{_alternation(_LONG)})"
    rf"|\s(?P<short>{_alternation(_SHORT)}))"
    r"(?![A-Za-z0-9²])"
)
# An amount of money is never a quantity, whatever follows it.
_CURRENCY_BEFORE = re.compile(r"(?:RM|MYR|USD|SGD|EUR|GBP|[$£€¥])\s?$", re.IGNORECASE)
_CURRENCY_LOOKBACK = 4


@dataclass(frozen=True)
class Measure:
    value: float
    unit: str


@dataclass(frozen=True)
class Quantity:
    text: str  # as written
    start: int
    end: int
    dimension: str
    system: UnitSystem  # of the unit as written
    metric: Measure
    imperial: Measure
    base: float  # unrounded, in the dimension's first metric unit: what comparisons use


@lru_cache(maxsize=1)
def _registry() -> pint.UnitRegistry:
    return pint.UnitRegistry()


def _round(value: float) -> float:
    if abs(value) >= WHOLE_UNITS_FROM:
        return float(round(value))
    if value == 0:
        return 0.0
    return round(value, SIGNIFICANT_FIGURES - math.floor(math.log10(abs(value))) - 1)


def _display(quantity: pint.Quantity, candidates: list[Unit]) -> Measure:
    for unit in candidates:
        converted = quantity.to(unit.pint_name).magnitude
        if abs(converted) >= MIN_DISPLAY_VALUE or unit is candidates[-1]:
            return Measure(_round(converted), unit.label)
    raise AssertionError("candidates is never empty")


def _unit_for(written: str) -> Unit:
    return SYMBOLS.get(written) or WORDS[written.lower()]


def _is_money(text: str, start: int) -> bool:
    return bool(_CURRENCY_BEFORE.search(text[max(0, start - _CURRENCY_LOOKBACK):start]))


def _quantity(match: re.Match[str]) -> Quantity:
    unit = _unit_for(match.group("unit") or match.group("short"))
    value = parse_number(match.group("number")) * (-1 if match.group("sign") else 1)
    measured = _registry().Quantity(value, unit.pint_name)
    dimension = str(measured.dimensionality)
    targets = TARGETS[dimension]
    # The written side is echoed exactly: rounding it would put a figure in front of the reader
    # that the sender never wrote.
    as_written = Measure(value, unit.label)
    displays = {system: as_written if system == unit.system else _display(measured, targets[system])
                for system in UnitSystem}
    return Quantity(
        text=match.group(0), start=match.start(), end=match.end(), dimension=dimension,
        system=unit.system, metric=displays[_M], imperial=displays[_I],
        base=measured.to(targets[_M][0].pint_name).magnitude,
    )


def quantities_in(text: str) -> list[Quantity]:
    return [_quantity(match) for match in _QUANTITY.finditer(text)
            if not _is_money(text, match.start())
            and math.isfinite(parse_number(match.group("number")))]


# Converting and rounding moves a figure a little ("4,409 lb" for 2,000 kg is 1999.9 kg); a
# wrong figure moves it a lot. Applies only across units: the same unit needs the same figure.
CONVERSION_TOLERANCE = 0.01
TEMPERATURE = "[temperature]"
TEMPERATURE_TOLERANCE = 0.5  # degrees Celsius: rounding a conversion to whole degrees


def _written(quantity: Quantity) -> Measure:
    return quantity.metric if quantity.system == UnitSystem.METRIC else quantity.imperial


def _is_conversion_of(candidate: Quantity, source: Quantity) -> bool:
    if candidate.dimension != source.dimension or _written(candidate).unit == _written(source).unit:
        return False
    # Temperatures cross zero, where a relative tolerance can never match (0 °C is 32 °F).
    absolute = TEMPERATURE_TOLERANCE if candidate.dimension == TEMPERATURE else 0.0
    return math.isclose(candidate.base, source.base, rel_tol=CONVERSION_TOLERANCE, abs_tol=absolute)


def converted_figures(text: str, reference: str) -> set[str]:
    """Figures in `text` that are a unit conversion of a quantity in `reference`."""
    sources = quantities_in(reference)
    # Unsigned, to match the figures gate, which reads "-5" as the figure 5.
    return {canonical(abs(_written(q).value)) for q in quantities_in(text)
            if any(_is_conversion_of(q, source) for source in sources)}
