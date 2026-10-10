// Hand-computed cognitive complexity per function (SonarSource rules), see expected.json.
function chain(a) {
  if (a === 1) { return 1; } else if (a === 2) { return 2; } else { return 3; }
}
const arrow = (xs) => {
  outer: for (const x of xs) {
    for (const y of xs) {
      if (x && y) { continue outer; }
    }
  }
};
class K {
  m(a) { return a ? this.m(a - 1) : 0; }
  n(a) { switch (a) { case 1: return [1].map(v => v ? 1 : 0); default: return 0; } }
}
function tryIt(f) { try { f(); } catch (e) { return e || null; } }
