"""Klien IMF PortWatch: jumlah kapal yang transit per hari di selat-selat strategis.

PortWatch (IMF dan University of Oxford) menghitung transit harian dari data AIS satelit, sehingga
cakupannya merata di tengah laut, tidak bergantung pada penerima darat seperti aliran live.
Data dibuka lewat ArcGIS REST API tanpa kunci. Server kadang menjawab "Invalid URL" secara acak
(beberapa node di belakang load balancer gagal), sehingga setiap permintaan diulang beberapa kali.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

import pandas as pd

URL_HARIAN = ("https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/"
              "Daily_Chokepoints_Data/FeatureServer/0/query")
URL_CHOKEPOINT = ("https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/"
                  "PortWatch_chokepoints_database/FeatureServer/0/query")

# Selat di perairan Indonesia (empat di antaranya jalur ALKI) dan beberapa pembanding dunia.
SELAT: dict[str, dict] = {
    "chokepoint5": {"nama": "Selat Malaka", "grup": "Indonesia", "alki": "Selat internasional"},
    "chokepoint19": {"nama": "Selat Sunda", "grup": "Indonesia", "alki": "ALKI I"},
    "chokepoint15": {"nama": "Selat Lombok", "grup": "Indonesia", "alki": "ALKI II"},
    "chokepoint20": {"nama": "Selat Makassar", "grup": "Indonesia", "alki": "ALKI II"},
    "chokepoint16": {"nama": "Selat Ombai", "grup": "Indonesia", "alki": "ALKI III"},
    "chokepoint6": {"nama": "Selat Hormuz", "grup": "Pembanding", "alki": "-"},
    "chokepoint1": {"nama": "Terusan Suez", "grup": "Pembanding", "alki": "-"},
    "chokepoint11": {"nama": "Selat Taiwan", "grup": "Pembanding", "alki": "-"},
}

KOLOM_JENIS = {
    "n_tanker": "Tanker",
    "n_container": "Kontainer",
    "n_dry_bulk": "Curah kering",
    "n_general_cargo": "Kargo umum",
    "n_roro": "Ro-Ro",
}
KOLOM = ["tanggal", "portid", "selat", *KOLOM_JENIS, "n_total", "capacity", "capacity_tanker"]


class PortWatchError(RuntimeError):
    """Gagal mengambil data PortWatch setelah beberapa kali percobaan."""


def _minta(url: str, params: dict, percobaan: int = 30, jeda: float = 1.0) -> dict:
    alamat = url + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    terakhir = ""
    for _ in range(percobaan):
        try:
            with urllib.request.urlopen(alamat, timeout=40) as r:
                data = json.load(r)
            if "error" not in data:
                return data
            terakhir = str(data["error"].get("message"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            terakhir = f"{type(exc).__name__}: {exc}"
        time.sleep(jeda)
    raise PortWatchError(f"PortWatch tidak menjawab setelah {percobaan} percobaan ({terakhir}).")


def ambil_halaman(portid: str, offset: int, ukuran: int = 1000, percobaan: int = 30) -> dict:
    """Satu halaman baris harian untuk satu selat."""
    kolom = ",".join(["date", "portid", "portname", *KOLOM_JENIS, "n_total", "capacity", "capacity_tanker"])
    return _minta(URL_HARIAN, {
        "where": f"portid='{portid}'", "outFields": kolom, "resultOffset": offset,
        "resultRecordCount": ukuran, "returnGeometry": "false", "f": "json",
    }, percobaan=percobaan)


def ambil_harian(portids=None, sejak: str = "2019-01-01", ukuran_halaman: int = 1000, putaran: int = 6) -> pd.DataFrame:
    """Seluruh baris harian untuk selat terpilih sejak tanggal tertentu.

    Klausa ``where`` sengaja ditulis tanpa spasi (``portid='chokepoint5'``) dan tanpa ``orderByFields``:
    permintaan seperti itu lebih jarang ditolak server. Server tetap kadang menolak beruntun, sehingga
    halaman yang gagal dicoba lagi pada putaran berikutnya (sampai ``putaran`` kali) tanpa mengulang
    halaman yang sudah berhasil. Pengurutan dan filter tanggal dilakukan setelah data diterima.
    """
    halaman: dict[tuple[str, int], list] = {}
    antre = [(p, 0) for p in list(portids or SELAT)]
    for _ in range(putaran):
        gagal = []
        while antre:
            portid, offset = antre.pop(0)
            try:
                data = ambil_halaman(portid, offset, ukuran_halaman, percobaan=10)
            except PortWatchError:
                gagal.append((portid, offset))
                continue
            fitur = data.get("features", [])
            halaman[(portid, offset)] = [f["attributes"] for f in fitur]
            if fitur and data.get("exceededTransferLimit"):
                antre.append((portid, offset + len(fitur)))
        if not gagal:
            break
        antre = gagal
        time.sleep(10)
    if antre:
        raise PortWatchError(f"{len(antre)} halaman PortWatch tetap gagal: {antre[:4]}")
    baris = [b for isi in halaman.values() for b in isi]
    df = rapikan(pd.DataFrame(baris))
    return df[df["tanggal"] >= pd.Timestamp(sejak)].reset_index(drop=True)


def rapikan(df: pd.DataFrame) -> pd.DataFrame:
    """Nama kolom Indonesia, tanggal sebagai datetime, nama selat dari kamus ``SELAT``."""
    if df.empty:
        return pd.DataFrame(columns=KOLOM)
    d = df.rename(columns={"date": "tanggal"}).copy()
    d["tanggal"] = pd.to_datetime(d["tanggal"])
    d["selat"] = d["portid"].map(lambda p: SELAT.get(p, {}).get("nama")).fillna(d.get("portname"))
    for k in [*KOLOM_JENIS, "n_total", "capacity", "capacity_tanker"]:
        d[k] = pd.to_numeric(d[k], errors="coerce")
    return d[KOLOM].sort_values(["tanggal", "portid"]).drop_duplicates(["tanggal", "portid"]).reset_index(drop=True)


def ambil_ringkasan_tahunan() -> pd.DataFrame:
    """Ringkasan setahun per chokepoint dari basis data PortWatch (28 selat dunia)."""
    data = _minta(URL_CHOKEPOINT, {"where": "1=1", "outFields": "*", "returnGeometry": "false",
                                   "resultRecordCount": 100, "f": "json"})
    df = pd.DataFrame([f["attributes"] for f in data.get("features", [])])
    kolom = ["portid", "portname", "lat", "lon", "vessel_count_total", "vessel_count_tanker", "vessel_count_container",
             "vessel_count_dry_bulk", "vessel_count_general_cargo", "vessel_count_RoRo", "industry_top1"]
    return df[[k for k in kolom if k in df.columns]]


# ------------------------------------------------------------------ analisis murni
def tren(df: pd.DataFrame, portid: str, jendela: int = 30) -> pd.DataFrame:
    """Deret harian satu selat dengan rata-rata bergerak ``jendela`` hari."""
    d = df[df["portid"] == portid].sort_values("tanggal").copy()
    d["rata_bergerak"] = d["n_total"].rolling(jendela, min_periods=max(1, jendela // 2)).mean()
    return d


def per_tahun(df: pd.DataFrame) -> pd.DataFrame:
    """Rata-rata transit per hari menurut selat dan tahun (tahun berjalan ikut, ditandai jumlah hari)."""
    if df.empty:
        return pd.DataFrame(columns=["selat", "tahun", "rata_harian", "hari"])
    d = df.assign(tahun=df["tanggal"].dt.year)
    g = d.groupby(["selat", "tahun"]).agg(rata_harian=("n_total", "mean"), hari=("n_total", "size")).reset_index()
    g["rata_harian"] = g["rata_harian"].round(1)
    return g


def komposisi(df: pd.DataFrame, portid: str, hari_terakhir: int = 365) -> pd.DataFrame:
    """Porsi jenis kapal di satu selat selama N hari terakhir dalam data."""
    d = df[df["portid"] == portid]
    if d.empty:
        return pd.DataFrame(columns=["jenis", "kapal", "persen"])
    batas = d["tanggal"].max() - pd.Timedelta(days=hari_terakhir - 1)
    d = d[d["tanggal"] >= batas]
    total = d[list(KOLOM_JENIS)].sum()
    hasil = pd.DataFrame({"jenis": [KOLOM_JENIS[k] for k in total.index], "kapal": total.values.astype(int)})
    hasil["persen"] = (100 * hasil["kapal"] / max(int(hasil["kapal"].sum()), 1)).round(1)
    return hasil.sort_values("kapal", ascending=False).reset_index(drop=True)


def bandingkan(df: pd.DataFrame, hari_terakhir: int = 365) -> pd.DataFrame:
    """Rata-rata transit harian dan porsi tanker setiap selat selama N hari terakhir."""
    if df.empty:
        return pd.DataFrame(columns=["portid", "selat", "rata_harian", "tanker_harian", "persen_tanker", "grup", "alki"])
    batas = df["tanggal"].max() - pd.Timedelta(days=hari_terakhir - 1)
    d = df[df["tanggal"] >= batas]
    g = d.groupby(["portid", "selat"]).agg(rata_harian=("n_total", "mean"), tanker_harian=("n_tanker", "mean")).reset_index()
    g["persen_tanker"] = (100 * g["tanker_harian"] / g["rata_harian"]).round(1)
    g["rata_harian"] = g["rata_harian"].round(1)
    g["tanker_harian"] = g["tanker_harian"].round(1)
    g["grup"] = g["portid"].map(lambda p: SELAT.get(p, {}).get("grup", "-"))
    g["alki"] = g["portid"].map(lambda p: SELAT.get(p, {}).get("alki", "-"))
    return g.sort_values("rata_harian", ascending=False).reset_index(drop=True)


def anomali(df: pd.DataFrame, portid: str, jendela: int = 28, ambang: float = 2.5) -> pd.DataFrame:
    """Hari yang jumlah transitnya menyimpang jauh dari kebiasaan (z-score terhadap 28 hari sebelumnya)."""
    d = df[df["portid"] == portid].sort_values("tanggal").copy()
    if len(d) < jendela + 1:
        return d.iloc[0:0].assign(z=pd.Series(dtype=float))
    acuan = d["n_total"].shift(1).rolling(jendela, min_periods=jendela)
    d["z"] = ((d["n_total"] - acuan.mean()) / acuan.std()).round(2)
    return d[d["z"].abs() >= ambang][["tanggal", "selat", "n_total", "n_tanker", "z"]].reset_index(drop=True)
