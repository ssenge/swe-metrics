// Hand-computed cognitive complexity per function (SonarSource rules), see expected.json.
fun chain(a: Int): Int {
    if (a == 1) { return 1 } else if (a == 2) { return 2 } else { return 3 }
}

fun expr(a: Int, b: Boolean, c: Int?): Int {
    val v = if (a > 0 && b) 1 else 2
    val w = c ?: 0
    return when {
        a > 0 || !b -> v
        else -> w
    }
}

fun loops(xs: List<Int>): Int {
    var total = 0
    outer@ for (x in xs) {
        var i = 0
        while (i < x) {
            if (x < 0) continue@outer
            i++
        }
    }
    do { total++ } while (total < 0)
    return total
}

class Sample(private val other: Sample?) {
    fun nested(xs: List<Int>) {
        try {
            xs.forEach { x -> if (x > 0) println(x) }
            val f = fun(y: Int): Int { return when (y) { 0 -> 1; else -> 2 } }
            println(f(1))
        } catch (e: IllegalStateException) {
            println(e)
        } catch (e: Exception) {
            println(e)
        }
    }

    fun recurse(n: Int): Int =
        if (n > 0) this.recurse(n - 1) + recurse(n - 2) else other?.recurse(n) ?: 0
}
