// Hand-computed cognitive complexity per function (SonarSource rules), see expected.json.
#include <stdexcept>
#include <string>
#include <vector>

auto twice = [](int x) { return x > 0 ? 2 * x : 0; };

class Tree {
public:
    int *buffer = nullptr;
    int depth(const Tree *t) const;

    ~Tree()
    {
        if (buffer != nullptr) {
            delete[] buffer;
        }
    }

    int sum(const std::vector<int> &xs) const
    {
        int total = 0;
        for (int x : xs) {
            auto keep = [&](int y) {
                if (y > 0 && x > 0) {
                    return true;
                }
                return false;
            };
            total += keep(x) ? x : 0;
        }
        return total;
    }
};

int Tree::depth(const Tree *t) const
{
    if (t == nullptr) {
        return 0;
    }
    return 1 + this->depth(nullptr);
}

int parse(const std::string &s)
{
    try {
        return std::stoi(s);
    } catch (const std::invalid_argument &) {
        return -1;
    } catch (...) {
        if (s.empty()) {
            throw;
        }
        return -2;
    }
}

template <typename T>
T power(T base, int n)
{
    if (n == 0) {
        return 1;
    } else if (n % 2 == 0) {
        T half = power<T>(base, n / 2);
        return half * half;
    }
    return base * power(base, n - 1);
}
