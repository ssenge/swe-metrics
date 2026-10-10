# Hand-computed cognitive complexity per function (SonarSource rules), see expected.json.
import subprocess


def chain(a):
    if a == 1:
        return 1
    elif a == 2:
        return 2
    else:
        return 3


def comprehension(xs, flag):
    if flag:
        return [x for x in xs if x and flag]
    return []


class Service:
    def run(self, n):
        subprocess.run(["x"])
        return self.run(n - 1) if n else 0


def with_lambda(xs):
    return sorted(xs, key=lambda x: 1 if x else 0)


def loops(xs):
    while xs:
        try:
            xs.pop()
        except IndexError:
            break
    else:
        return 0
    return 1
