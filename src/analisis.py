"""Analisis murni (pandas/numpy) atas tabel kapal: bendera, kategori, pelabuhan terdekat, grid, ringkasan."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from src import mmsi as km
from src.ais import BBOX_SELAT

R_BUMI_KM = 6371.0
KNOT_KE_KMH = 1.852

# Ambang kecepatan (knot) untuk fase pelayaran.
AMBANG_DIAM = 0.5
AMBANG_LAMBAT = 5.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Jarak lingkaran besar antara dua titik, dalam km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_BUMI_KM * math.asin(math.sqrt(a))


def haversine_vektor(lat: np.ndarray, lon: np.ndarray, lat0: float, lon0: float) -> np.ndarray:
    """Versi numpy: jarak banyak titik ke satu titik acuan, dalam km."""
    p1 = np.radians(np.asarray(lat, dtype=float))
    p2 = math.radians(lat0)
    dp = p2 - p1
    dl = np.radians(lon0 - np.asarray(lon, dtype=float))
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * math.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R_BUMI_KM * np.arcsin(np.sqrt(a))


def fase_pelayaran(sog_knot, status_kode=None) -> str:
    """Fase dari kecepatan (SOG) dan, bila ada, status navigasi yang dilaporkan kapal."""
    if status_kode is not None and status_kode == status_kode:
        try:
            s = int(status_kode)
        except (TypeError, ValueError):
            s = 15
        if s == 1:
            return "Berlabuh jangkar"
        if s == 5:
            return "Tertambat"
        if s == 7:
            return "Menangkap ikan"
    if sog_knot is None or sog_knot != sog_knot:
        return "Tidak diketahui"
    if sog_knot < AMBANG_DIAM:
        return "Diam"
    if sog_knot < AMBANG_LAMBAT:
        return "Lambat"
    return "Berlayar"


def pelabuhan_terdekat(df: pd.DataFrame, pelabuhan: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Nama pelabuhan terdekat dan jaraknya (km) untuk setiap baris kapal."""
    if df.empty or pelabuhan is None or pelabuhan.empty:
        kosong = pd.Series([None] * len(df), index=df.index, dtype=object)
        return kosong, pd.Series([np.nan] * len(df), index=df.index, dtype=float)
    hanya_pelabuhan = pelabuhan[pelabuhan["jenis"] == "pelabuhan"] if "jenis" in pelabuhan else pelabuhan
    if hanya_pelabuhan.empty:
        hanya_pelabuhan = pelabuhan
    jarak = np.column_stack([
        haversine_vektor(df["lat"].to_numpy(), df["lon"].to_numpy(), float(p["lat"]), float(p["lon"]))
        for _, p in hanya_pelabuhan.iterrows()
    ])
    idx = jarak.argmin(axis=1)
    nama = hanya_pelabuhan["nama"].to_numpy()[idx]
    return pd.Series(nama, index=df.index), pd.Series(jarak[np.arange(len(df)), idx], index=df.index).round(1)


def perkaya(df: pd.DataFrame, pelabuhan: pd.DataFrame | None = None) -> pd.DataFrame:
    """Menambah kolom turunan: bendera, kategori tipe, nama tipe, status, fase, km/jam, pelabuhan terdekat."""
    d = df.copy()
    if d.empty:
        for k in ("bendera", "kategori", "tipe", "status_nav", "fase", "kecepatan_kmh", "arah",
                  "pelabuhan_terdekat", "jarak_pelabuhan_km", "label"):
            d[k] = pd.Series(dtype=object)
        return d
    d["mmsi"] = d["mmsi"].astype(str)
    d["bendera"] = d["mmsi"].map(km.negara_bendera)
    d["jenis_mmsi"] = d["mmsi"].map(km.jenis_mmsi)
    d["kategori"] = d["tipe_kode"].map(km.kategori_tipe) if "tipe_kode" in d else km.TIDAK_DIKETAHUI
    d["tipe"] = d["tipe_kode"].map(km.nama_tipe) if "tipe_kode" in d else km.TIDAK_DIKETAHUI
    d["status_nav"] = d["status_nav_kode"].map(km.status_navigasi) if "status_nav_kode" in d else km.STATUS_NAVIGASI[15]
    d["fase"] = [fase_pelayaran(s, k) for s, k in zip(d["sog_knot"], d.get("status_nav_kode", pd.Series([None] * len(d))))]
    d["kecepatan_kmh"] = (pd.to_numeric(d["sog_knot"], errors="coerce") * KNOT_KE_KMH).round(1)
    # Arah ikon: COG (arah gerak) lebih dipercaya saat kapal bergerak; heading saat diam.
    cog = pd.to_numeric(d["cog"], errors="coerce")
    hdg = pd.to_numeric(d["heading"], errors="coerce")
    bergerak = pd.to_numeric(d["sog_knot"], errors="coerce").fillna(0) >= AMBANG_DIAM
    d["arah"] = np.where(bergerak & cog.notna(), cog, hdg.where(hdg.notna(), cog))
    nama = d["nama"].fillna("").astype(str).str.strip()
    d["label"] = nama.where(nama != "", "MMSI " + d["mmsi"])
    if pelabuhan is not None and not pelabuhan.empty:
        d["pelabuhan_terdekat"], d["jarak_pelabuhan_km"] = pelabuhan_terdekat(d, pelabuhan)
    else:
        d["pelabuhan_terdekat"], d["jarak_pelabuhan_km"] = None, np.nan
    return d


