"""Views."""
from ..models import Order
from shop.pricing import price


def index():
    """The index view."""
    from ..util import slug
    return slug(str(price(Order())))
