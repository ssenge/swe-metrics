export function First({ a, onDone }: { a: number; onDone: (x: number) => void }) {
  if (a > 1) onDone(1);
  if (a > 2) return <b>big</b>;
  return <span>{a}</span>;
}

function Second({ b }: { b: string }) {
  if (b === "x") return <i>x</i>;
  return <span>{b}</span>;
}

export function Third({ c }: { c: number }) {
  if (c > 0) return <p>one</p>;
  return <p>zero</p>;
}
