# Sumber dan keterbatasan data

## 1. Posisi kapal live: aisstream.io

| Hal | Keterangan |
|---|---|
| Sumber | [aisstream.io](https://aisstream.io), WebSocket `wss://stream.aisstream.io/v0/stream` |
| Dokumentasi | https://aisstream.io/documentation |
| Kotak batas | lintang -1,5° s.d. 7,5°; bujur 95,0° s.d. 105,5° (Sabang sampai pintu timur Selat Singapura) |
| Pesan yang dipakai | `PositionReport` (kelas A), `StandardClassBPositionReport` (kelas B), `ShipStaticData` (nama, tipe, tujuan, dimensi) |
| Akses | kunci API gratis (masuk dengan akun GitHub); satu kunci = satu koneksi pada satu waktu; penggunaan non-komersial |
| Cara ambil | tidak ada endpoint snapshot; aplikasi mendengarkan aliran selama 10–60 detik dan menyimpan posisi terakhir tiap MMSI (`src/ais.py`) |
| Kompresi | server mensyaratkan `permessage-deflate` agar seluruh pesan terkirim |

Nilai "tidak tersedia" menurut standar AIS dibuang di `urai_pesan`: SOG 102,3 knot, COG 360°, heading 511, lintang 91,
bujur 181. Nama dan tujuan dibersihkan dari karakter pengisi `@` dan spasi.

**Keterbatasan penting**

- **Cakupan bergantung pada penerima sukarelawan di darat.** Jangkauan AIS VHF sekitar 40–70 km dari antena. Selat
  Singapura, Johor, dan pantai barat Semenanjung Malaysia tercakup sangat baik; pantai timur Sumatera dan bagian utara
  selat lebih tipis. Area yang tampak kosong belum tentu kosong.
- **Hanya kapal yang memancarkan AIS yang terlihat.** AIS kelas A wajib untuk kapal niaga ≥ 300 GT dan kapal penumpang
  (SOLAS). Kapal kecil, sebagian kapal ikan, dan kapal perang umumnya tidak terlihat. Kapal yang mematikan AIS
  ("dark ships") tidak terdeteksi.
- **Tipe kapal dan tujuan diisi manual oleh operator kapal**, sehingga bisa salah, kosong, atau ejaannya beragam.
- **Data statis datang hanya tiap 6 menit.** Pada pendengaran 20 detik, sebagian kapal belum punya tipe/tujuan dan
  diberi label "Tidak diketahui". Aplikasi menyimpan data statis antar snapshot dalam satu sesi.
- **Kapal berlabuh melapor tiap 3 menit**, sehingga pada pendengaran singkat sebagian kapal berlabuh belum tampil.

## 1b. Transit harian: IMF PortWatch

| Hal | Keterangan |
|---|---|
| Sumber | [IMF PortWatch](https://portwatch.imf.org) (International Monetary Fund dan University of Oxford), layanan ArcGIS `Daily_Chokepoints_Data` dan `PortWatch_chokepoints_database` |
| Data dasar | AIS satelit dan darat yang diolah PortWatch menjadi jumlah kapal yang melintasi garis batas setiap chokepoint per hari, dipecah per jenis (tanker, kontainer, curah kering, kargo umum, Ro-Ro) beserta kapasitas (DWT) |
| Selat | Malaka, Sunda (ALKI I), Lombok dan Makassar (ALKI II), Ombai (ALKI III), serta Hormuz, Suez, Taiwan sebagai pembanding |
| Rentang | 1 Januari 2019 sampai data terakhir yang diterbitkan (biasanya tertinggal beberapa hari) |
| Akses | tanpa kunci; server kadang menolak permintaan secara acak ("Invalid URL"), sehingga `src/portwatch.py` mengulang setiap halaman yang gagal |
| Pembaruan | `scripts/perbarui_portwatch.py`, dijalankan otomatis setiap Senin oleh GitHub Actions |

**Keterbatasan:** hanya kapal niaga yang dikelompokkan PortWatch (kapal ikan, penumpang, dan kapal kecil tidak masuk
hitungan), transit dihitung saat kapal melintasi garis batas sehingga kapal yang berlabuh di dalam selat tidak terhitung,
dan angka beberapa hari terakhir dapat direvisi oleh PortWatch.

## 2. Sampel offline: `data/sample/`

| File | Isi |
|---|---|
| `posisi.csv` | satu baris = satu kapal pada satu snapshot (bucket waktu); kolom `waktu_snapshot` dalam UTC |
| `kapal_statis.csv` | satu baris = satu kapal yang sempat mengirim pesan statis selama perekaman |

Direkam dengan `scripts/rekam_sampel.py` (posisi terakhir tiap kapal per bucket 60 detik). Waktu perekaman tercantum
di README. Sampel adalah potret satu jam tertentu; komposisi bendera dan jenis kapal berubah dari jam ke jam.

## 3. Negara bendera: `src/mmsi.py`

Tiga digit pertama MMSI (Maritime Identification Digits) dialokasikan ITU per negara, lihat
[ITU-R M.585](https://www.itu.int/rec/R-REC-M.585) dan tabel MID publik ITU. Daftar di `MID_NEGARA` mencakup negara
Asia Tenggara, Asia Timur, Timur Tengah, bendera kemudahan utama, dan negara Eropa yang lazim terlihat; MID lain
menjadi "Tidak diketahui". Awalan khusus (`00` stasiun pantai, `99` alat bantu navigasi, `970` AIS-SART, dan
lain-lain) dikeluarkan dari hitungan kapal.

Catatan: bendera bukan kepemilikan. Panama, Liberia, dan Kepulauan Marshall adalah bendera kemudahan; pemilik kapalnya
bisa dari negara mana pun.

## 4. Tipe kapal dan status navigasi

Kode tipe 0–99 dan status navigasi 0–15 mengikuti [ITU-R M.1371](https://www.itu.int/rec/R-REC-M.1371) (pesan 5 dan
pesan 1/2/3). Pengelompokan di `KATEGORI_TIPE`: kargo 70–79, tanker 80–89, penumpang 60–69, nelayan 30, kecepatan
tinggi 40–49, militer 35, penegak hukum 55, SAR 51, kapal tunda/servis 31–34 dan 50–58, rekreasi 36–37.

## 5. Pelabuhan, pangkalan, titik kunci: `data/pelabuhan.csv`, `data/titik_kunci.csv`

Koordinat pelabuhan dari halaman Wikipedia masing-masing pelabuhan, dibulatkan 2 desimal (sekitar 1 km); cukup untuk
label "pelabuhan terdekat", tidak untuk navigasi. Pangkalan TNI AL (Lantamal I Belawan, Lantamal IV Batam, Koarmada I
Tanjung Pinang, Lanal Sabang, Dumai, Lhokseumawe, Tanjung Balai Karimun), Changi Naval Base, dan Pangkalan TLDM Lumut
dari Wikipedia. Titik kunci (One Fathom Bank, Selat Phillip, pintu utara dan timur) adalah titik acuan umum yang
dipilih sendiri untuk pantauan radius, bukan batas resmi.

## Disclaimer

Seluruh data berasal dari sumber publik dan disajikan untuk tujuan edukasi dan portofolio. Data ini **bukan** data
operasional pelayaran dan tidak boleh dipakai untuk navigasi, pengawasan, atau keputusan keselamatan. Proyek ini tidak
berafiliasi dengan aisstream.io, IMF, otoritas pelabuhan, TNI AL, Kementerian Perhubungan, maupun operator kapal mana pun.
