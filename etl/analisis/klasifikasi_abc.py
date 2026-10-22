import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from etl_config import buat_mysql_url


class AnalisisABC:
    """Menghitung klasifikasi ABC dari tabel detail_penjualan di MySQL,
    lalu menyimpan hasilnya ke tabel periode_analisis dan klasifikasi_abc."""

    def __init__(self, db_url):
        self.engine = create_engine(db_url)
        self.df_jual = None
        self.df_abc = None
        self.id_periode = None
        self.total_semua_penjualan = 0
        self.tgl_mulai = None
        self.tgl_akhir = None

    # buat table sql
    def siapkan_tabel(self):
        with self.engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS periode_analisis (
                    id_periode INT AUTO_INCREMENT PRIMARY KEY,
                    tanggal_mulai DATE NOT NULL,
                    tanggal_akhir DATE NOT NULL
                )
            """))

          
            ada_tabel = conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = 'klasifikasi_abc'"
            )).scalar()
            if ada_tabel:
                kolom_baru = conn.execute(text(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_schema = DATABASE() AND table_name = 'klasifikasi_abc' "
                    "AND column_name = 'qty_terjual'"
                )).scalar()
                if not kolom_baru:
                    try:
                        conn.execute(text("DROP TABLE klasifikasi_abc"))
                    except Exception as e:
                        raise RuntimeError(
                            "Tabel klasifikasi_abc lama tidak bisa dihapus, kemungkinan masih "
                            "dipakai FOREIGN KEY oleh tabel lain (misalnya matriks_abc_fsn). "
                            "Hapus tabel yang bergantung padanya dulu, lalu jalankan ulang."
                        ) from e

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS klasifikasi_abc (
                    id_abc INT AUTO_INCREMENT PRIMARY KEY,
                    id_periode INT NOT NULL,
                    kode_produk VARCHAR(50) NOT NULL,
                    nama_produk VARCHAR(100),
                    qty_terjual INT,
                    harga_satuan DECIMAL(18,2),
                    total_penjualan_produk DECIMAL(18,2),
                    total_penjualan_semua_produk DECIMAL(18,2),
                    persentase_nilai DECIMAL(8,4),
                    persentase_kumulatif DECIMAL(8,4),
                    kelas_abc CHAR(1),
                    FOREIGN KEY (id_periode) REFERENCES periode_analisis(id_periode),
                    FOREIGN KEY (kode_produk) REFERENCES barang(kode_produk)
                )
            """))
        return self

    # muat data langsung dr sql
    def muat_data(self, tgl_mulai=None, tgl_akhir=None):
        """Ambil data dari detail_penjualan, di-JOIN ke barang untuk nama_produk.
        tgl_mulai/tgl_akhir opsional, format 'YYYY-MM-DD'.
        Rentang: tanggal >= tgl_mulai dan tanggal < tgl_akhir."""
        query = """
            SELECT
                dp.kode_produk,
                b.nama_produk,
                dp.tanggal,
                dp.total_qty,
                dp.subtotal
            FROM detail_penjualan dp
            JOIN barang b ON dp.kode_produk = b.kode_produk
        """
        params = {}
        if tgl_mulai and tgl_akhir:
            query += " WHERE dp.tanggal >= :mulai AND dp.tanggal < :akhir"
            params = {"mulai": tgl_mulai, "akhir": tgl_akhir}

        df = pd.read_sql(text(query), self.engine, params=params)
        if df.empty:
            raise ValueError("Tidak ada data penjualan pada rentang tanggal tersebut.")

        # Kolom DECIMAL dari MySQL bisa terbaca sebagai Decimal/object,
        # jadi dipaksa ke angka supaya perhitungan aman.
        df["tanggal"] = pd.to_datetime(df["tanggal"])
        for kol in ["total_qty", "subtotal"]:
            df[kol] = pd.to_numeric(df[kol], errors="coerce").fillna(0)

        if (df["total_qty"] == 0).all():
            raise ValueError(
                "Kolom total_qty kosong semua. Jalankan penjualan.py dulu "
                "supaya detail_penjualan terisi ulang dengan total_qty."
            )

        self.df_jual = df
        self.tgl_mulai = pd.to_datetime(tgl_mulai).date() if tgl_mulai else df["tanggal"].min().date()
        # tgl_akhir eksklusif, jadi tanggal terakhir periode = sehari sebelumnya
        self.tgl_akhir = (
            (pd.to_datetime(tgl_akhir) - pd.Timedelta(days=1)).date()
            if tgl_akhir else df["tanggal"].max().date()
        )
        return self

    # ---------- 3. Hitung klasifikasi ABC ----------
    def hitung_abc(self):
        df_abc = (
            self.df_jual.groupby(["kode_produk", "nama_produk"])
            .agg(
                Qty_Terjual=("total_qty", "sum"),
                Total_Penjualan=("subtotal", "sum"),
                Periode_Awal=("tanggal", "min"),
                Periode_Akhir=("tanggal", "max"),
            )
            .reset_index()
        )
        df_abc["Qty_Terjual"] = df_abc["Qty_Terjual"].round().astype(int)

        # harga satuan per pcs (rata-rata) = total penjualan / qty terjual (pcs),
        # sehingga qty x harga satuan = total penjualan produk
        df_abc["Harga_Satuan"] = (
            df_abc["Total_Penjualan"] / df_abc["Qty_Terjual"].where(df_abc["Qty_Terjual"] != 0)
        ).round(2)

        # total penjualan seluruh produk dari detail_penjualan
        self.total_semua_penjualan = df_abc["Total_Penjualan"].sum()
        if self.total_semua_penjualan == 0:
            raise ValueError("Total penjualan 0, klasifikasi ABC tidak bisa dihitung.")
        df_abc["Total_Penjualan_Semua_Produk"] = self.total_semua_penjualan

       #omset terbesar ke terkecil
        df_abc = df_abc.sort_values(by="Total_Penjualan", ascending=False).reset_index(drop=True)
        df_abc["Persen_Omzet"] = df_abc["Total_Penjualan"] / self.total_semua_penjualan
        df_abc["Persen_Kumulatif"] = df_abc["Persen_Omzet"].cumsum()

        def tentukan_kelas_abc(persen):
            if persen <= 0.80:
                return "A"
            elif persen <= 0.95:
                return "B"
            else:
                return "C"
        df_abc["Kelas_ABC"] = df_abc["Persen_Kumulatif"].apply(tentukan_kelas_abc)

        self.df_abc = df_abc[[
            "kode_produk", "nama_produk", "Qty_Terjual", "Harga_Satuan",
            "Total_Penjualan", "Total_Penjualan_Semua_Produk",
            "Persen_Omzet", "Persen_Kumulatif", "Kelas_ABC",
            "Periode_Awal", "Periode_Akhir",
        ]]
        return self

    def ringkasan_kelas(self):
        """Jumlah produk, persen produk, total penjualan, dan persen penjualan per kelas ABC."""
        total_produk = len(self.df_abc)
        total_omzet = self.df_abc["Total_Penjualan"].sum()
        df = (
            self.df_abc.groupby("Kelas_ABC")
            .agg(Jumlah_Produk=("kode_produk", "count"),
                 Total_Penjualan=("Total_Penjualan", "sum"))
            .reindex(["A", "B", "C"])
            .fillna(0)
        )
        df["Persen_Produk"] = df["Jumlah_Produk"] / total_produk * 100
        df["Persen_Penjualan"] = df["Total_Penjualan"] / total_omzet * 100
        return df.reset_index()

    # ---------- 4. Simpan cadangan ke CSV ----------
    def simpan_csv(self, path_output="Data_Klasifikasi_ABC.csv"):
        df_simpan = self.df_abc.copy()
        df_simpan["Periode_Awal"] = df_simpan["Periode_Awal"].dt.strftime("%Y-%m-%d")
        df_simpan["Periode_Akhir"] = df_simpan["Periode_Akhir"].dt.strftime("%Y-%m-%d")
        df_simpan.to_csv(path_output, index=False, encoding="utf-8-sig")
        self.ringkasan_kelas().to_csv(
            "Ringkasan_Kelas_ABC.csv", index=False, encoding="utf-8-sig"
        )
        return self

    # ---------- 5. Simpan ke MySQL ----------
    def simpan_ke_sql(self):
        with self.engine.begin() as conn:
            params = {"mulai": self.tgl_mulai, "akhir": self.tgl_akhir}
            cari_periode = text(
                "SELECT id_periode FROM periode_analisis "
                "WHERE tanggal_mulai = :mulai AND tanggal_akhir = :akhir "
                "ORDER BY id_periode DESC LIMIT 1"
            )
            row = conn.execute(cari_periode, params).fetchone()
            if row is None:
                conn.execute(
                    text("INSERT INTO periode_analisis (tanggal_mulai, tanggal_akhir) "
                         "VALUES (:mulai, :akhir)"),
                    params,
                )
                row = conn.execute(cari_periode, params).fetchone()
            self.id_periode = row[0]

            # hapus hasil lama periode yang sama supaya tidak dobel
            conn.execute(
                text("DELETE FROM klasifikasi_abc WHERE id_periode = :p"),
                {"p": self.id_periode},
            )

            df_sql = self.df_abc[[
                "kode_produk", "nama_produk", "Qty_Terjual", "Harga_Satuan",
                "Total_Penjualan", "Total_Penjualan_Semua_Produk",
                "Persen_Omzet", "Persen_Kumulatif", "Kelas_ABC",
            ]].copy()
            df_sql.insert(0, "id_periode", self.id_periode)
            df_sql["Persen_Omzet"] = (df_sql["Persen_Omzet"] * 100).round(4)
            df_sql["Persen_Kumulatif"] = (df_sql["Persen_Kumulatif"] * 100).round(4)

            df_sql = df_sql.rename(columns={
                "Qty_Terjual": "qty_terjual",
                "Harga_Satuan": "harga_satuan",
                "Total_Penjualan": "total_penjualan_produk",
                "Total_Penjualan_Semua_Produk": "total_penjualan_semua_produk",
                "Persen_Omzet": "persentase_nilai",
                "Persen_Kumulatif": "persentase_kumulatif",
                "Kelas_ABC": "kelas_abc",
            })

            df_sql.to_sql("klasifikasi_abc", conn, if_exists="append", index=False)
        return self

    # ---------- Jalankan semua ----------
    def jalankan(self, tgl_mulai=None, tgl_akhir=None):
        self.siapkan_tabel()
        self.muat_data(tgl_mulai, tgl_akhir)
        self.hitung_abc()
        self.simpan_csv()
        self.simpan_ke_sql()
        return self.df_abc

    def ringkasan(self):
        pd.options.display.float_format = "{:,.2f}".format
        pd.options.display.width = 200
        pd.options.display.max_columns = None

        print(" KLASIFIKASI ABC ")
        print(
            self.df_abc[[
                "kode_produk", "nama_produk", "Qty_Terjual", "Harga_Satuan",
                "Total_Penjualan", "Persen_Kumulatif", "Kelas_ABC",
            ]].head(15)
        )
        print(f"\nTotal produk dianalisis       : {len(self.df_abc)}")
        print(f"Total qty terjual (semua)     : {self.df_abc['Qty_Terjual'].sum():,}")
        print(f"Total penjualan semua produk  : Rp {self.total_semua_penjualan:,.2f}")
        print(f"Periode                       : {self.tgl_mulai} s/d {self.tgl_akhir}")
        print(f"id_periode yang dipakai       : {self.id_periode}")

        tabel = self.ringkasan_kelas()
        total_produk = len(self.df_abc)
        print("\nRingkasan per kelas:")
        print(tabel)
        print()
        for _, r in tabel.iterrows():
            print(
                f"Kelas {r['Kelas_ABC']}: {int(r['Jumlah_Produk'])} produk "
                f"({r['Persen_Produk']:.2f}% dari {total_produk} jenis produk) "
                f"menyumbang {r['Persen_Penjualan']:.2f}% dari total nilai penjualan"
            )


if __name__ == "__main__":
    analisis = AnalisisABC(db_url=buat_mysql_url())
    # kosongkan tgl_mulai/tgl_akhir kalau mau pakai seluruh data di detail_penjualan
    analisis.jalankan(tgl_mulai="2025-07-01", tgl_akhir="2026-08-01")
    analisis.ringkasan()
