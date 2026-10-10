# Fixture for the opengrep test: one eval (error) and one print (note).
def run(expr):
    print(expr)
    return eval(expr)
