import sys
from pathlib import Path

import pandas as pd
import pyodbc
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from etl_config import buat_mysql_engine, koneksi_sql_server

# koneksi mysql
mysql_engine = buat_mysql_engine()

# buat tabel di mysql
with mysql_engine.begin() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS barang_detail (
            id_barang_detail INT AUTO_INCREMENT PRIMARY KEY,
            kode_produk VARCHAR(50) NOT NULL,
            no_id VARCHAR(10) NOT NULL,
            satuan VARCHAR(20),
            harga_satuan DECIMAL(18,2),
            isi DECIMAL(18,2),
            UNIQUE KEY uq_barang_detail (kode_produk, no_id),
            FOREIGN KEY (kode_produk) REFERENCES barang(kode_produk)
        )
    """))

# koneksi sql server
conn_sqlserver = pyodbc.connect(koneksi_sql_server())

query_barang_dtl = """
    SELECT 
        cKodeBrg AS kode_produk,
        cNoid AS no_id,
        cSat AS satuan,
        nHarga AS harga_satuan,
        nIsi AS isi
    FROM dbGrosir.dbo.tbBarangDtl
"""

df_dtl = pd.read_sql(query_barang_dtl, conn_sqlserver)
conn_sqlserver.close()

# buang spasi berlebih
for kolom in ["kode_produk", "no_id", "satuan"]:
    df_dtl[kolom] = df_dtl[kolom].astype(str).str.strip()

# satuan kosong dijadikan NULL
df_dtl.loc[df_dtl["satuan"].isin(["", "None", "nan"]), "satuan"] = None

# kolom angka dipastikan berupa angka
for kolom in ["harga_satuan", "isi"]:
    df_dtl[kolom] = pd.to_numeric(df_dtl[kolom], errors="coerce")

# buang duplikat (kode_produk + no_id harus unik)
jumlah_duplikat = df_dtl.duplicated(subset=["kode_produk", "no_id"]).sum()
if jumlah_duplikat > 0:
    print(f"Peringatan: {jumlah_duplikat} baris duplikat (kode_produk + no_id) dibuang.")
df_dtl = df_dtl.drop_duplicates(subset=["kode_produk", "no_id"], keep="first")

# pisahkan baris yang kode_produk-nya TIDAK ada di tabel barang (karena ada FOREIGN KEY)
df_kode_valid = pd.read_sql("SELECT kode_produk FROM barang", mysql_engine)
kode_valid = set(df_kode_valid["kode_produk"])

mask_valid = df_dtl["kode_produk"].isin(kode_valid)
jumlah_dibuang = (~mask_valid).sum()
if jumlah_dibuang > 0:
    print(f"Peringatan: {jumlah_dibuang} baris dibuang karena kode_produk tidak ditemukan di tabel barang.")
    df_dtl[~mask_valid].to_csv("BarangDtl_KodeProduk_TidakDitemukan.csv", index=False, encoding="utf-8-sig")
df_dtl = df_dtl[mask_valid]

# simpan cadangan ke CSV
df_dtl.to_csv("Data_barang_detail.csv", index=False, encoding="utf-8-sig")

if not df_dtl.empty:
    # Replace atomically so a failed insert does not leave the table empty.
    with mysql_engine.begin() as conn:
        conn.execute(text("DELETE FROM barang_detail"))
        df_dtl.to_sql("barang_detail", conn, if_exists="append", index=False, chunksize=1000)
else:
    print("Tidak ada detail barang dari SQL Server; data sebelumnya dipertahankan.")

print(f"{len(df_dtl)} baris barang detail berhasil disimpan ke MySQL.")
