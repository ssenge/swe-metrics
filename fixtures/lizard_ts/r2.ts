export class Calendar {
  view(days: string[], today: string): Record<string, unknown> {
    return {
      today,
      days: days.map((date) => ({ date, past: date < today })),
    };
  }

  desk(id: number): number {
    if (id > 1) return 1;
    if (id > 2) return 2;
    return 0;
  }

  other(x: number): number {
    if (x > 0) return 1;
    return 0;
  }
}