def hanya_kapal(df: pd.DataFrame) -> pd.DataFrame:
    """Buang stasiun pantai, pelampung navigasi, dan pemancar darurat dari tabel."""
    if df.empty or "jenis_mmsi" not in df:
        return df
    return df[df["jenis_mmsi"] == "Kapal"]


def hitung_unik(df: pd.DataFrame, kolom: str, teratas: int | None = None) -> pd.DataFrame:
    """Kapal unik (MMSI) per kategori, diurutkan menurun, dengan persentase."""
    if df.empty or kolom not in df:
        return pd.DataFrame(columns=[kolom, "kapal", "persen"])
    g = df.groupby(kolom, dropna=False)["mmsi"].nunique().reset_index(name="kapal")
    g[kolom] = g[kolom].fillna(km.TIDAK_DIKETAHUI).astype(str)
    g = g.sort_values(["kapal", kolom], ascending=[False, True]).reset_index(drop=True)
    total = max(int(df["mmsi"].nunique()), 1)
    g["persen"] = (100 * g["kapal"] / total).round(1)
    return g.head(teratas) if teratas else g


def ringkasan(df: pd.DataFrame) -> dict:
    """Angka KPI untuk bagian atas halaman."""
    if df.empty:
        return {"total": 0, "indonesia": 0, "persen_indonesia": 0.0, "bendera_teratas": "-", "jumlah_bendera": 0,
                "tanker": 0, "kargo": 0, "bergerak": 0, "berlabuh": 0, "kategori_teratas": "-", "tanpa_tipe": 0}
    unik = df.drop_duplicates("mmsi")
    total = len(unik)
    indo = int((unik["bendera"] == "Indonesia").sum())
    bendera = hitung_unik(unik[unik["bendera"] != km.TIDAK_DIKETAHUI], "bendera", 1)
    kategori = hitung_unik(unik[unik["kategori"] != km.TIDAK_DIKETAHUI], "kategori", 1)
    return {
        "total": total,
        "indonesia": indo,
        "persen_indonesia": round(100 * indo / total, 1) if total else 0.0,
        "bendera_teratas": bendera["bendera"].iloc[0] if not bendera.empty else "-",
        "jumlah_bendera": int(unik.loc[unik["bendera"] != km.TIDAK_DIKETAHUI, "bendera"].nunique()),
        "tanker": int((unik["kategori"] == "Tanker").sum()),
        "kargo": int((unik["kategori"] == "Kargo").sum()),
        "bergerak": int(unik["fase"].isin(["Berlayar", "Lambat"]).sum()),
        "berlabuh": int(unik["fase"].isin(["Berlabuh jangkar", "Tertambat", "Diam"]).sum()),
        "kategori_teratas": kategori["kategori"].iloc[0] if not kategori.empty else "-",
        "tanpa_tipe": int((unik["kategori"] == km.TIDAK_DIKETAHUI).sum()),
    }


