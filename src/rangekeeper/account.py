"""Shared account conventions without numerical or declaration dependencies."""

from enum import Enum, unique


@unique
class Balance(Enum):
    OPENING = "opening"
    CLOSING = "closing"


@unique
class CurrentInterest(Enum):
    EXCLUDED = "excluded"
    INCLUDED = "included"


@unique
class InterestTreatment(Enum):
    SEPARATE = "separate"
    FINANCED = "financed"


def check_conventions(
    *,
    balance: Balance,
    current_interest: CurrentInterest,
    treatment: InterestTreatment,
) -> None:
    """Require named choices and reject self-inclusion without financing."""
    for value, kind in (
        (balance, Balance),
        (current_interest, CurrentInterest),
        (treatment, InterestTreatment),
    ):
        if not isinstance(value, kind):
            raise TypeError(f"account option must be a {kind.__name__}")
    if (
        current_interest is CurrentInterest.INCLUDED
        and treatment is InterestTreatment.SEPARATE
    ):
        raise ValueError("included current interest requires financed treatment")
