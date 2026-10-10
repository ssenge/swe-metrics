// Hand-computed cognitive complexity per method (SonarSource rules), see expected.json.
class Sample {
  int sumOfPrimes(int max) {
    int total = 0;
    OUT: for (int i = 1; i <= max; ++i) {
      for (int j = 2; j < i; ++j) {
        if (i % j == 0) {
          continue OUT;
        }
      }
      total += i;
    }
    return total;
  }

  String getWords(int number) {
    switch (number) {
      case 1: return "one";
      case 2: return "a couple";
      default: return "lots";
    }
  }

  int chain(int a) {
    if (a == 1) { return 1; } else if (a == 2) { return 2; } else { return 3; }
  }

  boolean logic(boolean a, boolean b, boolean c, boolean d) {
    return a && b && c || d && (a || b);
  }

  void nested(java.util.List<Integer> xs) {
    try {
      for (int x : xs) {
        Runnable r = () -> { if (x > 0) { } };
      }
    } catch (RuntimeException e) {
      int y = e == null ? 0 : 1;
    }
  }

  int recurse(int n) { return n > 0 ? recurse(n - 1) : other.recurse(n); }
}
