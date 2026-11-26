// French number formatting.
const nf = (opts) => new Intl.NumberFormat("fr-FR", opts);
const INT = nf({ maximumFractionDigits: 0 });
const D1 = nf({ minimumFractionDigits: 1, maximumFractionDigits: 1 });
const D2 = nf({ minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function fmt(v, kind) {
  if (v == null || !Number.isFinite(v)) return "—";
  switch (kind) {
    case "int": return INT.format(v);
    case "dec1": return D1.format(v);
    case "pct1": return `${D1.format(v)} %`;
    case "pct2": return `${v > 0 ? "+" : ""}${D2.format(v)} %`;
    case "pts": return `${v > 0 ? "+" : ""}${D1.format(v)} pt${Math.abs(v) >= 2 ? "s" : ""}`;
    case "eur": return `${INT.format(Math.round(v / 10) * 10)} €`;
    case "millions": return `${D1.format(v / 1e6)} M`;
    default: return D1.format(v);
  }
}
