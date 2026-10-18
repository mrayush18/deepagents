"""Starting-point size estimates from body measurements in inches.

These follow the common US "band plus cup" method. Fit varies by brand and
style, so the agents present them as a starting point, not a guarantee.
"""

from __future__ import annotations

CUPS = ["AA", "A", "B", "C", "D", "DD", "DDD", "G", "H", "I", "J"]

# Upper hip limit in inches for each brief size.
BRIEF_SIZES = [(35, "XS"), (38, "S"), (41, "M"), (44, "L"), (47, "XL"), (51, "2XL"), (55, "3XL")]


def bra_size(underbust: float, bust: float) -> str:
    """Estimate a US bra size such as `34C`.

    Args:
        underbust: Snug measurement directly under the bust.
        bust: Measurement around the fullest part of the bust.

    Raises:
        ValueError: If a measurement is out of the supported range.
    """
    if not 24 <= underbust <= 50 or bust < underbust:
        msg = "Measurements look out of range; underbust should be 24-50 in and bust at least underbust."
        raise ValueError(msg)
    band = round(underbust)
    band += band % 2  # Bands come in even sizes; round odd values up.
    difference = max(0, round(bust - band))
    cup = CUPS[min(difference, len(CUPS) - 1)]
    return f"{band}{cup}"


def brief_size(hip: float) -> str:
    """Estimate a letter size for briefs from the fullest hip measurement.

    Raises:
        ValueError: If the measurement is out of the supported range.
    """
    for limit, size in BRIEF_SIZES:
        if hip <= limit:
            return size
    msg = "Hip measurement is above the size chart; suggest checking the brand's extended sizes."
    raise ValueError(msg)
