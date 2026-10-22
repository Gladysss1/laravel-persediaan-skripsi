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
# satuan1= dos, ikat.bal
# nisi= isi dari satuan 1, misal 1 dos 8 rtg
# satuan_2= isi dari 1 dos ada berbagai macam rtg, pak
# satuan_3= isi dari satuan_2 misal pcs
# nisi_2= isi dari rtg tersebut misal 10 pcs
with mysql_engine.begin() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS barang (
            kode_produk VARCHAR(50) PRIMARY KEY,
            nama_produk VARCHAR(150),
            satuan VARCHAR(20),
            satuan_2 VARCHAR(20),
            satuan_3 VARCHAR(20),
            nisi DECIMAL(18,2),
            nisi_2 DECIMAL(18,2)
        )
    """))

    
    kolom_baru = {
        "satuan_3": "VARCHAR(20)",
        "nisi": "DECIMAL(18,2)",
        "nisi_2": "DECIMAL(18,2)",
    }
    for nama_kolom, tipe in kolom_baru.items():
        ada = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = 'barang' "
            "AND column_name = :k"
        ), {"k": nama_kolom}).scalar()
        if not ada:
            conn.execute(text(f"ALTER TABLE barang ADD COLUMN {nama_kolom} {tipe}"))

# koneksi sql server
conn_sqlserver = pyodbc.connect(koneksi_sql_server())

query_barang = """
    SELECT 
        cKode AS kode_produk,
        cNama AS nama_produk,
        cSat1 AS satuan,
        cSat2 AS satuan_2,
        cSat3 AS satuan_3,
        nIsi AS nisi,
        nIsi2 AS nisi_2
    FROM tbBarang
"""

df_barang = pd.read_sql(query_barang, conn_sqlserver)
conn_sqlserver.close()

# buang spasi berlebih
for kolom in ["kode_produk", "nama_produk", "satuan", "satuan_2", "satuan_3"]:
    df_barang[kolom] = df_barang[kolom].str.strip()

# satuan yang kosong dijadikan NULL
for kolom in ["satuan", "satuan_2", "satuan_3"]:
    df_barang.loc[df_barang[kolom] == "", kolom] = None

# isi (nisi, nisi_2)  berupa angka
for kolom in ["nisi", "nisi_2"]:
    df_barang[kolom] = pd.to_numeric(df_barang[kolom], errors="coerce")

# isi nama_produk yang kosong dengan penanda
df_barang["nama_produk"] = df_barang["nama_produk"].fillna("TANPA NAMA")
df_barang.loc[df_barang["nama_produk"] == "", "nama_produk"] = "TANPA NAMA"

# buang kode_produk duplikat
df_barang = df_barang.drop_duplicates(subset="kode_produk", keep="first")

df_barang.to_csv("Data_barang.csv", index=False, encoding="utf-8-sig")

#None supaya tersimpan sebagai NULL di MySQL
records = df_barang.astype(object).where(df_barang.notna(), None).to_dict("records")

# upsert: tambah produk baru, perbarui produk lama.
# Tidak memakai DELETE karena barang dipakai FOREIGN KEY oleh stok, detail_penjualan, dll.
with mysql_engine.begin() as conn:
    conn.execute(text("""
        INSERT INTO barang
            (kode_produk, nama_produk, satuan, satuan_2, satuan_3, nisi, nisi_2)
        VALUES
            (:kode_produk, :nama_produk, :satuan, :satuan_2, :satuan_3, :nisi, :nisi_2)
        ON DUPLICATE KEY UPDATE
            nama_produk = VALUES(nama_produk),
            satuan      = VALUES(satuan),
            satuan_2    = VALUES(satuan_2),
            satuan_3    = VALUES(satuan_3),
            nisi        = VALUES(nisi),
            nisi_2      = VALUES(nisi_2)
    """), records)

print(f"{len(df_barang)} baris barang berhasil disimpan ke MySQL.")
