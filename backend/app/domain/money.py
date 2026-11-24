"""金额换算：一律整数分（engineering-rules 8.4）。换算系数只在此处出现。"""

from decimal import Decimal

_CENTS_PER_YUAN = 100


def yuan_to_cents(value: str | int | Decimal) -> int:
    d = Decimal(str(value)) * _CENTS_PER_YUAN
    if d != d.to_integral_value():
        raise ValueError(f"金额精度超过分: {value}")
    return int(d)


def cents_to_yuan_str(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    q, r = divmod(abs(cents), _CENTS_PER_YUAN)
    return f"{sign}{q}.{r:02d}"
