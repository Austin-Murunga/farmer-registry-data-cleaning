"""Analytical work sample: cleaning and reconciling a synthetic farmer registry.

All data is generated here with a fixed seed. Nothing comes from a real organisation.
Run: py -I build_sample.py <output_dir>
"""
import inspect
import re
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
AS_OF = date(2026, 11, 21)
PROGRAMME_START = date(2023, 1, 1)
rng = np.random.default_rng(42)

COUNTIES = ["Kiambu", "Murang'a", "Nakuru", "Meru", "Machakos", "Kakamega"]
VARIANTS = {
    "Kiambu": ["kiambu", "Kiambu County", "KIAMBU ", "Kiambu"],
    "Murang'a": ["Muranga", "Murang'a County", "muranga", "Murang’a"],
    "Nakuru": ["nakuru", "Nakuru County", " Nakuru", "NAKURU"],
    "Meru": ["meru", "Meru County", "MERU"],
    "Machakos": ["machakos", "Machakos County", "Machakos "],
    "Kakamega": ["kakamega", "Kakamega County", "KAKAMEGA"],
}
FIRST = ["Wanjiru", "Kamau", "Achieng", "Otieno", "Mutua", "Njeri", "Kiprop", "Wambui", "Mwangi",
         "Akinyi", "Chebet", "Muthoni", "Kariuki", "Nyambura", "Omondi", "Wekesa", "Nafula", "Karimi"]
LAST = ["Mwangi", "Odhiambo", "Kamau", "Wanjiku", "Mutiso", "Kiplagat", "Njoroge", "Wafula",
        "Gitau", "Ndungu", "Barasa", "Kirui", "Muriuki", "Onyango", "Kilonzo", "Shikuku"]
PROGRAMMES = ["Compost training", "Input credit", "Market linkage"]


# ---------------------------------------------------------------- synthetic data
def make_registry(n=480):
    rows = []
    for i in range(1, n + 1):
        reg = PROGRAMME_START + timedelta(days=int(rng.integers(0, (AS_OF - PROGRAMME_START).days - 30)))
        rows.append({
            "farmer_id": f"FR-{i:04d}",
            "name": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
            "phone": f"07000{i:05d}",  # clearly fictional numbers, never real ones
            "county": str(rng.choice(COUNTIES)),
            "gender": str(rng.choice(["F", "M"], p=[0.56, 0.44])),
            "programme": str(rng.choice(PROGRAMMES, p=[0.5, 0.3, 0.2])),
            "acres": round(float(rng.gamma(2.0, 0.6)), 1),
            "registration_date": reg.isoformat(),
            "last_updated": (reg + timedelta(days=int(rng.integers(0, 60)))).isoformat(),
        })
    return pd.DataFrame(rows)


def inject_issues(clean):
    df = clean.copy()
    idx = lambda k: rng.choice(df.index, k, replace=False)
    # inconsistent county names
    for i in idx(150):
        df.at[i, "county"] = str(rng.choice(VARIANTS[df.at[i, "county"]]))
    # messy phone formats
    for i in idx(90):
        p = df.at[i, "phone"]
        df.at[i, "phone"] = str(rng.choice(["+254" + p[1:], p[1:], f"{p[:4]} {p[4:7]} {p[7:]}"]))
    # mixed and impossible dates
    for i in idx(70):
        d = date.fromisoformat(df.at[i, "registration_date"])
        df.at[i, "registration_date"] = str(rng.choice([d.strftime("%d/%m/%Y"), d.strftime("%d %b %Y")]))
    for i in idx(6):
        df.at[i, "registration_date"] = (AS_OF + timedelta(days=int(rng.integers(30, 400)))).isoformat()
    for i in idx(5):
        df.at[i, "registration_date"] = str(rng.choice(["1900-01-01", "2019-06-15", "2020-02-30"]))
    # missing values
    for col, k in [("phone", 22), ("county", 14), ("gender", 30), ("acres", 25)]:
        df.loc[idx(k), col] = None
    # names typed inconsistently
    for i in idx(40):
        n = df.at[i, "name"]
        df.at[i, "name"] = str(rng.choice([n.upper(), n.lower(), "  " + n.replace(" ", "   ")]))
    # conflicting versions of the same farmer (field team edits, later update wins)
    conflicts = df.loc[idx(15)].copy()
    conflicts["acres"] = (conflicts["acres"].fillna(1) + 0.5).round(1)
    conflicts["last_updated"] = [(date.fromisoformat(x) + timedelta(days=30)).isoformat()
                                 for x in conflicts["last_updated"]]
    # re-registrations: same person, same phone, new ID
    rereg_src = df[df["phone"].notna() & df["phone"].str.fullmatch(r"0[17]\d{8}")].sample(12, random_state=7)
    rereg = rereg_src.copy()
    rereg["farmer_id"] = [f"FR-{900 + k:04d}" for k in range(len(rereg))]
    rereg["name"] = rereg["name"].str.lower()
    rereg["registration_date"] = [(date.fromisoformat(x) + timedelta(days=90)).isoformat()
                                  if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(x)) and x[:4] > "2022" else x
                                  for x in rereg["registration_date"]]
    # exact duplicate rows (double upload)
    exact = df.loc[idx(18)].copy()
    raw = pd.concat([df, conflicts, rereg, exact]).sample(frac=1, random_state=3).reset_index(drop=True)
    return raw, rereg_src["farmer_id"].tolist(), rereg["farmer_id"].tolist()


