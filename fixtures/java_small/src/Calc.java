// Fixture with known metric values (see ../expected.json). Do not reformat.
public class Calc {
    public int max(int a, int b) {
        if (a > b) {
            return a;
        }
        return b;
    }

    public int sum(int[] xs) {
        int s = 0;
        for (int x : xs) {
            s += x;
        }
        return s;
    }

    public String sign(int n) {
        if (n > 0 && n < 100) {
            return "small";
        } else if (n >= 100) {
            return "big";
        }
        return n == 0 ? "zero" : "negative";
    }
}
