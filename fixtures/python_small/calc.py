# Fixture with known metric values (see expected.json). Do not reformat.
def add(a, b):
    return a + b


def classify(n):
    if n < 0:
        return "negative"
    elif n == 0:
        return "zero"
    for i in range(3):
        if i == n:
            return "small"
    return "large"
