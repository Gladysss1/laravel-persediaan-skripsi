import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from etl_config import buat_mysql_url

# Prioritas kontrol persediaan per kategori matriks ABC-FSN
PRIORITAS_KONTROL = {
    "AF": "Sangat Tinggi", "AS": "Tinggi", "AN": "Tinggi",
    "BF": "Tinggi",        "BS": "Sedang", "BN": "Sedang",
    "CF": "Sedang",        "CS": "Rendah", "CN": "Rendah",
}
URUTAN_PRIORITAS = {"Sangat Tinggi": 0, "Tinggi": 1, "Sedang": 2, "Rendah": 3}


class MatriksABCFSN:
    """Membuat matriks ABC-FSN dengan membaca LANGSUNG dari tabel yang sudah ada:
        - klasifikasi_abc  (kolom kelas_abc)
        - klasifikasi_fsn  (kolom kelas_fsn)
    lalu menyimpannya ke tabel matriks_abc_fsn di MySQL.

    Skrip ini tidak menghitung ulang ABC maupun FSN. Yang dipakai adalah hasil
    periode TERBARU di masing-masing tabel."""

    def __init__(self, db_url):
        self.engine = create_engine(db_url)
        self.id_periode_abc = None
        self.id_periode_fsn = None
        self.df_abc = None
        self.df_fsn = None
        self.df_matriks = None
        self.df_tanpa_pasangan = None

    # ---------- 1. Buat tabel (kalau belum ada) ----------
    def siapkan_tabel(self):
        with self.engine.begin() as conn:
            # Tabel lama dibuat ulang kalau strukturnya belum sesuai (tanpa ON DELETE CASCADE
            # atau tanpa kolom kategori_matriks). Aman karena isinya hasil gabungan ulang
            # dan tidak ada tabel lain yang bergantung padanya.
            ada_tabel = conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = 'matriks_abc_fsn'"
            )).scalar()
            if ada_tabel:
                tanpa_cascade = conn.execute(text(
                    "SELECT COUNT(*) FROM information_schema.referential_constraints "
                    "WHERE constraint_schema = DATABASE() AND table_name = 'matriks_abc_fsn' "
                    "AND referenced_table_name IN ('klasifikasi_abc', 'klasifikasi_fsn') "
                    "AND delete_rule <> 'CASCADE'"
                )).scalar()
                ada_kolom = conn.execute(text(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_schema = DATABASE() AND table_name = 'matriks_abc_fsn' "
                    "AND column_name IN ('kategori_matriks', 'prioritas_kontrol')"
                )).scalar()
                if tanpa_cascade > 0 or ada_kolom < 2:
                    conn.execute(text("DROP TABLE matriks_abc_fsn"))

            # ON DELETE CASCADE: kalau klasifikasi_abc / klasifikasi_fsn dihitung ulang
            # dan hasil lamanya dihapus, baris matriks terkait ikut terhapus otomatis
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS matriks_abc_fsn (
                    id_matriks INT AUTO_INCREMENT PRIMARY KEY,
                    id_abc INT NOT NULL,
                    id_fsn INT NOT NULL,
                    kode_produk VARCHAR(50) NOT NULL,
                    kategori_matriks CHAR(2),
                    prioritas_kontrol VARCHAR(20),
                    FOREIGN KEY (id_abc) REFERENCES klasifikasi_abc(id_abc) ON DELETE CASCADE,
                    FOREIGN KEY (id_fsn) REFERENCES klasifikasi_fsn(id_fsn) ON DELETE CASCADE,
                    FOREIGN KEY (kode_produk) REFERENCES barang(kode_produk)
                )
            """))
        return self

    # -muat kelas abc dan fsn
    def muat_data(self):
        with self.engine.connect() as conn:
            self.id_periode_abc = conn.execute(
                text("SELECT MAX(id_periode) FROM klasifikasi_abc")
            ).scalar()
            self.id_periode_fsn = conn.execute(
                text("SELECT MAX(id_periode) FROM klasifikasi_fsn")
            ).scalar()

        if self.id_periode_abc is None:
            raise ValueError("Tabel klasifikasi_abc masih kosong.")
        if self.id_periode_fsn is None:
            raise ValueError("Tabel klasifikasi_fsn masih kosong.")

        # hasil periode terbaru di masing-masing tabel
        self.df_abc = pd.read_sql(text("""
    SELECT a.id_abc, a.kode_produk, b.nama_produk,
           a.total_penjualan_produk, a.kelas_abc
    FROM klasifikasi_abc a
    JOIN barang b
      ON CONVERT(a.kode_produk USING utf8mb4) COLLATE utf8mb4_unicode_ci
       = CONVERT(b.kode_produk USING utf8mb4) COLLATE utf8mb4_unicode_ci
    WHERE a.id_periode = :p
