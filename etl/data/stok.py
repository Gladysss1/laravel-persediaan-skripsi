from datetime import date, timedelta
import sys
from pathlib import Path

import pandas as pd
import pyodbc
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from etl_config import buat_mysql_engine, koneksi_sql_server

# koneksi mysql
mysql_engine = buat_mysql_engine()

tgl_mulai = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date(2025, 7, 1)
tgl_akhir = date.fromisoformat(sys.argv[2]) + timedelta(days=1) if len(sys.argv) > 2 else date(2026, 8, 1)
if len(sys.argv) not in (1, 3):
    raise SystemExit("Gunakan dua tanggal inklusif: stok.py YYYY-MM-DD YYYY-MM-DD")
if tgl_mulai >= tgl_akhir:
    raise SystemExit("Tanggal mulai harus sama dengan atau sebelum tanggal akhir.")

# buat tabel di mysql
with mysql_engine.begin() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS stok (
            id_stok INT AUTO_INCREMENT PRIMARY KEY,
            no_transaksi VARCHAR(50),
            tanggal DATE,
            kode_produk VARCHAR(50),
            nama_produk VARCHAR(50),
            total_qty DECIMAL(18,2),
            total_qty_real DECIMAL(18,2),
            FOREIGN KEY (kode_produk) REFERENCES barang(kode_produk)
        )
    """))

# data stok
# ganti DATABASE di bawah kalau stok berada di database SQL Server yang berbeda
conn_stok = pyodbc.connect(koneksi_sql_server())

query_stok = """
    SELECT 
        cNomer AS no_transaksi,
        dTglVal AS tanggal,
        cKodebrg AS kode_produk,
        cNamaBrg AS nama_produk,
        nTotQty AS total_qty,
        nTotQtyReal AS total_qty_real
    FROM 
        dbGrosir.dbo.TbStock
    WHERE 
        dTglVal >= ?
        AND dTglVal < ?
    ORDER BY 
        dTglVal ASC
"""

# Driver ODBC "SQL Server" lama tidak mendukung binding objek datetime.date
# (HYC00 / SQLBindParameter). Kirim tanggal ISO sebagai VARCHAR; SQL Server
# mengonversinya saat membandingkan dengan kolom tanggal.
df_stok = pd.read_sql(
    query_stok,
    conn_stok,
    params=(tgl_mulai.isoformat(), tgl_akhir.isoformat()),
)
conn_stok.close()

# buang spasi berlebih
for kolom in ["no_transaksi", "kode_produk"]:
    df_stok[kolom] = df_stok[kolom].astype(str).str.strip()

# cek kode_produk yang valid di tabel barang (karena ada FOREIGN KEY)
df_kode_valid = pd.read_sql("SELECT kode_produk FROM barang", mysql_engine)
kode_valid = set(df_kode_valid["kode_produk"])
df_stok = df_stok[df_stok["kode_produk"].isin(kode_valid)].copy()


# csv
df_stok.to_csv("Data_Stok.csv", index=False, encoding="utf-8-sig")



with mysql_engine.begin() as conn:
    # Refresh only a non-empty slice so repeated imports do not double stock movements
    # and an empty source result cannot erase previously imported movements.
    if not df_stok.empty:
        conn.execute(text("DELETE FROM stok WHERE tanggal >= :mulai AND tanggal < :akhir"),
                     {"mulai": tgl_mulai, "akhir": tgl_akhir})
    df_stok.to_sql("stok", conn, if_exists="append", index=False, chunksize=1000)

print(f"{len(df_stok)} baris stok berhasil disimpan ke MySQL.")
if df_stok.empty:
    print("Tidak ada pergerakan stok valid pada rentang ini; data sebelumnya dipertahankan.")
