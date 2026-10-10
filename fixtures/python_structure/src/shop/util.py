"""Helpers."""


def slug(text):
    def inner(value):
        """Not public API: nested in a function."""
        return value.lower()
    return inner(text)