"""), self.engine, params={"p": self.id_periode_abc})
        
        self.df_fsn = pd.read_sql(text("""
            SELECT id_fsn, kode_produk, tor, kelas_fsn
            FROM klasifikasi_fsn
            WHERE id_periode = :p
        """), self.engine, params={"p": self.id_periode_fsn})

        # tampilkan periode yang dipakai; beri peringatan kalau berbeda
        periode = pd.read_sql(text(
            "SELECT id_periode, tanggal_mulai, tanggal_akhir FROM periode_analisis "
            "WHERE id_periode IN (:a, :f)"
        ), self.engine, params={"a": self.id_periode_abc, "f": self.id_periode_fsn})
        periode = periode.set_index("id_periode")

        def teks_periode(i):
            if i in periode.index:
                return f"{periode.loc[i, 'tanggal_mulai']} s/d {periode.loc[i, 'tanggal_akhir']}"
            return "-"

        self.periode_abc = teks_periode(self.id_periode_abc)
        self.periode_fsn = teks_periode(self.id_periode_fsn)
        if self.id_periode_abc != self.id_periode_fsn:
            print(
                "Peringatan: ABC dan FSN memakai periode berbeda.\n"
                f"  ABC: id_periode {self.id_periode_abc} ({self.periode_abc})\n"
                f"  FSN: id_periode {self.id_periode_fsn} ({self.periode_fsn})"
            )
        return self

    # ---------- 3. Susun matriks ----------
    def susun_matriks(self):
        df = pd.merge(self.df_abc, self.df_fsn, on="kode_produk", how="outer", indicator=True)

        # produk yang hanya ada di salah satu klasifikasi tidak bisa dimasukkan ke matriks
        tanpa = df[df["_merge"] != "both"].copy()
        tanpa["keterangan"] = tanpa["_merge"].map({
            "left_only": "Ada di ABC, tidak ada di FSN (tidak punya data stok)",
            "right_only": "Ada di FSN, tidak ada di ABC (tidak ada penjualan)",
        })
        self.df_tanpa_pasangan = tanpa.drop(columns="_merge")

        df = df[df["_merge"] == "both"].drop(columns="_merge").copy()
        df["id_abc"] = df["id_abc"].astype(int)
        df["id_fsn"] = df["id_fsn"].astype(int)

        df["kategori_matriks"] = df["kelas_abc"] + df["kelas_fsn"]
        df["prioritas_kontrol"] = df["kategori_matriks"].map(PRIORITAS_KONTROL).fillna("Sedang")

        df["_urut"] = df["prioritas_kontrol"].map(URUTAN_PRIORITAS)
        df = (
            df.sort_values(["_urut", "kategori_matriks", "total_penjualan_produk"],
                           ascending=[True, True, False])
            .drop(columns="_urut")
            .reset_index(drop=True)
        )
        self.df_matriks = df
        return self

    # ---------- 4. Simpan cadangan ke CSV ----------
    def simpan_csv(self, path_output="Data_Matriks_ABC_FSN.csv"):
        self.df_matriks.to_csv(path_output, index=False, encoding="utf-8-sig")
        if len(self.df_tanpa_pasangan) > 0:
            self.df_tanpa_pasangan.to_csv(
                "Matriks_TanpaPasangan.csv", index=False, encoding="utf-8-sig"
            )
        return self

    # ---------- 5. Simpan ke MySQL ----------
    def simpan_ke_sql(self):
        with self.engine.begin() as conn:
            # kosongkan matriks lama supaya tidak dobel kalau dijalankan ulang
            conn.execute(text("DELETE FROM matriks_abc_fsn"))

            df_sql = self.df_matriks[[
                "id_abc", "id_fsn", "kode_produk", "kategori_matriks", "prioritas_kontrol"
            ]]
            df_sql.to_sql("matriks_abc_fsn", conn, if_exists="append", index=False)
        return self

    # ---------- Jalankan semua ----------
    def jalankan(self):
        self.siapkan_tabel()
        self.muat_data()
        self.susun_matriks()
        self.simpan_csv()
        self.simpan_ke_sql()
        return self.df_matriks

    def ringkasan(self):
        pd.options.display.float_format = "{:,.2f}".format
        pd.options.display.width = 200
        pd.options.display.max_columns = None

        print(" MATRIKS ABC - FSN ")
        print(self.df_matriks[[
            "kode_produk", "nama_produk", "kelas_abc", "kelas_fsn",
            "kategori_matriks", "prioritas_kontrol",
        ]].head(15))

        print(f"\nPeriode ABC             : id {self.id_periode_abc} ({self.periode_abc})")
        print(f"Periode FSN             : id {self.id_periode_fsn} ({self.periode_fsn})")
        print(f"Produk masuk matriks    : {len(self.df_matriks)}")
        if len(self.df_tanpa_pasangan) > 0:
            print(f"Produk tanpa pasangan   : {len(self.df_tanpa_pasangan)} "
                  "(lihat Matriks_TanpaPasangan.csv)")

        print("\nJumlah produk per sel matriks (baris = ABC, kolom = FSN):")
        print(pd.crosstab(self.df_matriks["kelas_abc"], self.df_matriks["kelas_fsn"], margins=True))

        print("\nJumlah produk per prioritas kontrol:")
        print(self.df_matriks["prioritas_kontrol"]
              .value_counts()
              .reindex(URUTAN_PRIORITAS.keys())
              .fillna(0).astype(int))


if __name__ == "__main__":
    matriks = MatriksABCFSN(db_url=buat_mysql_url())
    matriks.jalankan()
    matriks.ringkasan()
