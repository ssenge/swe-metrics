import json
import shop.util
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Order


def price(order: "Order") -> float:
    """The price of an order."""
    return float(len(json.dumps(shop.util.slug("x"))))


async def fetch():
    return None
