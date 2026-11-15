export function view(days: string[], today: string): boolean[] {
  return days.map((date) => date < today);
}

function desk(id: number): number {
  if (id > 1) return 1;
  if (id > 2) return 2;
  return 0;
}

function other(x: number): number {
  if (x > 0) return 1;
  return 0;
}
