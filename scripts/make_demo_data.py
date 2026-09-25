"""Generate a small SYNTHETIC LCA-like dataset (fake employers) for demos/tests.

Column names mimic the DOL LCA disclosure layout. Numbers are random, not real.
Run: python scripts/make_demo_data.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "data" / "demo"
EMPLOYERS = [
    ("Acme Analytics, Inc.", "AZ"),
    ("Blue River Logistics LLC", "TX"),
    ("Quantfield Capital L.P.", "NY"),
    ("Northstar Consulting Corp", "IL"),
    ("Desert Health System", "AZ"),
]
SOCS = [
    ("15-2031.00", "Operations Research Analysts"),
    ("15-2051.00", "Data Scientists"),
    ("13-2051.00", "Financial and Investment Analysts"),
    ("17-2112.00", "Industrial Engineers"),
    ("15-1252.00", "Software Developers"),
]


def make_year(fy: int, n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    emp = rng.integers(0, len(EMPLOYERS), n)
    soc = rng.integers(0, len(SOCS), n)
    wage = rng.normal(105_000, 20_000, n).round(-2)
    pw = (wage * rng.uniform(0.8, 1.0, n)).round(-2)
    df = pd.DataFrame(
        {
            "CASE_NUMBER": [f"I-200-{fy}-{i:05d}" for i in range(n)],
            "CASE_STATUS": rng.choice(
                ["Certified", "Certified - Withdrawn", "Denied", "Withdrawn"],
                n,
                p=[0.85, 0.07, 0.03, 0.05],
            ),
            "DECISION_DATE": pd.Timestamp(f"{fy - 1}-10-01")
            + pd.to_timedelta(rng.integers(0, 360, n), unit="D"),
            "VISA_CLASS": rng.choice(["H-1B", "E-3 Australian"], n, p=[0.95, 0.05]),
            "JOB_TITLE": [SOCS[s][1].rstrip("s") for s in soc],
            "SOC_CODE": [SOCS[s][0] for s in soc],
            "SOC_TITLE": [SOCS[s][1] for s in soc],
            "FULL_TIME_POSITION": "Y",
            "TOTAL_WORKER_POSITIONS": rng.choice([1, 1, 1, 2], n),
            "NEW_EMPLOYMENT": rng.choice([0, 1], n),
            "CHANGE_EMPLOYER": rng.choice([0, 0, 1], n),
            "EMPLOYER_NAME": [EMPLOYERS[e][0] for e in emp],
            "EMPLOYER_FEIN": [f"00-00000{e:02d}" for e in emp],
            "EMPLOYER_STATE": [EMPLOYERS[e][1] for e in emp],
            "WORKSITE_CITY": "Demo City",
            "WORKSITE_STATE": [EMPLOYERS[e][1] for e in emp],
            "WAGE_RATE_OF_PAY_FROM": wage,
            "WAGE_UNIT_OF_PAY": "Year",
            "PREVAILING_WAGE": pw,
            "PW_UNIT_OF_PAY": "Year",
            "PW_WAGE_LEVEL": rng.choice(["I", "II", "III", "IV", None], n),
            "H-1B_DEPENDENT": "N",
            "WILLFUL_VIOLATOR": "N",
        }
    )
    # Edge cases the cleaner must handle:
    df.loc[0, ["WAGE_RATE_OF_PAY_FROM", "WAGE_UNIT_OF_PAY"]] = [50.0, "Hour"]  # hourly
    df.loc[1, "WAGE_RATE_OF_PAY_FROM"] = 9_000_000  # outlier
    dup = df.iloc[[2]].copy()
    dup["DECISION_DATE"] = dup["DECISION_DATE"] + pd.Timedelta(days=5)
    return pd.concat([df, dup], ignore_index=True)  # duplicate case number


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for fy, seed in [(2024, 1), (2025, 2)]:
        path = OUT / f"lca_demo_FY{fy}.csv"
        make_year(fy, 200, seed).to_csv(path, index=False)
        print("wrote", path)
