from __future__ import annotations

PERIODS_PER_YEAR = {"hour": 2080, "day": 260, "week": 52, "month": 12, "year": 1}


def annual(amount: float | None, per: str) -> float | None:
    return None if amount is None else amount * PERIODS_PER_YEAR.get(per or "year", 1)


def to_rate_currency(amount: float | None, currency: str, rate: dict) -> float | None:
    """Convert a posted salary into the currency of your rate, using rate.fx_to_rate_currency.
    Returns None when the conversion is unknown (the job is then left for Claude to judge)."""
    if amount is None:
        return None
    mine = (rate.get("currency") or "USD").upper()
    theirs = (currency or "").upper()
    if theirs == mine:
        return amount
    fx = {code.upper(): value for code, value in (rate.get("fx_to_rate_currency") or {}).items()}
    return amount * fx[theirs] if theirs in fx else None
