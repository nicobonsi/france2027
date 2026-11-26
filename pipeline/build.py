"""Turn the raw files in pipeline/raw/ into the JSON the site reads (web/data/).

Outputs
  geo.json      projected, simplified SVG paths: metropolitan France, DROM insets, schematic tiles
                for the other overseas collectivities and French voters abroad
  data.json     one record per territory with every lens value (null = not published for it)
  lenses.json   what each lens means, its unit, colour scale, source and coverage
  sources.json  the source list (from sources.py)
  nation.json   national headline figures for the top bar

Run:  python pipeline/fetch.py && python pipeline/build.py
"""
from __future__ import annotations

import json
import math
import zipfile
from pathlib import Path

import pandas as pd
from pyproj import Transformer
from shapely.geometry import shape, MultiPolygon, Polygon
import shapely

from sources import SOURCES

HERE = Path(__file__).parent
RAW = HERE / "raw"
OUT = HERE.parent / "web" / "data"

# ----------------------------------------------------------------------------------------------
# Territories
# ----------------------------------------------------------------------------------------------

# Five overseas départements/regions (DROM): drawn from IGN outlines, each in its own inset, with a
# projection suited to it (Lambert-93 is only valid for mainland France).
DROM = {
    "971": {"name": "Guadeloupe", "epsg": 5490},
    "972": {"name": "Martinique", "epsg": 5490},
    "973": {"name": "Guyane", "epsg": 2972},
    "974": {"name": "La Réunion", "epsg": 2975},
    "976": {"name": "Mayotte", "epsg": 4471},
}

# Other overseas collectivities and voters abroad: IGN's ADMIN EXPRESS has no outlines for them, so
# they are drawn as labelled tiles rather than with made-up shapes. Codes are INSEE COG codes, except
# Saint-Martin/Saint-Barthélemy, which the Ministry of the Interior reports as one unit (ZX), and
# voters abroad (ZZ).
TILES = [
    {"code": "988", "name": "Nouvelle-Calédonie", "status": "Collectivité sui generis (titre XIII)"},
    {"code": "987", "name": "Polynésie française", "status": "Collectivité d'outre-mer (art. 74)"},
    {"code": "986", "name": "Wallis-et-Futuna", "status": "Collectivité d'outre-mer (art. 74)"},
    {"code": "975", "name": "Saint-Pierre-et-Miquelon", "status": "Collectivité d'outre-mer (art. 74)"},
    {"code": "ZX", "name": "Saint-Martin / Saint-Barthélemy", "status": "Deux collectivités d'outre-mer (art. 74), regroupées dans les résultats électoraux"},
    {"code": "ZZ", "name": "Français établis hors de France", "status": "Électeurs inscrits sur les listes consulaires"},
]

# Ministry of the Interior département codes → INSEE codes
ELECTION_CODES = {"ZA": "971", "ZB": "972", "ZC": "973", "ZD": "974", "ZM": "976",
                  "ZN": "988", "ZP": "987", "ZW": "986", "ZS": "975", "ZX": "ZX", "ZZ": "ZZ"}

# ----------------------------------------------------------------------------------------------
# Layout (SVG units ≈ km for mainland France)
# ----------------------------------------------------------------------------------------------
METRO_ORIGIN = (60_000, 7_130_000)    # Lambert-93 (x, y) mapped to SVG (INSET_COL_W, 0)
INSET_COL_W = 240                      # left column for DROM insets
INSET = 190                            # inset box size
INSET_GAP = 18
METRO_W, METRO_H = 1_200, 1_100
TILE_ROW_Y = METRO_H + 20
TILE_W, TILE_H, TILE_GAP = 188, 84, 12
VIEW_W = INSET_COL_W + METRO_W
VIEW_H = TILE_ROW_Y + TILE_H + 20

SIMPLIFY_M = 450

# Enlarged inset for Paris and the inner suburbs, in the empty top-right corner (north of Alsace's latitude).
IDF = ["75", "92", "93", "94"]
IDF_BOX = [INSET_COL_W + 975, 10, 215, 190]  # metres; IGN's CARTO product is already generalised


def transform(fn, geom):
    """Reproject a geometry with a pyproj transform function (vectorised)."""
    return shapely.transform(geom, lambda x, y: fn(x, y), interleaved=False)


