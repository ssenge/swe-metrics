export function inRange(a: number, b: number): boolean {
  return a < b ? a > 0 : b > 0;
}

export function pick(a: number, b: number, c: number): number {
  const low = a < b ? b : a;
  return low < c ? c > 9 ? 9 : c : low;
}

export function fallback(a: number, b: number | null): number {
  return a < b ?? 0 > a ? 1 : 0;
}
