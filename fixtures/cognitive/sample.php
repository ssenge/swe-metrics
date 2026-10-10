<?php
// Hand-computed cognitive complexity per function (SonarSource rules), see expected.json.
function chain($a)
{
    if ($a == 1) {
        return 1;
    } elseif ($a == 2) {
        return 2;
    } else if ($a == 3) {
        return 3;
    } else {
        return 4;
    }
}

function loops(array $xs)
{
    $total = 0;
    foreach ($xs as $x) {
        for ($i = 0; $i < $x; $i++) {
            if ($x < 0 and $i > 0 or $i < -1) {
                continue 2;
            }
            $total += $i;
        }
    }
    return $total;
}

function branches($a)
{
    switch ($a) {
        case 1:
            goto done;
        default:
            $a = match (true) { $a > 0 => 1, default => -1 };
    }
    $a = $a ?: ($a > 0 ? 1 : 0);
done:
    return $a;
}

class Sample
{
    public function nested(array $xs)
    {
        try {
            $f = function ($x) use ($xs) { while ($x > 0) { $x--; } return $x; };
            $g = fn($x) => $x > 0 ? 1 : 0;
            return $f($g(1));
        } catch (RuntimeException $e) {
            do {
                $e = null;
            } while ($e);
        }
    }

    public function recurse($n, $o)
    {
        return $n > 0 && $n < 100
            ? $this->recurse($n - 1, $o) + self::recurse($n - 2, $o) + static::recurse(0, $o)
            : Other::recurse($n, $o) + $o->recurse(1, $o);
    }
}
