from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str

    def add(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise ValueError("Cannot add different currencies.")
        return Money(self.amount + other.amount, self.currency)

    def subtract(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise ValueError("Cannot subtract different currencies.")
        return Money(self.amount - other.amount, self.currency)