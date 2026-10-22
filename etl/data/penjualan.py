from datetime import date, timedelta
import sys
from pathlib import Path

import pandas as pd
import pyodbc
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from etl_config import buat_mysql_engine, koneksi_sql_server, rentang_analisis_default

# koneksi mysql
mysql_engine = buat_mysql_engine()

if len(sys.argv) not in (1, 3):
    raise SystemExit("Gunakan dua tanggal inklusif: penjualan.py YYYY-MM-DD YYYY-MM-DD")
awal_default, akhir_default = rentang_analisis_default()
# CLI end dates are inclusive. Internally the SQL range uses an exclusive end.
tgl_mulai = date.fromisoformat(sys.argv[1]) if len(sys.argv) == 3 else awal_default
tgl_akhir_inklusif = date.fromisoformat(sys.argv[2]) if len(sys.argv) == 3 else akhir_default
tgl_akhir = tgl_akhir_inklusif + timedelta(days=1)
if tgl_mulai >= tgl_akhir:
    raise SystemExit("Tanggal mulai harus sama dengan atau sebelum tanggal akhir.")

# buat tabel di mysql
with mysql_engine.begin() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS detail_penjualan (
            id_detail_jual INT AUTO_INCREMENT PRIMARY KEY,
            no_penjualan VARCHAR(50),
            tanggal DATE,
            nama_pelanggan VARCHAR(150),
            kota VARCHAR(100),
            kode_produk VARCHAR(50),
            nama_produk VARCHAR(150),
            jumlah DECIMAL(18,2),
            satuan VARCHAR(20),
            isi DECIMAL(18,2),
            total_qty DECIMAL(18,2),
            harga_satuan DECIMAL(18,2),
            subtotal DECIMAL(18,2),
            FOREIGN KEY (kode_produk) REFERENCES barang(kode_produk)
        )
    """))

    # kalau tabel lama sudah ada, tambahkan kolom baru yang belum ada
    #   jumlah    = nQty1   (qty dalam satuan transaksi, misalnya 3 BAL)
    #   isi       = nIsi    (isi per satuan, dalam satuan terkecil)
    #   total_qty = nTotQty (qty dalam satuan terkecil/pcs = jumlah x isi)
    kolom_baru = {
        "jumlah": "DECIMAL(18,2)",
        "isi": "DECIMAL(18,2)",
        "total_qty": "DECIMAL(18,2)",
    }
    for nama_kolom, tipe in kolom_baru.items():
        ada = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = 'detail_penjualan' "
            "AND column_name = :k"
        ), {"k": nama_kolom}).scalar()
        if not ada:
            conn.execute(text(f"ALTER TABLE detail_penjualan ADD COLUMN {nama_kolom} {tipe}"))

    # nama_produk di tabel lama hanya 50 karakter, dilebarkan supaya tidak terpotong
    conn.execute(text("ALTER TABLE detail_penjualan MODIFY nama_produk VARCHAR(150)"))

# data penjualan
conn_penjualan = pyodbc.connect(koneksi_sql_server())

query_penjualan = """
    SELECT 
        j.cNoJual AS no_penjualan,
        j.dtanggal AS tanggal,
        j.cNamaCust AS nama_pelanggan,
        j.cKota AS kota,
        d.cKodeBrg AS kode_produk,
        d.cNama AS nama_produk,
        d.nQty1 AS jumlah,
        d.cSat AS satuan,
        d.nIsi AS isi,
        d.nTotQty AS total_qty,
        d.nHarga AS harga_satuan,
        d.nSTotal AS subtotal
    FROM 
        dbGrosir.dbo.tbJual j
    INNER JOIN 
        dbGrosir.dbo.tbJualDtl d ON j.cNoJual = d.cNoJual
    WHERE 
        j.dtanggal >= ?
        AND j.dtanggal < ?
        AND j.dtanggal NOT LIKE '%/%'
    ORDER BY 
        j.dtanggal ASC
"""

# Driver ODBC "SQL Server" lama tidak mendukung binding objek datetime.date
# (HYC00 / SQLBindParameter). Kirim tanggal ISO sebagai VARCHAR; SQL Server
# mengonversinya saat membandingkan dengan kolom tanggal.
df_penjualan = pd.read_sql(
    query_penjualan,
    conn_penjualan,
    params=(tgl_mulai.isoformat(), tgl_akhir.isoformat()),
)
conn_penjualan.close()

# buang spasi berlebih
kolom_teks = ["no_penjualan", "nama_pelanggan", "kota", "kode_produk", "nama_produk", "satuan"]
for kolom in kolom_teks:
    df_penjualan[kolom] = df_penjualan[kolom].str.strip()

# tanggal dijadikan tipe date (kolom MySQL bertipe DATE, jam dibuang)
df_penjualan["tanggal"] = pd.to_datetime(df_penjualan["tanggal"], errors="coerce").dt.date

# kolom angka dipastikan berupa angka
for kolom in ["jumlah", "isi", "total_qty", "harga_satuan", "subtotal"]:
    df_penjualan[kolom] = pd.to_numeric(df_penjualan[kolom], errors="coerce")

# ambil daftar kode_produk yang sudah ada di tabel barang
df_kode_valid = pd.read_sql("SELECT kode_produk FROM barang", mysql_engine)
kode_valid = set(df_kode_valid["kode_produk"])

# pisahkan baris yang kode_produk-nya TIDAK ada di tabel barang
mask_valid = df_penjualan["kode_produk"].isin(kode_valid)
jumlah_dibuang = (~mask_valid).sum()
if jumlah_dibuang > 0:
    print(f"Peringatan: {jumlah_dibuang} baris dibuang karena kode_produk tidak ditemukan di tabel barang.")
    df_penjualan[~mask_valid].to_csv("Penjualan_KodeProduk_TidakDitemukan.csv", index=False, encoding="utf-8-sig")
df_penjualan = df_penjualan[mask_valid]
if df_penjualan.empty:
    raise ValueError(
        f"Tidak ada penjualan valid dari SQL Server pada {tgl_mulai} s/d {tgl_akhir_inklusif}. "
        "Data MySQL sebelumnya tidak diubah."
    )

# peringatan kalau ada nilai angka yang kosong/tidak terbaca
kosong = df_penjualan[["jumlah", "isi", "total_qty", "harga_satuan", "subtotal"]].isna().sum()
if kosong.any():
    print("Peringatan: ada nilai angka kosong/tidak terbaca:")
    print(kosong[kosong > 0])

# Simpan cadangan ke CSV (opsional, boleh dihapus kalau tidak perlu)
df_penjualan.to_csv("Data_Penjualan.csv", index=False, encoding="utf-8-sig")

# kosongkan tabel lalu isi ulang dalam SATU transaksi:
# kalau pengisian gagal, penghapusan dibatalkan sehingga data lama tidak hilang
with mysql_engine.begin() as conn:
    if len(sys.argv) > 2:
        conn.execute(text("DELETE FROM detail_penjualan WHERE tanggal >= :mulai AND tanggal < :akhir"),
                     {"mulai": tgl_mulai, "akhir": tgl_akhir})
    else:
        conn.execute(text("DELETE FROM detail_penjualan"))
    df_penjualan.to_sql(
        "detail_penjualan",
        conn,
        if_exists="append",
        index=False,
        chunksize=1000,
    )

print(f"{len(df_penjualan)} baris penjualan berhasil disimpan ke MySQL.")
print(f"Total qty (pcs)          : {df_penjualan['total_qty'].sum():,.0f}")
print(f"Total subtotal (nSTotal) : Rp {df_penjualan['subtotal'].sum():,.2f}")
