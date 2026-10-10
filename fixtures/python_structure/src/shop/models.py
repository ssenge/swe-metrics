"""Orders."""
from . import pricing


class Order:
    """An order of items."""

    def total(self):
        return pricing.price(self)

    def _check(self):
        return True


class _Hidden:
    def visible(self):
        return 1
