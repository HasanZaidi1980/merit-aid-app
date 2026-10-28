"""Generate small, realistic sample IPEDS files so the app runs without the real
dataset. Writes the 8 expected CSVs into ../data. Swap in real IPEDS files later.
"""
import os
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
N = 300
DATA = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(DATA, exist_ok=True)

unitids = np.arange(100000, 100000 + N)
names = [f"Sample College {i}" for i in range(N)]
states = rng.choice(["TX", "CA", "NY", "FL", "OH", "PA", "IL", "MA"], N)

tuition = rng.integers(8000, 60000, N)
room_board = rng.integers(9000, 18000, N)
books = rng.integers(800, 1600, N)
grant = (tuition * rng.uniform(0.1, 0.8, N)).astype(int)
net = (tuition + room_board + books - grant - rng.integers(0, 8000, N)).clip(2000, 64000)

control = rng.choice([1, 2], N)
pd.DataFrame({"UNITID": unitids, "INSTNM": names, "STABBR": states,
              "CONTROL": control, "ICLEVEL": 1, "HDEGOFR1": 4}
             ).to_csv(f"{DATA}/HD2022.csv", index=False)
# One SFA file, matching IPEDS. Net price splits across two mutually exclusive
# columns -- NPT442 for private institutions, NPIS442 for public (in-state) -- so
# the sample data exercises the coalescing in data.net_price() rather than hiding it.
is_public = control == 1
pd.DataFrame({"UNITID": unitids, "IGRNT_A": grant,
              "NPT442": np.where(is_public, np.nan, net),
              "NPIS442": np.where(is_public, net, np.nan)}
             ).to_csv(f"{DATA}/SFA2122.csv", index=False)
pd.DataFrame({"UNITID": unitids, "TUITION2": tuition,
              "CHG4AY3": room_board, "CHG5AY3": books}).to_csv(f"{DATA}/IC2022_AY.csv", index=False)
pd.DataFrame({"UNITID": unitids, "SATVR75": rng.integers(500, 750, N),
              "SATMT75": rng.integers(500, 780, N)}).to_csv(f"{DATA}/ADM2022.csv", index=False)
pd.DataFrame({"UNITID": unitids, "DVADM01": rng.integers(10, 95, N)}
             ).to_csv(f"{DATA}/DRVADM2022.csv", index=False)
pd.DataFrame({"UNITID": unitids, "GBA4RTT": rng.integers(20, 95, N)}
             ).to_csv(f"{DATA}/DRVGR2022.csv", index=False)

themes = ["leadership and service", "undergraduate research", "faith and community",
          "affordability and access", "innovation and technology", "the liberal arts"]
missions = [f"{names[i]} is dedicated to excellence in {rng.choice(themes)}, "
            f"preparing students for lives of purpose." for i in range(N)]
pd.DataFrame({"unitid": unitids, "mission": missions}
             ).to_csv(f"{DATA}/IC2022Mission.csv", index=False)

print(f"Wrote 7 sample files to {os.path.abspath(DATA)}")