def load_geojson(name: str) -> list[dict]:
    return json.loads((RAW / name).read_text())["features"]


def to_svg_path(geom, fx) -> str:
    """Polygon/MultiPolygon → SVG path, coordinates mapped through fx(x, y) and rounded to 0.1."""
    polys = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
    parts = []
    for p in polys:
        for ring in [p.exterior, *p.interiors]:
            pts = [fx(x, y) for x, y in ring.coords]
            if len(pts) < 4:
                continue
            seg = "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in pts[:-1]) + "Z"
            parts.append(seg)
    return "".join(parts)


def drop_specks(geom, min_area: float):
    """Remove islets below min_area (projected units²) so the paths stay light."""
    polys = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
    kept = [p for p in polys if p.area >= min_area] or [max(polys, key=lambda p: p.area)]
    return MultiPolygon(kept) if len(kept) > 1 else kept[0]


def build_geo() -> dict:
    deps = load_geojson("dep.geojson")
    regs = load_geojson("reg.geojson")
    chefs = {f["properties"]["code_insee_du_departement"]: f for f in load_geojson("chefs_dep.geojson")}

    l93 = Transformer.from_crs(4326, 2154, always_xy=True)
    mx0, my0 = METRO_ORIGIN

    def metro_fx(x, y):
        return INSET_COL_W + (x - mx0) / 1000, (my0 - y) / 1000

    features, insets = [], []
    drom_order = ["971", "972", "973", "974", "976"]

    for f in deps:
        p = f["properties"]
        code = p["code_insee"]
        g = shape(f["geometry"])
        chef = chefs.get(code)
        if code in DROM:
            continue
        gp = transform(l93.transform, g).simplify(SIMPLIFY_M, preserve_topology=True)
        gp = drop_specks(gp, 2_000_000)  # 2 km²
        lp = gp.representative_point()
        cx, cy = metro_fx(lp.x, lp.y)
        feat = {"code": code, "name": p["nom_officiel"], "region": p["code_insee_de_la_region"],
                "kind": "dep", "path": to_svg_path(gp, metro_fx), "label": [round(cx, 1), round(cy, 1)]}
        if chef:
            cg = transform(l93.transform, shape(chef["geometry"]))
            feat["capital"] = chef["properties"]["nom_du_chef_lieu"]
            feat["capital_xy"] = [round(v, 1) for v in metro_fx(cg.x, cg.y)]
        features.append(feat)

    # DROM insets, stacked in the left column
    for i, code in enumerate(drom_order):
        f = next(f for f in deps if f["properties"]["code_insee"] == code)
        tr = Transformer.from_crs(4326, DROM[code]["epsg"], always_xy=True)
        gp = transform(tr.transform, shape(f["geometry"]))
        minx, miny, maxx, maxy = gp.bounds
        span = max(maxx - minx, maxy - miny)
        gp = gp.simplify(span / 1500, preserve_topology=True)
        gp = drop_specks(gp, (span / 300) ** 2)
        bx, by = 20, 10 + i * (INSET + INSET_GAP)
        pad = 14
        k = (INSET - 2 * pad - 16) / span  # SVG units per metre (16 px reserved for the caption)
        w, h = (maxx - minx) * k, (maxy - miny) * k
        ox = bx + (INSET - w) / 2
        oy = by + 16 + pad + (INSET - 16 - 2 * pad - h) / 2

        def fx(x, y, ox=ox, oy=oy, k=k, minx=minx, maxy=maxy):
            return ox + (x - minx) * k, oy + (maxy - y) * k

        lp = gp.representative_point()
        feat = {"code": code, "name": DROM[code]["name"], "region": f["properties"]["code_insee_de_la_region"],
                "kind": "drom", "path": to_svg_path(gp, fx), "label": [round(v, 1) for v in fx(lp.x, lp.y)]}
        chef = chefs.get(code)
        if chef:
            cg = transform(tr.transform, shape(chef["geometry"]))
            feat["capital"] = chef["properties"]["nom_du_chef_lieu"]
            feat["capital_xy"] = [round(v, 1) for v in fx(cg.x, cg.y)]
        features.append(feat)
        # scale bar: a round number of km close to a third of the box
        km_per_unit = 1 / (k * 1000)
        target = INSET / 3 * km_per_unit
        nice = min([1, 2, 5, 10, 20, 25, 50, 100, 200], key=lambda v: abs(v - target))
        insets.append({"code": code, "name": DROM[code]["name"], "box": [bx, by, INSET, INSET],
                       "scale_km": nice, "scale_len": round(nice / km_per_unit, 1)})

    # Paris + petite couronne, enlarged
    bx, by, bw, bh = IDF_BOX
    idf = {f["properties"]["code_insee"]: transform(l93.transform, shape(f["geometry"])).simplify(60, preserve_topology=True)
           for f in deps if f["properties"]["code_insee"] in IDF}
    minx = min(g.bounds[0] for g in idf.values()); miny = min(g.bounds[1] for g in idf.values())
    maxx = max(g.bounds[2] for g in idf.values()); maxy = max(g.bounds[3] for g in idf.values())
    k = min((bw - 24) / (maxx - minx), (bh - 40) / (maxy - miny))
    ox = bx + (bw - (maxx - minx) * k) / 2
    oy = by + 22 + (bh - 22 - (maxy - miny) * k) / 2

    def idf_fx(x, y):
        return ox + (x - minx) * k, oy + (maxy - y) * k

    for code in IDF:
        g = idf[code]
        lp = g.representative_point()
        name = next(f["properties"]["nom_officiel"] for f in deps if f["properties"]["code_insee"] == code)
        features.append({"code": code, "name": name, "kind": "dep", "inset": "idf", "path": to_svg_path(g, idf_fx),
                         "label": [round(v, 1) for v in idf_fx(lp.x, lp.y)]})
    km_per_unit = 1 / (k * 1000)
    insets.append({"code": "idf", "name": "Paris et petite couronne", "box": IDF_BOX, "scale_km": 5,
                   "scale_len": round(5 / km_per_unit, 1)})

    # Region outlines (mainland + Corsica only; DROM regions coincide with their département)
    regions = []
    for f in regs:
        p = f["properties"]
        code = p["code_insee"]
        if code in {"01", "02", "03", "04", "06"}:
            continue
        gp = transform(l93.transform, shape(f["geometry"])).simplify(SIMPLIFY_M, preserve_topology=True)
        gp = drop_specks(gp, 2_000_000)
        regions.append({"code": code, "name": p["nom_officiel"], "path": to_svg_path(gp, metro_fx)})

    # Schematic tiles along the bottom
    tiles = []
    x = INSET_COL_W + 10
    for t in TILES:
        tiles.append({**t, "kind": "abroad" if t["code"] == "ZZ" else "com", "box": [x, TILE_ROW_Y, TILE_W, TILE_H]})
        x += TILE_W + TILE_GAP

    metro_scale_len = 100  # 100 km = 100 units
    return {"viewBox": [0, 0, VIEW_W, VIEW_H], "features": features, "regions": regions, "insets": insets,
            "tiles": tiles, "metro_scale": {"km": 100, "len": metro_scale_len, "at": [INSET_COL_W + 40, 60]}}


