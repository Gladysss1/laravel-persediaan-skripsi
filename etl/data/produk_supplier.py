import sys
from datetime import timedelta
from pathlib import Path
import random
import re

import pandas as pd
import pyodbc
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from etl_config import buat_mysql_engine, koneksi_sql_server, rentang_analisis_default

# koneksi mysql
mysql_engine = buat_mysql_engine()

tgl_mulai_default, tgl_akhir_default = rentang_analisis_default()
tgl_mulai = tgl_mulai_default.isoformat()
tgl_akhir = (tgl_akhir_default + timedelta(days=1)).isoformat()  # eksklusif


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


def info_kolom_kunci(conn, tabel, kolom):
    """Baca tipe dan collation kolom induk untuk membuat foreign key yang kompatibel."""
    info = conn.execute(text(
        "SELECT COLUMN_TYPE AS col_type, CHARACTER_SET_NAME AS char_set, "
        "COLLATION_NAME AS collation "
        "FROM information_schema.columns "
        "WHERE table_schema = DATABASE() AND table_name = :tabel AND column_name = :kolom"
    ), {"tabel": tabel, "kolom": kolom}).mappings().first()
    if not info:
        raise ValueError(f"Kolom {tabel}.{kolom} tidak ditemukan di database MySQL aktif.")
    tipe = str(info["col_type"])
    charset = info["char_set"]
    collation = info["collation"]
    if not charset or not collation:
        raise ValueError(f"{tabel}.{kolom} harus berupa kolom teks untuk relasi produk-supplier.")
    if not re.fullmatch(r"[A-Za-z0-9_(), ]+", tipe):
        raise ValueError(f"Tipe kolom {tabel}.{kolom} tidak aman/tidak didukung: {tipe}")
    if not re.fullmatch(r"[A-Za-z0-9_]+", str(charset)) or not re.fullmatch(r"[A-Za-z0-9_]+", str(collation)):
        raise ValueError(f"Charset/collation {tabel}.{kolom} tidak valid.")
    definisi = f"{tipe} CHARACTER SET {charset} COLLATE {collation} NOT NULL"
    return {"type": tipe, "charset": charset, "collation": collation, "definition": definisi}


def samakan_kolom_dan_fk(conn, kolom, tabel_induk, kolom_induk, nama_fk, info_induk):
    """Samakan kolom anak dengan kolom induk, lalu pastikan foreign key ada."""
    anak = conn.execute(text(
        "SELECT COLUMN_TYPE AS col_type, CHARACTER_SET_NAME AS char_set, "
        "COLLATION_NAME AS collation "
        "FROM information_schema.columns "
        "WHERE table_schema = DATABASE() AND table_name = 'produk_supplier' AND column_name = :kolom"
    ), {"kolom": kolom}).mappings().first()
    if not anak:
        conn.execute(text(
            f"ALTER TABLE produk_supplier ADD COLUMN `{kolom}` {info_induk['definition']}"
        ))
    elif (
        str(anak["col_type"]).lower() != info_induk["type"].lower()
        or str(anak["char_set"]).lower() != info_induk["charset"].lower()
        or str(anak["collation"]).lower() != info_induk["collation"].lower()
    ):
        fk_lama = conn.execute(text(
            "SELECT constraint_name FROM information_schema.key_column_usage "
            "WHERE table_schema = DATABASE() AND table_name = 'produk_supplier' "
            "AND column_name = :kolom AND referenced_table_name = :tabel"
        ), {"kolom": kolom, "tabel": tabel_induk}).scalars().all()
        for nama in fk_lama:
            aman_nama = str(nama).replace("`", "``")
            conn.execute(text(f"ALTER TABLE produk_supplier DROP FOREIGN KEY `{aman_nama}`"))
        conn.execute(text(
            f"ALTER TABLE produk_supplier MODIFY COLUMN `{kolom}` {info_induk['definition']}"
        ))

    ada_fk = conn.execute(text(
        "SELECT COUNT(*) FROM information_schema.key_column_usage "
        "WHERE table_schema = DATABASE() AND table_name = 'produk_supplier' "
        "AND column_name = :kolom AND referenced_table_name = :tabel "
        "AND referenced_column_name = :kolom_induk"
    ), {"kolom": kolom, "tabel": tabel_induk, "kolom_induk": kolom_induk}).scalar()
    if not ada_fk:
        conn.execute(text(
            f"ALTER TABLE produk_supplier ADD CONSTRAINT `{nama_fk}` "
            f"FOREIGN KEY (`{kolom}`) REFERENCES `{tabel_induk}` (`{kolom_induk}`)"
        ))


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

        info_produk = info_kolom_kunci(conn, "barang", "kode_produk")
        info_supplier = info_kolom_kunci(conn, "supplier", "kode_supplier")
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS produk_supplier (
                id_produk_supplier INT AUTO_INCREMENT PRIMARY KEY,
                kode_produk {info_produk['definition']},
                kode_supplier {info_supplier['definition']},
                lead_time INT NULL,
                UNIQUE KEY uq_produk_supplier (kode_produk, kode_supplier),
                CONSTRAINT fk_produk_supplier_barang
                    FOREIGN KEY (kode_produk) REFERENCES barang(kode_produk),
                CONSTRAINT fk_produk_supplier_supplier
                    FOREIGN KEY (kode_supplier) REFERENCES supplier(kode_supplier)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """))

        # Tabel yang sudah terlanjur dibuat mungkin memakai collation database default.
        # Samakan dengan kolom induk sebelum memasang FK agar tidak error 3780.
        samakan_kolom_dan_fk(
            conn, "kode_produk", "barang", "kode_produk", "fk_produk_supplier_barang", info_produk
        )
        samakan_kolom_dan_fk(
            conn, "kode_supplier", "supplier", "kode_supplier", "fk_produk_supplier_supplier", info_supplier
        )
        ada_lead_time = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = 'produk_supplier' AND column_name = 'lead_time'"
        )).scalar()
        if not ada_lead_time:
            conn.execute(text("ALTER TABLE produk_supplier ADD COLUMN lead_time INT NULL"))

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

    # Lead time dummy ditetapkan satu kali per supplier, acak 1-10 hari.
    # Nilai yang sudah ada tidak diacak ulang agar baseline ROP tetap stabil.
    with mysql_engine.begin() as conn:
        ada_lead_time_supplier = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = 'supplier' AND column_name = 'lead_time'"
        )).scalar()
        if not ada_lead_time_supplier:
            conn.execute(text("ALTER TABLE supplier ADD COLUMN lead_time SMALLINT UNSIGNED NULL"))
        supplier_kosong = conn.execute(text(
            "SELECT kode_supplier FROM supplier WHERE lead_time IS NULL"
        )).scalars().all()
        for kode in supplier_kosong:
            conn.execute(text(
                "UPDATE supplier SET lead_time = :lead_time "
                "WHERE kode_supplier = :kode_supplier AND lead_time IS NULL"
            ), {"lead_time": random.randint(1, 10), "kode_supplier": kode})
    if supplier_kosong:
        print(f"Lead time dummy 1-10 hari ditetapkan untuk {len(supplier_kosong)} supplier tanpa nilai.")

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
