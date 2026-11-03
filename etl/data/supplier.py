import sys
from pathlib import Path

import pandas as pd
import pyodbc
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from etl_config import buat_mysql_engine, koneksi_sql_server


def rapikan_teks(kolom: pd.Series) -> pd.Series:
    """Trim teks dan ubah penanda kosong dari ODBC menjadi NULL pandas."""
    hasil = kolom.astype("string").str.strip()
    kosong = hasil.str.casefold().isin(["", "none", "nan", "null", "<na>"])
    return hasil.mask(kosong, pd.NA)


def main() -> None:
    mysql_engine = buat_mysql_engine()

    # Pastikan tabel tersedia, tetapi jangan hapus data supplier sebelumnya.
    with mysql_engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS supplier (
                kode_supplier VARCHAR(50) PRIMARY KEY,
                nama_supplier VARCHAR(150),
                alamat VARCHAR(255),
                kota VARCHAR(100),
                telepon VARCHAR(30)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """))

    koneksi = None
    try:
        koneksi = pyodbc.connect(koneksi_sql_server(), timeout=30)
        query_supplier = """
            SELECT
                cKode AS kode_supplier,
                cNama AS nama_supplier,
                cAlamat1 AS alamat,
                cKota AS kota,
                ctelp AS telepon
            FROM dbGrosir.dbo.tbSupplier
        """
        df_supplier = pd.read_sql(query_supplier, koneksi)
    finally:
        if koneksi is not None:
            koneksi.close()

    jumlah_sumber = len(df_supplier)

    # Rapikan kode dan kolom tampilan. Kolom lain yang kosong tetap boleh NULL.
    kolom_teks = ["kode_supplier", "nama_supplier", "alamat", "kota", "telepon"]
    for kolom in kolom_teks:
        df_supplier[kolom] = rapikan_teks(df_supplier[kolom])

    # Kode kosong tidak dapat menjadi primary key; simpan untuk pemeriksaan.
    mask_kode_kosong = df_supplier["kode_supplier"].isna()
    dibuang = df_supplier.loc[mask_kode_kosong].copy()
    if not dibuang.empty:
        dibuang["alasan_dibuang"] = "kode_supplier kosong"

    valid = df_supplier.loc[~mask_kode_kosong].copy()

    # Primary key harus unik. Pertahankan baris pertama dan catat duplikat
    # agar kehilangan baris tidak terjadi tanpa laporan.
    mask_duplikat = valid.duplicated(subset=["kode_supplier"], keep="first")
    duplikat = valid.loc[mask_duplikat].copy()
    if not duplikat.empty:
        duplikat["alasan_dibuang"] = "kode_supplier duplikat; baris pertama dipakai"
        dibuang = pd.concat([dibuang, duplikat], ignore_index=True)

    df_supplier = valid.loc[~mask_duplikat].copy()

    # Laporan audit selalu diperbarui agar angka baris yang dilewatkan terlihat.
    file_audit = Path(__file__).resolve().parent.parent / "Supplier_Dibuang.csv"
    if dibuang.empty:
        pd.DataFrame(columns=kolom_teks + ["alasan_dibuang"]).to_csv(
            file_audit, index=False, encoding="utf-8-sig"
        )
    else:
        dibuang.to_csv(file_audit, index=False, encoding="utf-8-sig")

    # CSV seluruh supplier valid untuk cadangan/pengecekan.
    file_csv = Path(__file__).resolve().parent.parent / "Data_Supplier.csv"
    df_supplier.to_csv(file_csv, index=False, encoding="utf-8-sig")

    if not df_supplier.empty:
        records = df_supplier.astype(object).where(df_supplier.notna(), None).to_dict("records")
        with mysql_engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO supplier
                    (kode_supplier, nama_supplier, alamat, kota, telepon)
                VALUES
                    (:kode_supplier, :nama_supplier, :alamat, :kota, :telepon)
                ON DUPLICATE KEY UPDATE
                    nama_supplier = VALUES(nama_supplier),
                    alamat = VALUES(alamat),
                    kota = VALUES(kota),
                    telepon = VALUES(telepon)
            """), records)

    print(f"Baris supplier dari SQL Server : {jumlah_sumber}")
    print(f"Supplier valid dan unik         : {len(df_supplier)}")
    print(f"Baris tanpa kode                : {int(mask_kode_kosong.sum())}")
    print(f"Baris kode duplikat             : {int(mask_duplikat.sum())}")
    print(f"Supplier di-upsert ke MySQL     : {len(df_supplier)}")
    print(f"CSV audit baris dilewatkan      : {file_audit}")
    print(f"CSV cadangan supplier           : {file_csv}")
    if df_supplier.empty:
        print("Tidak ada supplier valid dari SQL Server; data lama di MySQL tetap dipertahankan.")

    mysql_engine.dispose()


if __name__ == "__main__":
    main()