# ----------------------------------------------------------------------------------------------
# Statistics
# ----------------------------------------------------------------------------------------------

def load_comparateur() -> pd.DataFrame:
    with zipfile.ZipFile(RAW / "comparateur_csv.zip") as z:
        with z.open("comparateur.csv") as fh:
            df = pd.read_csv(fh, sep=";", dtype=str, usecols=["GEO_OBJECT", "GEO", "TIME_PERIOD", "DS", "TAB_MEASURE", "OBS_VALUE"])
    df = df[df.GEO_OBJECT.isin(["DEP", "FRANCE"])].copy()
    df["OBS_VALUE"] = pd.to_numeric(df.OBS_VALUE, errors="coerce")
    return df


def pick(df: pd.DataFrame, measure: str, year: str, ds: str | None = None) -> dict[str, float]:
    sel = df[(df.TAB_MEASURE == measure) & (df.TIME_PERIOD == year) & (df.GEO_OBJECT == "DEP")]
    if ds:
        sel = sel[sel.DS == ds]
    return dict(zip(sel.GEO, sel.OBS_VALUE))


def pick_fr(df: pd.DataFrame, geo: str, measure: str, year: str) -> float | None:
    sel = df[(df.GEO_OBJECT == "FRANCE") & (df.GEO == geo) & (df.TAB_MEASURE == measure) & (df.TIME_PERIOD == year)]
    return float(sel.OBS_VALUE.iloc[0]) if len(sel) else None


