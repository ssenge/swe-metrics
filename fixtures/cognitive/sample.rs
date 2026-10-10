// Hand-computed cognitive complexity per function (SonarSource rules), see expected.json.
struct Counter {
    n: i32,
}

impl Counter {
    fn chain(&self, a: Option<i32>) -> i32 {
        if let Some(x) = a {
            x
        } else if self.n > 0 {
            1
        } else {
            0
        }
    }

    fn count(&self, n: i32) -> i32 {
        match n {
            0 => 0,
            _ => self.count(n - 1) + Self::count(self, n - 2),
        }
    }
}

fn loops(grid: &[Vec<i32>]) -> i32 {
    let found = 0;
    'rows: for row in grid {
        let mut i = 0;
        while i < row.len() {
            if row[i] < 0 || row[i] > 9 && found > 0 {
                continue 'rows;
            }
            i += 1;
        }
    }
    found
}

fn retry(mut n: i32) -> i32 {
    let step = |x: i32| if x > 0 { x - 1 } else { 0 };
    loop {
        n = step(n);
        if n == 0 {
            break n;
        }
    }
}

fn drain(stack: &mut Vec<i32>, limit: i32) -> i32 {
    let mut sum = 0;
    while let Some(top) = stack.pop() {
        if let Some(v) = top.checked_mul(2) && v < limit {
            sum += v;
        }
    }
    sum
}

fn depth<T: Clone>(xs: &[T]) -> usize {
    if xs.is_empty() { 0 } else { 1 + depth::<T>(&xs[1..]) }
}
