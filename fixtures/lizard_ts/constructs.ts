export function first<T>(items: T[], pick: (x: T) => boolean): T[] {
  if (items.length === 0) return [];
  return items.filter((x) => pick(x));
}

export const second = <T,>(a: T, b: T): T => {
  if (a) return a;
  return b;
};

function third(a: number, b: number, c: number, d: number): boolean {
  if (a < b && c > d) return true;
  return a < b;
}

export class Box<T> {
  private items: T[] = [];

  get size(): number {
    if (this.items.length > 3) return 3;
    return this.items.length;
  }

  set first(value: T) {
    if (value) this.items.unshift(value);
  }

  map<U>(fn: (x: T) => U): Promise<Array<Map<string, U>>> {
    if (this.items.length === 0) return Promise.resolve([]);
    return Promise.resolve([new Map(this.items.map((x) => ["k", fn(x)]))]);
  }
}

export function last(x: number): number {
  if (x > 0) return 1;
  return 0;
}