def make_sales(clean, rereg_ids, n=1200):
    rows = []
    ids = clean["farmer_id"].tolist()
    for k in range(n):
        fid = str(rng.choice(ids))
        reg = date.fromisoformat(clean.set_index("farmer_id").at[fid, "registration_date"])
        d = reg + timedelta(days=int(rng.integers(1, max(2, (AS_OF - reg).days))))
        rows.append({"sale_id": f"S-{k + 1:05d}", "farmer_id": fid, "sale_date": d.isoformat(),
                     "amount_kes": int(rng.integers(5, 120)) * 100})
    s = pd.DataFrame(rows)
    s.loc[s.sample(40, random_state=1).index, "farmer_id"] = rng.choice(rereg_ids, 40)  # sold under the new ID
    s.loc[s.sample(30, random_state=2).index, "farmer_id"] = [f"FR-{x:04d}" for x in rng.integers(5000, 6000, 30)]
    early = s.sample(8, random_state=4).index
    s.loc[early, "sale_date"] = "2022-11-15"
    return s


# ---------------------------------------------------------------- cleaning rules
COUNTY_LOOKUP = {re.sub(r"[^a-z]", "", v.lower().replace("county", "")): k
                 for k, vs in VARIANTS.items() for v in vs + [k]}


def standardise_county(value):
    """Map any spelling to one agreed county name; unknown stays missing for review."""
    if value is None or pd.isna(value):
        return None
    key = re.sub(r"[^a-z]", "", str(value).lower().replace("county", ""))
    return COUNTY_LOOKUP.get(key)


def standardise_phone(value):
    """Return a 10-digit Kenyan mobile number (07XXXXXXXX / 01XXXXXXXX) or None."""
    if value is None or pd.isna(value):
        return None
    digits = re.sub(r"\D", "", str(value))
    if digits.startswith("254"):
        digits = "0" + digits[3:]
    elif len(digits) == 9:
        digits = "0" + digits
    return digits if re.fullmatch(r"0[17]\d{8}", digits) else None


def parse_date(value):
    """Accept the three formats seen in the field; reject impossible or out-of-range dates."""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d %b %Y"):
        try:
            d = datetime.strptime(str(value).strip(), fmt).date()
            return d if PROGRAMME_START <= d <= AS_OF else None
        except ValueError:
            continue
    return None


def resolve_conflicts(df):
    """Same farmer_id more than once: keep the most recently updated record."""
    return (df.sort_values("last_updated")
              .drop_duplicates("farmer_id", keep="last"))


def merge_reregistrations(df):
    """Same person registered twice (same phone + same name): keep the earliest farmer_id."""
    df = df.copy()
    df["_key"] = df["phone"] + "|" + df["name"]
    has_key = df["_key"].notna()
    keep = (df[has_key].sort_values(["registration_date", "farmer_id"])
              .groupby("_key")["farmer_id"].transform("first"))
    id_map = {old: new for old, new in zip(df.loc[keep.index, "farmer_id"], keep) if old != new}
    df = df[~df["farmer_id"].isin(id_map)].drop(columns="_key")
    return df, id_map


SQL_LATEST = """
-- Keep the latest version of each farmer (same rule as resolve_conflicts)
WITH ranked AS (
  SELECT *,
         ROW_NUMBER() OVER (PARTITION BY farmer_id
                            ORDER BY last_updated DESC) AS rn
  FROM registry_raw
)
SELECT * FROM ranked WHERE rn = 1;
""".strip()

SQL_LINK = """
-- Sales that do not link to a registered farmer, after ID merges
SELECT s.sale_id, s.farmer_id, s.sale_date
FROM sales s
LEFT JOIN id_map m   ON m.old_id = s.farmer_id
LEFT JOIN registry r ON r.farmer_id = COALESCE(m.new_id, s.farmer_id)
WHERE r.farmer_id IS NULL;
""".strip()


