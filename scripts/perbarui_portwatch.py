"""Mengunduh ulang data transit harian IMF PortWatch ke data/portwatch_harian.csv.

    python scripts/perbarui_portwatch.py            # sejak 2019
    python scripts/perbarui_portwatch.py --sejak 2023-01-01
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import portwatch  # noqa: E402

DIR_DATA = Path(__file__).resolve().parent.parent / "data"

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sejak", default="2019-01-01")
    args = p.parse_args()
    df = portwatch.ambil_harian(sejak=args.sejak)
    df["tanggal"] = df["tanggal"].dt.strftime("%Y-%m-%d")
    df.to_csv(DIR_DATA / "portwatch_harian.csv", index=False)
    print(f"{len(df):,} baris, {df['selat'].nunique()} selat, {df['tanggal'].min()} s.d. {df['tanggal'].max()}")
    ring = portwatch.ambil_ringkasan_tahunan()
    ring.to_csv(DIR_DATA / "portwatch_chokepoint.csv", index=False)
    print(f"Ringkasan: {len(ring)} chokepoint")