def ratio(a: dict, b: dict, k: float = 1.0) -> dict:
    return {g: a[g] / b[g] * k for g in a if g in b and b[g] and not math.isnan(a[g]) and not math.isnan(b[g])}


def quarter_label(col: str) -> str:
    q, y = col.split("_")  # "T2_2026"
    return f"{q[1]}{'er' if q[1] == '1' else 'e'} trimestre {y}"


def load_unemployment():
    """Latest quarter, plus a 12-month change computed on 4-quarter averages.

    DROM series swing by 2-3 points from one quarter to the next (small survey samples), so a raw
    quarter-on-quarter-a-year-earlier difference would mostly show noise.
    """
    x = pd.read_excel(RAW / "sl_etc.xls", sheet_name="Département", header=3, dtype={"Code": str})
    x = x[x.Code.notna()]
    cols = [c for c in x.columns if isinstance(c, str) and c.startswith("T")]
    q = x[cols].apply(pd.to_numeric, errors="coerce")
    now = dict(zip(x.Code, q[cols[-1]]))
    last4, prev4 = q[cols[-4:]].mean(axis=1), q[cols[-8:-4]].mean(axis=1)
    delta = dict(zip(x.Code, last4 - prev4))
    r = pd.read_excel(RAW / "sl_etc.xls", sheet_name="Région", header=3, dtype={"Code": str})
    fr = r[r["Libellé"].astype(str).str.contains("HORS MAYOTTE")]
    national = float(fr[cols[-1]].iloc[0]) if len(fr) else None
    window = (f"moyenne {quarter_label(cols[-8])} – {quarter_label(cols[-5])} → "
              f"moyenne {quarter_label(cols[-4])} – {quarter_label(cols[-1])}")
    return now, delta, national, quarter_label(cols[-1]), window


def load_election():
    df = pd.read_excel(RAW / "pres2022_t1_dpt.xlsx", dtype={"Code du département": str})
    base = list(df.columns[:17])
    rows, nat = {}, {"inscrits": 0, "abst": 0, "exp": 0, "votes": {}}
    for _, r in df.iterrows():
        code = ELECTION_CODES.get(r["Code du département"], r["Code du département"])
        votes = {}
        for i in range(17, len(df.columns), 6):
            name = r.iloc[i + 1]
            if isinstance(name, str):
                votes[f"{r.iloc[i + 2]} {name.title()}"] = int(r.iloc[i + 3])
        exp = int(r["Exprimés"])
        rows[code] = {"inscrits": int(r["Inscrits"]), "abst": int(r["Abstentions"]), "exp": exp, "votes": votes}
        nat["inscrits"] += int(r["Inscrits"])
        nat["abst"] += int(r["Abstentions"])
        nat["exp"] += exp
        for k, v in votes.items():
            nat["votes"][k] = nat["votes"].get(k, 0) + v
    return rows, nat