# ---------------------------------------------------------------- run
truth = make_registry()
raw, rereg_src_ids, rereg_ids = inject_issues(truth)
sales = make_sales(truth, rereg_ids)
raw.to_csv(OUT / "registry_raw.csv", index=False)
sales.to_csv(OUT / "sales_raw.csv", index=False)

log = []
std = set(COUNTIES)
iso_ok = lambda s: bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(s))) and parse_date(s) is not None
before = {
    "Valid phone": raw["phone"].fillna("").str.fullmatch(r"0[17]\d{8}").mean(),
    "Standard county": raw["county"].isin(std).mean(),
    "Valid registration date": raw["registration_date"].map(iso_ok).mean(),
}
county_labels_before = raw["county"].dropna().nunique()

df = raw.drop_duplicates()
log.append(("Exact duplicate rows (double upload)", len(raw) - len(df), "Removed"))

df = df.copy()
names_before = df["name"].copy()
df["name"] = df["name"].str.split().str.join(" ").str.title()
log.append(("Inconsistent name formatting", int((names_before != df["name"]).sum()), "Trimmed and title-cased"))

c_before = df["county"].copy()
df["county"] = df["county"].map(standardise_county)
log.append(("County spelt differently", int((c_before.notna() & (c_before != df["county"])).sum()),
            "Mapped to 6 agreed names"))

p_before = df["phone"].copy()
df["phone"] = df["phone"].map(standardise_phone)
log.append(("Phone in non-standard format", int((p_before.notna() & df["phone"].notna() & (p_before != df["phone"])).sum()),
            "Converted to 07XXXXXXXX"))

d_raw = df["registration_date"].copy()
df["registration_date"] = df["registration_date"].map(parse_date)
mixed = int(d_raw.map(lambda s: not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(s))).sum() - df["registration_date"].isna().sum()
            + d_raw[df["registration_date"].isna()].map(lambda s: not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(s))).sum())
log.append(("Date in mixed formats", mixed, "Parsed to one format"))
bad_dates = df[df["registration_date"].isna()]
log.append(("Impossible or out-of-range date", len(bad_dates), "Set blank, sent back to field team"))
df["registration_date"] = df["registration_date"].map(lambda d: d.isoformat() if d else None)

n0 = len(df)
df = resolve_conflicts(df)
log.append(("Conflicting versions of a farmer", n0 - len(df), "Kept latest update"))

n0 = len(df)
df, id_map = merge_reregistrations(df)
log.append(("Same farmer registered twice", n0 - len(df), "Merged to earliest ID"))

missing = {c: int(df[c].isna().sum()) for c in ["phone", "county", "gender", "acres"]}
log.append(("Missing values (phone/county/gender/acres)", sum(missing.values()),
            "Not guessed; reported and flagged"))

clean = df.sort_values("farmer_id").reset_index(drop=True)
clean.to_csv(OUT / "registry_clean.csv", index=False)

# SQL check: the window-function query must agree with the pandas rule
con = sqlite3.connect(":memory:")
dedup_input = raw.drop_duplicates()
dedup_input.to_sql("registry_raw", con, index=False)
sql_rows = pd.read_sql(SQL_LATEST, con)
assert len(sql_rows) == dedup_input["farmer_id"].nunique() == len(resolve_conflicts(dedup_input)), "SQL and pandas disagree"

clean.to_sql("registry", con, index=False)
sales.to_sql("sales", con, index=False)
pd.DataFrame(list(id_map.items()), columns=["old_id", "new_id"]).to_sql("id_map", con, index=False)
orphans = pd.read_sql(SQL_LINK, con)

raw_counts = raw["farmer_id"].value_counts()
linked_before = sales["farmer_id"].map(raw_counts).eq(1).mean()
mapped = sales["farmer_id"].replace(id_map)
linked_after = mapped.isin(clean["farmer_id"]).mean()
reg_dates = clean.set_index("farmer_id")["registration_date"]
s2 = sales.assign(fid=mapped, reg=mapped.map(reg_dates))
early_sales = s2[s2["reg"].notna() & (s2["sale_date"] < s2["reg"])]
log.append(("Sales under a merged (duplicate) ID", int(sales["farmer_id"].isin(id_map).sum()), "Re-pointed to kept ID"))
log.append(("Sales with an unknown farmer ID", len(orphans), "Flagged for Sales to correct"))
log.append(("Sale dated before registration", len(early_sales), "Flagged for review"))

after = {
    "Valid phone": clean["phone"].notna().mean(),
    "Standard county": clean["county"].isin(std).mean(),
    "Valid registration date": clean["registration_date"].notna().mean(),
}
county_labels_after = clean["county"].dropna().nunique()
log_df = pd.DataFrame(log, columns=["Issue", "Rows", "Action"])
log_df.to_csv(OUT / "issue_log.csv", index=False)