def grid_kepadatan(df: pd.DataFrame, ukuran_deg: float = 0.25) -> pd.DataFrame:
    """Membagi laut menjadi sel persegi dan menghitung posisi serta kapal unik per sel."""
    if df.empty:
        return pd.DataFrame(columns=["lat_tengah", "lon_tengah", "titik", "kapal"])
    g = df[["lat", "lon", "mmsi"]].dropna().copy()
    g["lat_sel"] = np.floor(g["lat"] / ukuran_deg)
    g["lon_sel"] = np.floor(g["lon"] / ukuran_deg)
    agg = g.groupby(["lat_sel", "lon_sel"]).agg(titik=("mmsi", "size"), kapal=("mmsi", "nunique")).reset_index()
    agg["lat_tengah"] = ((agg["lat_sel"] + 0.5) * ukuran_deg).round(4)
    agg["lon_tengah"] = ((agg["lon_sel"] + 0.5) * ukuran_deg).round(4)
    return agg.sort_values(["kapal", "titik"], ascending=False).reset_index(drop=True)[["lat_tengah", "lon_tengah", "titik", "kapal"]]


def label_lokasi(lat: float, lon: float, pelabuhan: pd.DataFrame, titik_kunci: pd.DataFrame | None = None) -> str:
    """Teks seperti 'Dekat Port Klang (18 km)' untuk sebuah koordinat."""
    acuan = pelabuhan[["nama", "lat", "lon"]]
    if titik_kunci is not None and not titik_kunci.empty:
        acuan = pd.concat([acuan, titik_kunci[["nama", "lat", "lon"]]], ignore_index=True)
    if acuan.empty:
        return f"{lat:.2f}, {lon:.2f}"
    jarak = haversine_vektor(acuan["lat"].to_numpy(), acuan["lon"].to_numpy(), lat, lon)
    i = int(jarak.argmin())
    return f"Dekat {acuan['nama'].iloc[i]} ({jarak[i]:.0f} km)"


def kapal_di_sekitar(df: pd.DataFrame, lat: float, lon: float, radius_km: float) -> pd.DataFrame:
    """Kapal unik dalam radius tertentu dari sebuah titik (misalnya pangkalan atau chokepoint)."""
    if df.empty:
        return df
    jarak = haversine_vektor(df["lat"].to_numpy(), df["lon"].to_numpy(), lat, lon)
    hasil = df.assign(jarak_km=np.round(jarak, 1))
    return hasil[hasil["jarak_km"] <= radius_km].sort_values("jarak_km").drop_duplicates("mmsi")


def sibuk_per_titik(df: pd.DataFrame, titik: pd.DataFrame, radius_km: float = 25.0) -> pd.DataFrame:
    """Jumlah kapal unik di sekitar setiap pelabuhan/titik kunci."""
    baris = []
    for _, t in titik.iterrows():
        sekitar = kapal_di_sekitar(df, float(t["lat"]), float(t["lon"]), radius_km)
        baris.append({"nama": t["nama"], "negara": t.get("negara", ""), "kapal": int(len(sekitar)),
                      "tanker": int((sekitar.get("kategori", pd.Series(dtype=object)) == "Tanker").sum()) if not sekitar.empty else 0})
    hasil = pd.DataFrame(baris, columns=["nama", "negara", "kapal", "tanker"])
    return hasil.sort_values("kapal", ascending=False).reset_index(drop=True)


def panjang_jejak_km(jejak: pd.DataFrame, teratas: int = 10) -> pd.DataFrame:
    """Total jarak yang ditempuh setiap kapal sepanjang rekaman (jumlah segmen antar snapshot)."""
    if jejak.empty or jejak["waktu_snapshot"].nunique() < 2:
        return pd.DataFrame(columns=["mmsi", "label", "kategori", "segmen", "km"])
    j = jejak.sort_values(["mmsi", "waktu_snapshot"])
    baris = []
    for mmsi, g in j.groupby("mmsi"):
        if len(g) < 2:
            continue
        lat, lon = g["lat"].to_numpy(), g["lon"].to_numpy()
        km_total = sum(haversine_km(lat[i], lon[i], lat[i + 1], lon[i + 1]) for i in range(len(g) - 1))
        baris.append({"mmsi": mmsi, "label": g["label"].iloc[-1], "kategori": g["kategori"].iloc[-1],
                      "segmen": len(g) - 1, "km": round(km_total, 1)})
    hasil = pd.DataFrame(baris, columns=["mmsi", "label", "kategori", "segmen", "km"])
    return hasil.sort_values("km", ascending=False).head(teratas).reset_index(drop=True)


def di_dalam_kotak(df: pd.DataFrame, bbox: dict = BBOX_SELAT) -> pd.DataFrame:
    """Buang posisi di luar kotak pantau (aisstream kadang meloloskan pesan di tepi)."""
    if df.empty:
        return df
    return df[df["lat"].between(bbox["lamin"], bbox["lamax"]) & df["lon"].between(bbox["lomin"], bbox["lomax"])]
