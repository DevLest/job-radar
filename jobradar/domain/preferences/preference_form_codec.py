"""Profile values <-> form values, per field kind."""

from __future__ import annotations


def to_form(value, kind: str):
    if kind == "tags":
        return ", ".join(str(item) for item in value or [])
    if kind == "lines":
        return "\n".join(value or [])
    if kind == "fx":
        return "\n".join(f"{currency} = {rate}" for currency, rate in (value or {}).items())
    if kind in ("pills", "cards"):
        return value or []
    if kind == "float" and isinstance(value, float) and value.is_integer():
        return int(value)
    return "" if value is None else value


def _fx_table(raw: str) -> dict[str, float]:
    table = {}
    for line in raw.splitlines():
        if "=" in line:
            currency, rate = line.split("=", 1)
            try:
                table[currency.strip().upper()] = float(rate)
            except ValueError:
                raise ValueError(f"Currency conversion: '{line.strip()}' should look like PHP = 0.0175")
    return table


def from_form(form, path: str, kind: str):
    """`form` is a MultiDict-like object (get / getlist / in). Raises ValueError with a friendly message."""
    raw = form.get(path, "")
    if kind == "switch":
        return path in form
    if kind in ("pills", "cards"):
        return form.getlist(path)
    if kind == "tags":
        return [item.strip() for item in raw.split(",") if item.strip()]
    if kind == "lines":
        return [line.strip() for line in raw.splitlines() if line.strip()]
    if kind in ("int", "float"):
        try:
            return (int if kind == "int" else float)(raw) if raw.strip() else None
        except ValueError:
            raise ValueError(f"'{raw}' is not a number")
    if kind == "fx":
        return _fx_table(raw)
    return raw.strip()
