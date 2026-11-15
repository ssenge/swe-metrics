export function first(a: number, onDone: (x: number) => void): void {
  if (a > 1) onDone(1);
  if (a > 2) onDone(2);
}

function second(b: string): string {
  if (b === "x") return "x";
  return b;
}

function third(c: number): number {
  if (c > 0) return 1;
  return 0;
}
