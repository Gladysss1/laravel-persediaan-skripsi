import sys
from pathlib import Path

import pandas as pd
import pyodbc
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from etl_config import buat_mysql_engine, koneksi_sql_server

# koneksi mysql
mysql_engine = buat_mysql_engine()

tgl_mulai = "2025-07-01"
tgl_akhir = "2026-08-01"   # eksklusif: yang diambil sampai 31 Juli 2026


def susun_pasangan(df, kode_produk_valid, kode_supplier_valid):
    """Rapikan data pembelian menjadi pasangan unik (kode_produk, kode_supplier).

    Mengembalikan (pasangan_valid, pasangan_dibuang). Pasangan dibuang kalau kode kosong,
    produknya tidak ada di tabel barang, atau suppliernya tidak ada di tabel supplier
    (keduanya FOREIGN KEY)."""
    df = df.copy()
    for kolom in ["kode_produk", "kode_supplier"]:
        df[kolom] = df[kolom].astype("string").str.strip()
        df.loc[df[kolom] == "", kolom] = pd.NA

    df = df.drop_duplicates(subset=["kode_produk", "kode_supplier"]).reset_index(drop=True)

    alasan = pd.Series("", index=df.index, dtype="object")
    alasan[df["kode_produk"].isna() | df["kode_supplier"].isna()] = "kode produk/supplier kosong"
    alasan[(alasan == "") & ~df["kode_produk"].isin(kode_produk_valid)] = "produk tidak ada di tabel barang"
    alasan[(alasan == "") & ~df["kode_supplier"].isin(kode_supplier_valid)] = "supplier tidak ada di tabel supplier"

    valid = df[alasan == ""].copy()
    dibuang = df[alasan != ""].copy()
    dibuang["alasan"] = alasan[alasan != ""]
    return valid, dibuang


if __name__ == "__main__":
    # ---------- 1. Siapkan tabel di MySQL ----------
    with mysql_engine.begin() as conn:
        # kode_supplier harus FOREIGN KEY dari supplier.kode_supplier,
        # jadi tabel supplier harus sudah ada dan kode_supplier-nya PRIMARY KEY / UNIQUE
        ada_kolom = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = 'supplier' "
            "AND column_name = 'kode_supplier'"
        )).scalar()
        if not ada_kolom:
            raise ValueError(
                "Tabel supplier atau kolom kode_supplier tidak ditemukan. "
                "Jalankan supplier.py dulu, atau cek nama kolomnya dengan: SHOW CREATE TABLE supplier;"
            )
        kode_supplier_unik = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.statistics "
            "WHERE table_schema = DATABASE() AND table_name = 'supplier' "
            "AND column_name = 'kode_supplier' AND seq_in_index = 1 AND non_unique = 0"
        )).scalar()
        if not kode_supplier_unik:
            raise ValueError(
                "supplier.kode_supplier belum berstatus PRIMARY KEY atau UNIQUE, jadi belum bisa "
                "dijadikan FOREIGN KEY. Jalankan di MySQL: "
                "ALTER TABLE supplier ADD UNIQUE (kode_supplier);"
            )

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS produk_supplier (
                id_produk_supplier INT AUTO_INCREMENT PRIMARY KEY,
                kode_produk VARCHAR(50) NOT NULL,
                kode_supplier VARCHAR(50) NOT NULL,
                lead_time INT NULL,
                UNIQUE KEY uq_produk_supplier (kode_produk, kode_supplier),
                FOREIGN KEY (kode_produk) REFERENCES barang(kode_produk),
                FOREIGN KEY (kode_supplier) REFERENCES supplier(kode_supplier)
            )
        """))

        # daftar produk dan supplier yang sah (untuk FOREIGN KEY)
        kode_supplier_valid = {
            str(r[0]).strip() for r in conn.execute(text("SELECT kode_supplier FROM supplier"))
        }
        kode_produk_valid = {
            str(r[0]).strip() for r in conn.execute(text("SELECT kode_produk FROM barang"))
        }

    # ---------- 2. Ambil data pembelian dari SQL Server ----------
    conn_sqlserver = pyodbc.connect(koneksi_sql_server())

    # hanya kode produk dan kode supplier; tanggal dipakai untuk membatasi periode
    query_pembelian = """
        SELECT DISTINCT
            d.cKodeBrg AS kode_produk,
            h.cKode AS kode_supplier
        FROM dbGrosir.dbo.tbBeli h
        INNER JOIN dbGrosir.dbo.tbBeliDtl d ON h.cNoBeli = d.cNoBeli
        WHERE
            h.dtanggal >= ?
            AND h.dtanggal < ?
            AND h.dtanggal NOT LIKE '%/%'
    """
    df_pembelian = pd.read_sql(query_pembelian, conn_sqlserver, params=(tgl_mulai, tgl_akhir))
    conn_sqlserver.close()

    # ---------- 3. Rapikan: pasangan unik dan sah ----------
    df_pasangan, df_dibuang = susun_pasangan(df_pembelian, kode_produk_valid, kode_supplier_valid)

    if len(df_dibuang) > 0:
        print(f"Peringatan: {len(df_dibuang)} pasangan dibuang:")
        print(df_dibuang["alasan"].value_counts().to_string())
        df_dibuang.to_csv("ProdukSupplier_Dibuang.csv", index=False, encoding="utf-8-sig")

    if df_pasangan.empty:
        raise ValueError("Tidak ada pasangan produk-supplier yang valid untuk disimpan.")

    df_pasangan.to_csv("Data_Produk_Supplier.csv", index=False, encoding="utf-8-sig")

    # ---------- 4. Pastikan relasi supplier tersedia ----------
    with mysql_engine.begin() as conn:
        sudah_fk = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.referential_constraints "
            "WHERE constraint_schema = DATABASE() AND table_name = 'produk_supplier' "
            "AND referenced_table_name = 'supplier'"
        )).scalar()
    if not sudah_fk:
        try:
            with mysql_engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE produk_supplier ADD CONSTRAINT fk_produk_supplier_supplier "
                    "FOREIGN KEY (kode_supplier) REFERENCES supplier(kode_supplier)"
                ))
        except Exception as e:
            raise RuntimeError(
                "FOREIGN KEY produk_supplier.kode_supplier -> supplier.kode_supplier gagal dibuat. "
                "Biasanya karena tipe atau collation kedua kolom berbeda. Cek dengan: "
                "SHOW CREATE TABLE supplier; lalu samakan tipe kolom kode_supplier."
            ) from e

    # Replace atomically; ON DELETE SET NULL protects ROP references if insertion fails.
    with mysql_engine.begin() as conn:
        conn.execute(text("DELETE FROM produk_supplier"))
        df_pasangan[["kode_produk", "kode_supplier"]].to_sql(
            "produk_supplier", conn, if_exists="append", index=False, chunksize=1000
        )

    jumlah_produk = df_pasangan["kode_produk"].nunique()
    jumlah_supplier = df_pasangan["kode_supplier"].nunique()
    produk_banyak = (df_pasangan.groupby("kode_produk")["kode_supplier"].nunique() > 1).sum()
    print(f"{len(df_pasangan)} pasangan produk-supplier berhasil disimpan ke MySQL.")
    print(f"Produk: {jumlah_produk}, supplier: {jumlah_supplier}, "
          f"produk dengan lebih dari 1 supplier: {produk_banyak}")