CANDIDATE_LENSES = [  # (lens id, name as it appears after .title(), colour ramp)
    ("p22_macron", "Emmanuel Macron", "gold"),
    ("p22_lepen", "Marine Le Pen", "navy"),
    ("p22_melenchon", "Jean-Luc Mélenchon", "red"),
    ("p22_zemmour", "Éric Zemmour", "brown"),
    ("p22_pecresse", "Valérie Pécresse", "blue"),
]
CANDIDATE_COLOURS = {  # neutral, conventional-ish colours for the "first place" lens
    "Emmanuel Macron": "#e3b505", "Marine Le Pen": "#1f3a93", "Jean-Luc Mélenchon": "#c0392b",
    "Éric Zemmour": "#6d4c41", "Valérie Pécresse": "#3d7fd1", "Yannick Jadot": "#2e9e4f",
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    geo = build_geo()
    (OUT / "geo.json").write_text(json.dumps(geo, ensure_ascii=False, separators=(",", ":")))

    c = load_comparateur()
    pop = pick(c, "POP", "2023", "DS_RP_SERIE_HISTORIQUE")
    pop17 = pick(c, "POP", "2017", "DS_RP_SERIE_HISTORIQUE")
    sup = pick(c, "SUP", "2023")
    med = pick(c, "MED_SL", "2023")
    pov = pick(c, "PR_MD60", "2023")
    births = pick(c, "LVB", "2025")
    deaths = pick(c, "DTH", "2025")
    dw = pick(c, "DWELLINGS", "2023")
    dw_main = pick(c, "DWELLINGS_OCS_DW_MAIN", "2023")
    dw_own = pick(c, "DWELLINGS_OCS_DW_MAIN_TSH_100", "2023")
    dw_sec = pick(c, "DWELLINGS_OCS_DW_SEC_DW_OCC", "2023")
    dw_vac = pick(c, "DWELLINGS_OCS_DW_VAC", "2023")
    estab = pick(c, "UNIT_LOC", "2024")
    estab_ind = pick(c, "UNIT_LOC_ACTIVITY_BE", "2024")

    unemp, unemp_delta, unemp_nat, unemp_label, unemp_prev_label = load_unemployment()
    elec, elec_nat = load_election()

    values = {
        "population": pop,
        "density": ratio(pop, sup),
        "pop_growth": {g: ((pop[g] / pop17[g]) ** (1 / 6) - 1) * 100 for g in pop if g in pop17 and pop17[g]},
        "natural_balance": {g: (births[g] - deaths[g]) / pop[g] * 1000 for g in pop if g in births and g in deaths},
        "median_income": med,
        "poverty": pov,
        "unemployment": unemp,
        "unemployment_change": unemp_delta,
        "establishments": ratio(estab, pop, 1000),
        "industry_share": ratio(estab_ind, estab, 100),
        "homeowners": ratio(dw_own, dw_main, 100),
        "secondary_homes": ratio(dw_sec, dw, 100),
        "vacant_homes": ratio(dw_vac, dw, 100),
        "p22_abstention": {g: e["abst"] / e["inscrits"] * 100 for g, e in elec.items()},
    }
    for lid, name, _ in CANDIDATE_LENSES:
        values[lid] = {g: e["votes"].get(name, 0) / e["exp"] * 100 for g, e in elec.items() if e["exp"]}
    winner = {g: max(e["votes"].items(), key=lambda kv: kv[1])[0] for g, e in elec.items()}

    # Territory records
    territories = {}
    for f in geo["features"]:
        if f.get("inset"):
            continue
        territories[f["code"]] = {"name": f["name"], "kind": f["kind"], "region": f.get("region"), "capital": f.get("capital")}
    for t in geo["tiles"]:
        territories[t["code"]] = {"name": t["name"], "kind": t["kind"], "status": t["status"]}
    reg_names = {r["code"]: r["name"] for r in geo["regions"]}
    reg_names.update({"01": "Guadeloupe", "02": "Martinique", "03": "Guyane", "04": "La Réunion", "06": "Mayotte"})
    for code, t in territories.items():
        t["region_name"] = reg_names.get(t.get("region"))
        t["values"] = {}
        for lid, m in values.items():
            v = m.get(code)
            t["values"][lid] = None if v is None or (isinstance(v, float) and math.isnan(v)) else round(float(v), 2)
        t["values"]["p22_winner"] = winner.get(code)
        if code in elec:
            e = elec[code]
            t["p22"] = {"inscrits": e["inscrits"], "exprimes": e["exp"],
                        "results": sorted(([k, round(v / e["exp"] * 100, 2)] for k, v in e["votes"].items()), key=lambda kv: -kv[1])}

    (OUT / "data.json").write_text(json.dumps({"territories": territories}, ensure_ascii=False, separators=(",", ":")))

    # Lenses
    NO_MAYOTTE_RP = "Mayotte : le recensement y suit un calendrier distinct et n'est pas publié dans cette base."
    NO_FILO_DOM = "Filosofi ne couvre que La Réunion parmi les DROM ; rien pour la Guadeloupe, la Martinique, la Guyane et Mayotte."
    COM_NOTE = "Les collectivités d'outre-mer (Nouvelle-Calédonie, Polynésie, Wallis, Saint-Pierre, Saint-Martin, Saint-Barthélemy) ont leurs propres instituts statistiques et ne figurent pas dans les bases de l'Insee."
    lenses = [
        {"id": "population", "group": "Population", "label": "Population", "unit": "hab.", "fmt": "int", "scale": "log", "ramp": "teal",
         "year": "2023", "source": "insee_comparateur", "description": "Population municipale du recensement (millésime 2023, collectes 2021–2025).",
         "coverage": f"{NO_MAYOTTE_RP} {COM_NOTE}"},
        {"id": "density", "group": "Population", "label": "Densité", "unit": "hab./km²", "fmt": "int", "scale": "log", "ramp": "teal",
         "year": "2023", "source": "insee_comparateur", "description": "Population 2023 divisée par la superficie.", "coverage": f"{NO_MAYOTTE_RP} {COM_NOTE}"},
        {"id": "pop_growth", "group": "Population", "label": "Croissance démographique", "unit": "%/an", "fmt": "pct2", "scale": "diverging", "ramp": "diverging",
         "year": "2017–2023", "source": "insee_comparateur", "description": "Taux de variation annuel moyen de la population entre les recensements 2017 et 2023.",
         "coverage": f"{NO_MAYOTTE_RP} {COM_NOTE}"},
        {"id": "natural_balance", "group": "Population", "label": "Solde naturel", "unit": "‰", "fmt": "dec1", "scale": "diverging", "ramp": "diverging",
         "year": "2025", "source": "insee_comparateur", "description": "Naissances moins décès en 2025, pour 1 000 habitants (population 2023).",
         "coverage": f"Mayotte : naissances et décès publiés, mais sans population de référence dans cette base. {COM_NOTE}"},
        {"id": "median_income", "group": "Revenus", "label": "Niveau de vie médian", "unit": "€/an", "fmt": "eur", "scale": "linear", "ramp": "green",
         "year": "2023", "source": "insee_comparateur", "higher_is": "good",
         "description": "Revenu disponible du ménage par unité de consommation, valeur médiane (Filosofi). Un adulte seul = 1 UC.",
         "coverage": f"{NO_FILO_DOM} {COM_NOTE}"},
        {"id": "poverty", "group": "Revenus", "label": "Taux de pauvreté", "unit": "%", "fmt": "pct1", "scale": "linear", "ramp": "orange",
         "year": "2023", "source": "insee_comparateur", "higher_is": "bad",
         "description": "Part des personnes dont le niveau de vie est inférieur à 60 % du niveau de vie médian national (Filosofi).",
         "coverage": f"{NO_FILO_DOM} {COM_NOTE}"},
        {"id": "unemployment", "group": "Emploi", "label": "Taux de chômage", "unit": "%", "fmt": "pct1", "scale": "linear", "ramp": "orange",
         "year": unemp_label, "source": "insee_chomage", "higher_is": "bad",
         "description": "Taux de chômage localisé au sens du BIT, moyenne trimestrielle corrigée des variations saisonnières.",
         "coverage": f"Mayotte : non publié dans cette série (l'Insee y mène une enquête Emploi annuelle distincte). {COM_NOTE}"},
        {"id": "unemployment_change", "group": "Emploi", "label": "Chômage : évolution sur un an", "unit": "pts", "fmt": "pts", "scale": "diverging", "ramp": "diverging_rev",
         "year": unemp_prev_label, "source": "insee_chomage", "higher_is": "bad",
         "description": "Variation du taux de chômage localisé, en points : moyenne des quatre derniers trimestres comparée à celle des quatre précédents (lisse la volatilité trimestrielle).",
         "coverage": "Mêmes limites que le taux de chômage. Dans les DROM, les séries trimestrielles varient fortement d'un trimestre à l'autre (petits échantillons) : à lire avec prudence."},
        {"id": "establishments", "group": "Économie", "label": "Établissements pour 1 000 hab.", "unit": "‰", "fmt": "dec1", "scale": "linear", "ramp": "purple",
         "year": "2024", "source": "insee_comparateur", "description": "Établissements actifs employeurs ou non (Flores) rapportés à la population 2023.",
         "coverage": f"Mayotte : établissements publiés, mais sans population de référence. {COM_NOTE}"},
        {"id": "industry_share", "group": "Économie", "label": "Part de l'industrie", "unit": "%", "fmt": "pct1", "scale": "linear", "ramp": "purple",
         "year": "2024", "source": "insee_comparateur",
         "description": "Part des établissements relevant de l'industrie (manufacturière, extractive, énergie, eau, déchets).",
         "coverage": COM_NOTE},
        {"id": "homeowners", "group": "Logement", "label": "Propriétaires occupants", "unit": "%", "fmt": "pct1", "scale": "linear", "ramp": "teal",
         "year": "2023", "source": "insee_comparateur", "description": "Part des résidences principales occupées par leur propriétaire.",
         "coverage": f"{NO_MAYOTTE_RP} {COM_NOTE}"},
        {"id": "secondary_homes", "group": "Logement", "label": "Résidences secondaires", "unit": "%", "fmt": "pct1", "scale": "log", "ramp": "teal",
         "year": "2023", "source": "insee_comparateur", "description": "Part des résidences secondaires et logements occasionnels dans le parc.",
         "coverage": f"{NO_MAYOTTE_RP} {COM_NOTE}"},
        {"id": "vacant_homes", "group": "Logement", "label": "Logements vacants", "unit": "%", "fmt": "pct1", "scale": "linear", "ramp": "orange",
         "year": "2023", "source": "insee_comparateur", "description": "Part des logements vacants dans le parc.", "coverage": f"{NO_MAYOTTE_RP} {COM_NOTE}"},
        {"id": "p22_winner", "group": "Présidentielle 2022", "label": "Arrivé(e) en tête au 1er tour", "scale": "categorical",
         "colors": CANDIDATE_COLOURS, "year": "10 avril 2022", "source": "mi_pres2022_t1",
         "description": "Candidat ayant obtenu le plus de suffrages exprimés au premier tour.", "coverage": "Tous les territoires, y compris les COM et les Français de l'étranger."},
        {"id": "p22_abstention", "group": "Présidentielle 2022", "label": "Abstention (1er tour)", "unit": "%", "fmt": "pct1", "scale": "linear", "ramp": "grey",
         "year": "10 avril 2022", "source": "mi_pres2022_t1", "description": "Abstentions rapportées aux inscrits.",
         "coverage": "Tous les territoires. À l'étranger, l'abstention structurelle est très élevée (listes consulaires peu tenues à jour)."},
    ]
    for lid, name, ramp in CANDIDATE_LENSES:
        lenses.append({"id": lid, "group": "Présidentielle 2022", "label": name, "unit": "% exprimés", "fmt": "pct1", "scale": "linear", "ramp": ramp,
                       "year": "10 avril 2022", "source": "mi_pres2022_t1", "description": f"Score de {name} au premier tour, en % des suffrages exprimés.",
                       "coverage": "Tous les territoires."})
    (OUT / "lenses.json").write_text(json.dumps({"lenses": lenses}, ensure_ascii=False, indent=1))

    (OUT / "sources.json").write_text(json.dumps(
        [{k: s[k] for k in ("id", "title", "publisher", "page", "licence")} for s in SOURCES], ensure_ascii=False, indent=1))

    pop_total = sum(v for v in pop.values() if not math.isnan(v))
    nation = {
        "headline": [
            {"id": "population", "label": "Population", "value": pop_total, "fmt": "millions", "note": "Recensement 2023, France hors Mayotte et hors COM."},
            {"id": "unemployment", "label": "Chômage", "value": unemp_nat, "fmt": "pct1", "note": f"{unemp_label}, France hors Mayotte."},
            {"id": "poverty", "label": "Pauvreté", "value": pick_fr(c, "FM", "PR_MD60", "2023"), "fmt": "pct1", "note": "2023, France métropolitaine (Filosofi)."},
            {"id": "median_income", "label": "Niveau de vie médian", "value": pick_fr(c, "FM", "MED_SL", "2023"), "fmt": "eur", "note": "2023, France métropolitaine (Filosofi)."},
            {"id": "p22_abstention", "label": "Abstention 2022", "value": round(elec_nat["abst"] / elec_nat["inscrits"] * 100, 2), "fmt": "pct1",
             "note": "Présidentielle 2022, 1er tour, ensemble des inscrits."},
        ],
        "p22": sorted(([k, round(v / elec_nat["exp"] * 100, 2)] for k, v in elec_nat["votes"].items()), key=lambda kv: -kv[1]),
    }
    (OUT / "nation.json").write_text(json.dumps(nation, ensure_ascii=False, indent=1))

    for p in sorted(OUT.glob("*.json")):
        print(f"{p.name:14s} {p.stat().st_size / 1024:8.1f} KB")


if __name__ == "__main__":
    main()
