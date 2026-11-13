"""Merekam sampel offline dari aisstream.io ke data/sample/.

Contoh (10 menit, satu posisi per kapal per 60 detik):
    AISSTREAM_API_KEY=... python scripts/rekam_sampel.py --durasi 600 --interval 60

Hasil:
- data/sample/posisi.csv       satu baris = satu kapal pada satu "snapshot" (bucket waktu)
- data/sample/kapal_statis.csv satu baris = satu kapal (nama, tipe, tujuan, dimensi) yang sempat mengirim pesan statis
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import ais  # noqa: E402

DIR_SAMPEL = Path(__file__).resolve().parent.parent / "data" / "sample"


def rapikan_posisi(baris: list[dict]) -> pd.DataFrame:
    """Buang posisi di luar kotak Selat, urutkan per snapshot, dan bulatkan koordinat ke 5 desimal (±1 m).

    Rekaman tanpa satu pun posisi (kunci salah, server sepi) tetap menghasilkan tabel berkolom lengkap.
    """
    df = pd.DataFrame(baris, columns=None if baris else ais.KOLOM_POSISI)
    df = df[df["lat"].between(ais.BBOX_SELAT["lamin"], ais.BBOX_SELAT["lamax"])
            & df["lon"].between(ais.BBOX_SELAT["lomin"], ais.BBOX_SELAT["lomax"])]
    df = df.sort_values(["waktu_snapshot", "mmsi"])
    for k in ("lat", "lon"):
        df[k] = df[k].astype(float).round(5)
    return df.reset_index(drop=True)


def rekam(api_key: str, durasi: int, interval: int, keluaran: Path = DIR_SAMPEL) -> tuple[pd.DataFrame, pd.DataFrame]:
    from websockets.exceptions import WebSocketException
    from websockets.sync.client import connect

    keluaran.mkdir(parents=True, exist_ok=True)
    posisi: dict[tuple[str, int], dict] = {}   # (mmsi, bucket) -> posisi terakhir dalam bucket
    statis: dict[str, dict] = {}
    mulai = time.time()
    jumlah = 0
    while time.time() - mulai < durasi:
        try:
            with connect(ais.URL_STREAM, compression="deflate", open_timeout=15) as ws:
                ws.send(json.dumps(ais.pesan_langganan(api_key)))
                while time.time() - mulai < durasi:
                    try:
                        mentah = ws.recv(timeout=5)
                    except TimeoutError:
                        continue
                    pesan = json.loads(mentah)
                    if "error" in pesan and "MessageType" not in pesan:
                        raise SystemExit(f"aisstream.io menolak: {pesan['error']}")
                    hasil = ais.urai_pesan(pesan)
                    jumlah += 1
                    if hasil is None:
                        continue
                    jenis, baris = hasil
                    if jenis == "statis":
                        statis[baris["mmsi"]] = baris
                        continue
                    bucket = int((time.time() - mulai) // interval)
                    baris["waktu_snapshot"] = datetime.fromtimestamp(mulai + bucket * interval, tz=timezone.utc).replace(microsecond=0)
                    posisi[(baris["mmsi"], bucket)] = baris
                    if jumlah % 200 == 0:
                        print(f"  {jumlah:,} pesan, {len({k[0] for k in posisi})} kapal, {len(statis)} data statis", flush=True)
        except (WebSocketException, OSError) as exc:
            # Koneksi panjang kadang diputus server; sambung ulang dan lanjutkan rekaman.
            print(f"  koneksi terputus ({type(exc).__name__}), menyambung ulang...", flush=True)
            time.sleep(3)

    df_pos = rapikan_posisi(list(posisi.values()))
    df_stat = pd.DataFrame(list(statis.values()), columns=ais.KOLOM_STATIS)
    df_pos.to_csv(keluaran / "posisi.csv", index=False)
    df_stat.to_csv(keluaran / "kapal_statis.csv", index=False)
    print(f"Selesai: {jumlah:,} pesan, {len(df_pos):,} baris posisi, {df_pos['mmsi'].nunique()} kapal unik, "
          f"{len(df_stat)} kapal dengan data statis → {keluaran}")
    return df_pos, df_stat


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--durasi", type=int, default=600, help="lama mendengarkan, detik (default 600)")
    p.add_argument("--interval", type=int, default=60, help="lebar bucket snapshot, detik (default 60)")
    p.add_argument("--api-key", default=None, help="kunci aisstream.io (default: variabel AISSTREAM_API_KEY)")
    args = p.parse_args()
    kunci = args.api_key or ais.ambil_api_key()
    if not kunci:
        raise SystemExit("Isi --api-key atau variabel lingkungan AISSTREAM_API_KEY.")
    rekam(kunci, args.durasi, args.interval)
