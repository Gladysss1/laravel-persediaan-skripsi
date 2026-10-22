import sys
from pathlib import Path

import pandas as pd
import pyodbc
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from etl_config import buat_mysql_engine, koneksi_sql_server

# koneksi mysql
mysql_engine = buat_mysql_engine()

# buat table di mysql
with mysql_engine.begin() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS supplier (
            kode_supplier VARCHAR(50) PRIMARY KEY,
            nama_supplier VARCHAR(150),
            alamat VARCHAR(255),
            kota VARCHAR(100),
            telepon VARCHAR(30)
        )
    """))

# data dari ms sql server 2000
conn = pyodbc.connect(koneksi_sql_server())

query_supplier = """
    SELECT 
        cKode AS kode_supplier,
        cNama AS nama_supplier,
        cAlamat1 AS alamat,
        cKota AS kota,
        ctelp AS telepon
    FROM tbSupplier
"""

df_supplier = pd.read_sql(query_supplier, conn)
conn.close()

# Rapikan teks tanpa mengubah nilai kosong menjadi string "nan".
for kolom in ["kode_supplier", "nama_supplier", "alamat", "kota", "telepon"]:
    df_supplier[kolom] = df_supplier[kolom].astype("string").str.strip()
    df_supplier.loc[df_supplier[kolom].isin(["", "None", "nan"]), kolom] = pd.NA

# buang kode_supplier duplikat (primary key tidak boleh kembar)
df_supplier = df_supplier.dropna(subset=["kode_supplier"]).drop_duplicates(subset="kode_supplier", keep="first")

# Simpan cadangan ke CSV (opsional, boleh dihapus kalau tidak perlu)
df_supplier.to_csv("Data_Supplier.csv", index=False, encoding="utf-8-sig")

if not df_supplier.empty:
    records = df_supplier.astype(object).where(df_supplier.notna(), None).to_dict("records")
    with mysql_engine.begin() as conn:
        for row in records:
            conn.execute(text("""
                INSERT INTO supplier (kode_supplier, nama_supplier, alamat, kota, telepon)
                VALUES (:kode_supplier, :nama_supplier, :alamat, :kota, :telepon)
                ON DUPLICATE KEY UPDATE
                    nama_supplier = VALUES(nama_supplier), alamat = VALUES(alamat),
                    kota = VALUES(kota), telepon = VALUES(telepon)
            """), row)

print(f"{len(df_supplier)} baris supplier berhasil disimpan ke MySQL.")
