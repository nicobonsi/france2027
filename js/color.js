// Colour ramps (light → dark on the dark map), interpolated in linear RGB.
export const MISSING_FILL = "#2b3542";

export const RAMPS = {
  teal: ["#e6f2ef", "#a8d8cf", "#5fb3a8", "#2c8582", "#165a62", "#0b3a46"],
  green: ["#f2f0d9", "#cfe3a3", "#94c66f", "#57a046", "#2e7432", "#174a22"],
  orange: ["#fbeed8", "#f6cd92", "#ee9f55", "#d8692f", "#ab3f1f", "#6e2112"],
  purple: ["#efe9f6", "#cfc0e6", "#a690cf", "#7d62b3", "#57408f", "#352464"],
  grey: ["#f1efe9", "#cfcbc2", "#a7a296", "#7c776d", "#57534b", "#36332e"],
  gold: ["#fbf3d6", "#f3dd8f", "#e3b84a", "#c08f1c", "#8f650f", "#5a3f07"],
  navy: ["#e8edf7", "#b6c4e3", "#7f97c9", "#4d68aa", "#2b4483", "#162758"],
  red: ["#fbe9e6", "#f2b7ab", "#e47e6b", "#cb4a39", "#9b2a1f", "#62160f"],
  brown: ["#f4ece6", "#dcc3b2", "#bf9779", "#9a6d4e", "#6f4a32", "#462d1d"],
  blue: ["#e8f1fb", "#b4d2f1", "#79ade3", "#3f84cc", "#1f5ea3", "#0e3b6e"],
  diverging: ["#2166ac", "#67a9cf", "#d1e5f0", "#f7f7f7", "#fddbc7", "#ef8a62", "#b2182b"],
  duel: ["#162758", "#2b4483", "#7f97c9", "#e9e4d6", "#f3dd8f", "#e3b84a", "#9a7108"], // Le Pen ← 50 % → Macron
  diverging_rev: ["#1a9850", "#91cf60", "#d9ef8b", "#f7f7f7", "#fee08b", "#fc8d59", "#d73027"],
};

const toLin = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
const toSrgb = (c) => Math.round(255 * (c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055));
const parse = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const hex = (rgb) => "#" + rgb.map((v) => Math.max(0, Math.min(255, v)).toString(16).padStart(2, "0")).join("");

export function rampColor(ramp, t) {
  const x = t * (ramp.length - 1);
  const i = Math.min(Math.floor(x), ramp.length - 2);
  const f = x - i;
  const a = parse(ramp[i]).map(toLin), b = parse(ramp[i + 1]).map(toLin);
  return hex(a.map((v, k) => toSrgb(v + (b[k] - v) * f)));
}

// Text colour that reads on a given fill.
export function textOn(fill) {
  if (!fill.startsWith("#")) return "#f4efe2";
  const [r, g, b] = parse(fill).map(toLin);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.25 ? "#0c1520" : "#f4efe2";
}