# ---------------------------------------------------------------- charts
plt.rcParams.update({"font.family": "Times New Roman", "font.size": 10})
BLUE, GREY = "#1f5f99", "#b8c4d0"

fig, ax = plt.subplots(figsize=(6.6, 3.3))
lg = log_df.iloc[::-1]
ax.barh(lg["Issue"], lg["Rows"], color=BLUE)
for y, v in enumerate(lg["Rows"]):
    ax.text(v + 1, y, str(v), va="center", fontsize=9)
ax.set_xlabel("Rows affected")
ax.set_title("Issues found, fixed or flagged", loc="left", fontweight="bold")
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout(); fig.savefig(OUT / "chart_issues.png", dpi=200); plt.close(fig)

fig, ax = plt.subplots(figsize=(6.6, 2.9))
labels = list(before) + ["Sales linked to one farmer"]
b = [before[k] * 100 for k in before] + [linked_before * 100]
a = [after[k] * 100 for k in after] + [linked_after * 100]
x = np.arange(len(labels)); w = 0.38
ax.bar(x - w / 2, b, w, label="Before", color=GREY)
ax.bar(x + w / 2, a, w, label="After", color=BLUE)
for xi, (bv, av) in enumerate(zip(b, a)):
    ax.text(xi - w / 2, bv + 1, f"{bv:.0f}%", ha="center", fontsize=8.5)
    ax.text(xi + w / 2, av + 1, f"{av:.0f}%", ha="center", fontsize=8.5)
ax.set_xticks(x, labels); ax.set_ylim(0, 125); ax.set_ylabel("% of records")
ax.set_title("Data quality before and after cleaning", loc="left", fontweight="bold")
ax.legend(frameon=False, loc="upper right", ncols=2)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout(); fig.savefig(OUT / "chart_quality.png", dpi=200); plt.close(fig)

# indicator on clean data: active farmers (a sale in the last 90 days) by county
cut = (AS_OF - timedelta(days=90)).isoformat()
active_ids = set(s2.loc[(s2["sale_date"] >= cut) & s2["fid"].isin(clean["farmer_id"]), "fid"])
by_county = (clean.assign(active=clean["farmer_id"].isin(active_ids))
             .groupby(clean["county"].fillna("County missing"))
             .agg(registered=("farmer_id", "count"), active=("active", "sum")))
by_county["rate"] = by_county["active"] / by_county["registered"]
by_county = by_county.sort_values("rate")
fig, ax = plt.subplots(figsize=(6.6, 2.8))
ax.barh(by_county.index, by_county["rate"] * 100, color=[GREY if i == "County missing" else BLUE for i in by_county.index])
for y, (r, n) in enumerate(zip(by_county["rate"], by_county["registered"])):
    ax.text(r * 100 + 0.8, y, f"{r * 100:.0f}%  (n={n})", va="center", fontsize=8.5)
ax.set_xlabel("% of registered farmers with a sale in the last 90 days")
ax.set_xlim(0, max(by_county["rate"]) * 100 + 18)
ax.set_title("Indicator on clean data: active farmers by county", loc="left", fontweight="bold")
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout(); fig.savefig(OUT / "chart_indicator.png", dpi=200); plt.close(fig)

# ---------------------------------------------------------------- facts for the write-up
facts = dict(
    raw_rows=len(raw), clean_rows=len(clean), sales=len(sales), county_before=county_labels_before,
    county_after=county_labels_after, linked_before=linked_before, linked_after=linked_after,
    before=before, after=after, missing=missing, orphans=len(orphans), early=len(early_sales),
    merged=len(id_map), active_total=len(active_ids), top=by_county.drop("County missing", errors="ignore").iloc[-1],
    low=by_county.drop("County missing", errors="ignore").iloc[0],
)
snippets = {name: inspect.getsource(fn) for name, fn in
            [("standardise_phone", standardise_phone), ("parse_date", parse_date),
             ("resolve_conflicts", resolve_conflicts), ("merge_reregistrations", merge_reregistrations)]}
import json
(OUT / "facts.json").write_text(json.dumps(
    {k: (v if not isinstance(v, pd.Series) else {"county": v.name, **{kk: float(vv) for kk, vv in v.items()}})
     for k, v in facts.items()}, indent=2, default=float), encoding="utf-8")
(OUT / "snippets.json").write_text(json.dumps({**snippets, "SQL_LATEST": SQL_LATEST, "SQL_LINK": SQL_LINK}, indent=2),
                                   encoding="utf-8")
print(log_df.to_string(index=False))
print(json.dumps({k: v for k, v in json.loads((OUT / "facts.json").read_text()).items()}, indent=1))
