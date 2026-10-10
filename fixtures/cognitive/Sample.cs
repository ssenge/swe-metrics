// Hand-computed cognitive complexity per method (SonarSource rules), see expected.json.
using System;
using System.Collections.Generic;

class Sample
{
    Sample(int a)
    {
        if (a > 0 && a < 10) { Console.WriteLine(a); }
    }

    int Chain(int a)
    {
        if (a == 1) { return 1; } else if (a == 2) { return 2; } else { return 3; }
    }

    int Loops(List<int> xs)
    {
        int total = 0;
        foreach (var x in xs)
        {
            for (int i = 0; i < x; i++)
            {
                while (total > 100 && x > 0 || i < 0)
                {
                    total--;
                }
            }
        }
        do { total++; } while (total < 0);
        return total;
    }

    string Switches(int a)
    {
        switch (a)
        {
            case 1:
                goto default;
            default:
                var s = a switch { 0 => "zero", _ => a > 0 ? "pos" : "neg" };
                return s ?? "";
        }
    }

    void Nested(List<int> xs)
    {
        try
        {
            Func<int, int> f = x => x > 0 ? 1 : 0;
            int Local(int y) { if (y > 0) { return y; } return 0; }
            Action g = delegate { foreach (var x in xs) { Console.WriteLine(Local(x) + f(x)); } };
            g();
        }
        catch (Exception e) when (e != null)
        {
            Console.WriteLine(e);
        }
    }

    int Recurse(int n, Sample other)
    {
        return n > 0 ? this.Recurse(n - 1, other) + Recurse(n - 2, other) : other.Recurse(n, other);
    }
}
