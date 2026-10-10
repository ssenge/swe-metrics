/* Hand-computed cognitive complexity per function (SonarSource rules), see expected.json. */
#include <stddef.h>

int chain(int a)
{
    if (a == 1) {
        return 1;
    } else if (a == 2) {
        return 2;
    } else {
        return 3;
    }
}

int loops(const int *xs, int n)
{
    int sum = 0;
    for (int i = 0; i < n; i++) {
        int j = 0;
        while (j < i) {
            if (xs[i] > 0 && xs[j] > 0 || xs[i] < 0) {
                sum++;
            }
            j++;
        }
    }
    return sum;
}

int sw(int a)
{
    switch (a) {
    case 1:
        return a > 0 ? 1 : 0;
    default:
        goto end;
    }
end:
    return sw(a - 1);
}

static const char *pick(const char *a, const char *b)
{
    return (a != NULL && (b == NULL || *a)) ? a : b;
}

int drain(int n)
{
    do {
        n--;
    } while (n > 0 && n != 7);
    return n;
}
