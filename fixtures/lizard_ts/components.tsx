export const Gen = <T extends unknown>({ v }: { v: T }) => {
  if (!v) return null;
  return <p>{String(v)}</p>;
};

export function Row({ a, b }: { a: number; b: number }) {
  return <tr className={a < b ? "lt" : "ge"}>{a > 0 && <td>{a}</td>}</tr>;
}

export function Grid({ n, today }: { n: number; today: number }) {
  const past = [n].filter((d) => d < today);
  if (past.length > 10) return <div>{past.map((p) => <Row key={p} a={p} b={n} />)}</div>;
  return <table />;
}
