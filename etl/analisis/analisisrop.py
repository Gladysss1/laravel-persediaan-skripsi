import argparse
import sys
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from etl_config import buat_mysql_url, rentang_analisis_default


def nilai_z(service_level):
    """Nilai Z distribusi normal untuk service level tertentu (misalnya 0.95 -> 1.645)."""
    return NormalDist().inv_cdf(service_level)


def format_satuan(pcs, s1, s2, s3, nisi, nisi_2):
    """Ubah total pcs jadi teks satuan, misalnya 2 IKT 3 BAL 5 PCS.

    Asumsi: 1 satuan (terbesar) = nisi satuan_2, dan 1 satuan_2 = nisi_2 satuan_3.
    Jadi 1 satuan terbesar = nisi x nisi_2 pcs.
    """
    if pd.isna(pcs):
        return None
    pcs = max(int(round(pcs)), 0)
    nisi = int(nisi) if pd.notna(nisi) and nisi > 0 else 1
    nisi_2 = int(nisi_2) if pd.notna(nisi_2) and nisi_2 > 0 else 1

    q1, sisa = divmod(pcs, nisi * nisi_2)
    q2, q3 = divmod(sisa, nisi_2)

    bagian = []
    if q1:
        bagian.append(f"{q1} {s1 or 'PCS'}")
    if q2:
        bagian.append(f"{q2} {s2 or 'PCS'}")
    if q3 or not bagian:
        bagian.append(f"{q3} {s3 or 'PCS'}")
    return " ".join(bagian)


class AnalisisSafetyStockROP:
    """Menghitung safety stock, reorder point, dan status reorder per produk,
    lalu menyimpannya ke tabel rekomendasi_rop.

    Rumus (lead time tetap, permintaan harian berfluktuasi):
        Safety Stock  = Z x sigma_harian x akar(Lead Time)
        Reorder Point = (rata-rata penjualan harian x Lead Time) + Safety Stock

    Semua perhitungan dalam pcs (satuan terkecil). Kolom stok_satuan hanya untuk tampilan
    (misalnya "2 IKT 3 BAL 5 PCS"), dibentuk dari satuan, satuan_2, satuan_3, nisi, nisi_2
    di tabel barang. Relasi produk-supplier berasal dari data pembelian asli
    (produk_supplier.py); lead time dibaca dari input manual di tabel supplier.
    Jalankan analisis_abc.py, analisis_fsn.py, matriks_abc_fsn.py, dan
    produk_supplier.py lebih dulu."""

    # Service level per kategori matriks ABC-FSN (dummy, sesuaikan kebijakan toko)
    SERVICE_LEVEL = {
        "AF": 0.99, "AS": 0.975, "AN": 0.95,
        "BF": 0.975, "BS": 0.95, "BN": 0.90,
        "CF": 0.95, "CS": 0.90, "CN": 0.80,
    }
    SERVICE_LEVEL_DEFAULT = 0.95
    LEAD_TIME_DEFAULT = 7

    def __init__(self, db_url, service_level=None, tanggal_mulai=None, tanggal_akhir=None):
        self.engine = create_engine(db_url)
        self.service_level = service_level or self.SERVICE_LEVEL
        self.id_periode = None
        self.tgl_periode_mulai = None
        self.tgl_periode_akhir = None
        self.tgl_mulai = None
        self.tgl_akhir = None
        self.df_matriks = None
        self.df_jual = None
        self.df_stok = None
        self.df_barang = None
        self.df_lead = None
        self.df_stat = None
        self.stok_saat_ini = None
        self.df_rop = None
        self.tanggal_mulai_override = pd.Timestamp(tanggal_mulai).normalize() if tanggal_mulai else None
        self.tanggal_akhir_override = pd.Timestamp(tanggal_akhir).normalize() if tanggal_akhir else None

    # ---------- 1. Buat tabel (kalau belum ada) ----------
    def siapkan_tabel(self):
        with self.engine.begin() as conn:
            ada_matriks = conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = 'matriks_abc_fsn'"
            )).scalar()
            if not ada_matriks:
                raise ValueError("Tabel matriks_abc_fsn belum ada. Jalankan matriks_abc_fsn.py dulu.")

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS produk_supplier (
                    id_produk_supplier INT AUTO_INCREMENT PRIMARY KEY,
                    kode_produk VARCHAR(50) CHARACTER SET utf8mb4
                        COLLATE utf8mb4_0900_ai_ci NOT NULL,
                    kode_supplier VARCHAR(50) CHARACTER SET utf8mb4
                        COLLATE utf8mb4_0900_ai_ci NOT NULL,
                    lead_time INT,
                    UNIQUE KEY uq_produk_supplier (kode_produk, kode_supplier),
                    FOREIGN KEY (kode_produk) REFERENCES barang(kode_produk),
                    FOREIGN KEY (kode_supplier) REFERENCES supplier(kode_supplier)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
            """))

            # Rebuild skema lama hanya pada analisis normal. Simulasi tidak boleh
            # menghapus tabel karena di dalamnya tersimpan baseline tahunan.
            ada_tabel = conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = 'rekomendasi_rop'"
            )).scalar()
            if ada_tabel:
                kolom_baru = conn.execute(text(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_schema = DATABASE() AND table_name = 'rekomendasi_rop' "
                    "AND column_name IN ('std_penjualan', 'stok_saat_ini', 'service_level', 'stok_satuan')"
                )).scalar()
                if kolom_baru < 4:
                    if self.tanggal_mulai_override is not None or self.tanggal_akhir_override is not None:
                        raise ValueError(
                            "Struktur tabel rekomendasi_rop belum lengkap. Simulasi dihentikan "
                            "agar data ROP tahunan tidak terhapus. Jalankan 'Analisis Ulang ROP Saja' dulu."
                        )
                    conn.execute(text("DROP TABLE rekomendasi_rop"))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS rekomendasi_rop (
                    id_rop INT AUTO_INCREMENT PRIMARY KEY,
                    id_periode INT NOT NULL,
                    kode_produk VARCHAR(50) CHARACTER SET utf8mb4
                        COLLATE utf8mb4_0900_ai_ci NOT NULL,
                    id_produk_supplier INT NULL,
                    id_matriks INT NULL,
                    kategori_matriks CHAR(2),
                    rata_rata_penjualan DECIMAL(18,2),
                    std_penjualan DECIMAL(18,2),
                    lead_time INT,
                    service_level DECIMAL(5,4),
                    safety_stock INT,
                    reorder_point INT,
                    stok_saat_ini DECIMAL(18,2),
                    stok_satuan VARCHAR(100),
                    status_reorder VARCHAR(30),
                    tanggal_mulai_data DATE,
                    tanggal_akhir_data DATE,
                    waktu_snapshot DATETIME NULL,
                    FOREIGN KEY (id_periode) REFERENCES periode_analisis(id_periode),
                    FOREIGN KEY (kode_produk) REFERENCES barang(kode_produk),
                    FOREIGN KEY (id_produk_supplier)
                        REFERENCES produk_supplier(id_produk_supplier) ON DELETE SET NULL,
                    FOREIGN KEY (id_matriks)
                        REFERENCES matriks_abc_fsn(id_matriks) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
            """))
            for kolom in ["tanggal_mulai_data", "tanggal_akhir_data"]:
                ada = conn.execute(text(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_schema = DATABASE() AND table_name = 'rekomendasi_rop' "
                    "AND column_name = :k"
                ), {"k": kolom}).scalar()
                if not ada:
                    conn.execute(text(f"ALTER TABLE rekomendasi_rop ADD COLUMN {kolom} DATE NULL"))
            ada_snapshot = conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = 'rekomendasi_rop' "
                "AND column_name = 'waktu_snapshot'"
            )).scalar()
            if not ada_snapshot:
                conn.execute(text(
                    "ALTER TABLE rekomendasi_rop ADD COLUMN waktu_snapshot DATETIME NULL"
                ))
        return self

    # ---------- 2. Periode: ikut periode ABC terbaru ----------
    def tentukan_periode(self):
        tanggal_mulai, tanggal_akhir = rentang_analisis_default()
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT p.id_periode, p.tanggal_mulai, p.tanggal_akhir "
                "FROM periode_analisis p "
                "JOIN klasifikasi_abc a ON a.id_periode = p.id_periode "
                "WHERE p.tanggal_mulai = :mulai AND p.tanggal_akhir = :akhir "
                "ORDER BY p.id_periode DESC LIMIT 1"
            ), {"mulai": tanggal_mulai, "akhir": tanggal_akhir}).fetchone()
        if row is None:
            raise ValueError(
                "Baseline ABC tahunan belum tersedia untuk "
                f"{tanggal_mulai} s/d {tanggal_akhir}. Jalankan analisis ABC tahunan dulu."
            )
        self.id_periode = row[0]
        self.tgl_periode_mulai = pd.Timestamp(row[1]).normalize()
        self.tgl_periode_akhir = pd.Timestamp(row[2]).normalize()
        self.tgl_mulai = self.tanggal_mulai_override or self.tgl_periode_mulai
        self.tgl_akhir = self.tanggal_akhir_override or self.tgl_periode_akhir
        if self.tgl_mulai > self.tgl_akhir:
            raise ValueError("Tanggal mulai tidak boleh melewati tanggal akhir.")
        return self

    # ---------- 3. Muat data dari MySQL ----------
    def muat_data(self):
        # tanggal_akhir di periode_analisis adalah hari terakhir (inklusif). Query memakai
        # batas eksklusif (< akhir + 1 hari) supaya aman walau kolom tanggal bertipe DATETIME.
        mulai = self.tgl_mulai.date()
        batas_akhir = (self.tgl_akhir + pd.Timedelta(days=1)).date()

        # Kategori matriks dibentuk langsung dari hasil ABC dan FSN (kelas ABC + kelas FSN,
        # misalnya "A" + "F" = "AF"), jadi tidak bergantung pada isi tabel matriks_abc_fsn.
        # id_matriks diambil kalau barisnya ada di tabel itu, kalau tidak NULL.
        self.df_matriks = pd.read_sql(text("""
            SELECT m.id_matriks, a.kode_produk,
                   CONCAT(a.kelas_abc, f.kelas_fsn) AS kategori_matriks
            FROM klasifikasi_abc a
            JOIN klasifikasi_fsn f
                 ON f.kode_produk COLLATE utf8mb4_unicode_ci
                    = a.kode_produk COLLATE utf8mb4_unicode_ci
                AND f.id_periode = a.id_periode
            LEFT JOIN matriks_abc_fsn m ON m.id_abc = a.id_abc
            WHERE a.id_periode = :p
        """), self.engine, params={"p": self.id_periode})
        if self.df_matriks.empty:
            raise ValueError(
                f"Tidak ada data ABC dan FSN yang cocok untuk id_periode {self.id_periode}. "
                "Pastikan analisis_abc.py dan analisis_fsn.py sudah tersimpan ke MySQL "
                "dengan rentang tanggal yang sama."
            )
        # satu produk harus satu baris
        self.df_matriks = (
            self.df_matriks.sort_values("id_matriks")
            .drop_duplicates("kode_produk", keep="last")
            .reset_index(drop=True)
        )

        # penjualan harian per produk (pcs)
        self.df_jual = pd.read_sql(text("""
            SELECT kode_produk, tanggal, SUM(total_qty) AS qty
            FROM detail_penjualan
            WHERE tanggal >= :m AND tanggal < :a
            GROUP BY kode_produk, tanggal
        """), self.engine, params={"m": mulai, "a": batas_akhir})
        self.df_jual["tanggal"] = pd.to_datetime(self.df_jual["tanggal"]).dt.normalize()
        self.df_jual["qty"] = pd.to_numeric(self.df_jual["qty"], errors="coerce").fillna(0)

        # pergerakan stok per transaksi (pcs, bertanda: + masuk, - keluar).
        # Diambil dari SELURUH riwayat sampai akhir periode (tanpa batas awal), karena stok
        # saat ini = saldo kumulatif. Membatasi dari awal periode bisa membuang saldo awal
        # yang dicatat lebih dulu, sehingga stok terhitung terlalu kecil.
        self.df_stok = pd.read_sql(text("""
            SELECT id_stok, kode_produk, tanggal, total_qty_real AS gerak
            FROM stok
            WHERE tanggal < :a
        """), self.engine, params={"a": batas_akhir})
        self.df_stok["tanggal"] = pd.to_datetime(self.df_stok["tanggal"])
        self.df_stok["gerak"] = pd.to_numeric(self.df_stok["gerak"], errors="coerce").fillna(0)

        # satuan dan isi per produk (untuk tampilan stok_satuan)
        self.df_barang = pd.read_sql(text("""
            SELECT kode_produk, satuan, satuan_2, satuan_3, nisi, nisi_2
            FROM barang
        """), self.engine)
        self.df_barang = self.df_barang.drop_duplicates("kode_produk")
        for kol in ["nisi", "nisi_2"]:
            self.df_barang[kol] = pd.to_numeric(self.df_barang[kol], errors="coerce")
        return self

    # ---------- 4. Lead time manual per supplier ----------
    def siapkan_supplier(self):
        """Ambil lead time manual dari supplier; produk tanpa data memakai default ROP.

        Kolom supplier.lead_time dibuat melalui migration Laravel. Nilai ini dipertahankan
        saat relasi produk_supplier diimpor ulang.
        """
        df_ps = pd.read_sql(
            text("""
                SELECT ps.id_produk_supplier, ps.kode_produk, ps.kode_supplier,
                       COALESCE(s.lead_time, ps.lead_time) AS lead_time
                FROM produk_supplier ps
                LEFT JOIN supplier s
                    ON s.kode_supplier COLLATE utf8mb4_unicode_ci
                       = ps.kode_supplier COLLATE utf8mb4_unicode_ci
            """),
            self.engine,
        )
        if df_ps.empty:
            raise ValueError("Tabel produk_supplier masih kosong. Jalankan produk_supplier.py dulu.")

        df_ps["lead_time"] = pd.to_numeric(df_ps["lead_time"], errors="coerce")
        # Jika satu produk punya beberapa supplier dengan lead time terisi, pilih yang tercepat.
        # NaN diurutkan belakangan; perhitungan ROP memakai default untuk lead time kosong.
        self.df_lead = (df_ps.sort_values("lead_time", na_position="last")
                        .drop_duplicates("kode_produk"))

        tanpa = set(self.df_matriks["kode_produk"]) - set(
            self.df_lead.loc[self.df_lead["lead_time"].notna(), "kode_produk"]
        )
        if tanpa:
            print(f"Info: {len(tanpa)} produk belum memiliki lead time supplier yang diinput, "
                  f"memakai lead time default {self.LEAD_TIME_DEFAULT} hari.")
        return self

    # ---------- 5. Statistik penjualan harian ----------
    def hitung_statistik_penjualan(self):
        hari = pd.date_range(self.tgl_mulai, self.tgl_akhir, freq="D")
        kode = self.df_matriks["kode_produk"]
        if self.df_jual.empty:
            harian = pd.DataFrame(0.0, index=pd.Index(kode, name="kode_produk"), columns=hari)
        else:
            harian = (
                self.df_jual.pivot_table(
                    index="kode_produk", columns="tanggal", values="qty",
                    aggfunc="sum", fill_value=0,
                )
                .reindex(columns=hari, fill_value=0)   # hari tanpa jual = 0
                .reindex(kode, fill_value=0)           # produk tanpa penjualan = 0
            )
        self.df_stat = pd.DataFrame({
            "kode_produk": harian.index,
            "rata_rata_penjualan": harian.mean(axis=1).values,
            "std_penjualan": harian.std(axis=1, ddof=1).fillna(0).values,
        })
        return self

    # ---------- 6. Stok saat ini (akhir periode) ----------
    def hitung_stok_saat_ini(self):
        """Hitung saldo berjalan dari seluruh pergerakan stok yang tersedia sampai akhir periode.

        Perhitungan dimulai dari nol pada awal riwayat yang diimpor (default ETL: 2019-01-01)
        dan tidak menambahkan stok awal perkiraan. Karena itu, tabel stok harus sudah memuat
        seluruh pergerakan sejak tanggal awal riwayat yang dijadikan baseline.
        """
        g = self.df_stok.sort_values(["kode_produk", "tanggal", "id_stok"]).copy()
        g["saldo"] = g.groupby("kode_produk")["gerak"].cumsum()
        saldo_akhir = g.groupby("kode_produk")["saldo"].last()
        self.stok_saat_ini = saldo_akhir.rename("stok_saat_ini")
        return self

    # ---------- 7. Safety stock dan ROP ----------
    def hitung_safety_stock_rop(self):
        df = self.df_stat.merge(self.df_matriks, on="kode_produk", how="left")
        df = df.merge(
            self.df_lead[["kode_produk", "id_produk_supplier", "lead_time"]],
            on="kode_produk", how="left",
        )
        df["lead_time"] = df["lead_time"].fillna(self.LEAD_TIME_DEFAULT)

        df["service_level"] = (
            df["kategori_matriks"].map(self.service_level).fillna(self.SERVICE_LEVEL_DEFAULT)
        )
        df["z"] = df["service_level"].apply(nilai_z)

        # SS = Z x sigma x akar(L) ; ROP = (d x L) + SS
        df["safety_stock"] = df["z"] * df["std_penjualan"] * np.sqrt(df["lead_time"])
        df["reorder_point"] = df["rata_rata_penjualan"] * df["lead_time"] + df["safety_stock"]

        df = df.merge(self.stok_saat_ini, left_on="kode_produk", right_index=True, how="left")

        df["safety_stock"] = np.ceil(df["safety_stock"]).astype(int)
        df["reorder_point"] = np.ceil(df["reorder_point"]).astype(int)
        df["lead_time"] = df["lead_time"].astype(int)

        # Reorder hanya kalau ROP > 0. Produk tanpa permintaan (ROP = 0) dengan stok 0
        # tidak perlu dipesan, jadi tidak boleh ikut berstatus Reorder.
        df["status_reorder"] = np.select(
            [
                df["stok_saat_ini"].isna(),
                (df["reorder_point"] > 0) & (df["stok_saat_ini"] <= df["reorder_point"]),
            ],
            ["Data stok tidak ada", "Reorder"],
            default="Aman",
        )
        df["rata_rata_penjualan"] = df["rata_rata_penjualan"].round(2)
        df["std_penjualan"] = df["std_penjualan"].round(2)
        df["stok_saat_ini"] = df["stok_saat_ini"].round(2)

        # Stok dalam satuan (hanya tampilan), misalnya "2 IKT 3 BAL 5 PCS"
        df = df.merge(self.df_barang, on="kode_produk", how="left")
        df["stok_satuan"] = df.apply(
            lambda r: format_satuan(
                r["stok_saat_ini"], r["satuan"], r["satuan_2"],
                r["satuan_3"], r["nisi"], r["nisi_2"],
            ),
            axis=1,
        )
        self.df_rop = df
        return self

    # ---------- 8. Simpan cadangan ke CSV ----------
    def simpan_csv(self, path_output="Data_Safety_Stock_ROP.csv"):
        self.df_rop.to_csv(path_output, index=False, encoding="utf-8-sig")
        return self

    # ---------- 9. Simpan ke MySQL ----------
    def simpan_ke_sql(self):
        # Simulasi tanggal hanya memperbarui snapshot stok dan status terhadap ROP
        # tahunan yang sudah tersimpan. Jangan menimpa statistik, safety stock, atau ROP.
        if self.tanggal_mulai_override is not None or self.tanggal_akhir_override is not None:
            return self.simpan_snapshot_simulasi()

        df = self.df_rop.copy()
        df.insert(0, "id_periode", self.id_periode)
        df["tanggal_mulai_data"] = self.tgl_mulai.date()
        df["tanggal_akhir_data"] = self.tgl_akhir.date()

        # kolom yang boleh kosong diubah ke int/None supaya tersimpan sebagai NULL
        for kol in ["id_produk_supplier", "id_matriks"]:
            df[kol] = pd.Series(
                [int(x) if pd.notna(x) else None for x in df[kol]], index=df.index, dtype=object
            )
        df["stok_saat_ini"] = df["stok_saat_ini"].astype(object).where(df["stok_saat_ini"].notna(), None)
        df["stok_satuan"] = df["stok_satuan"].astype(object).where(df["stok_satuan"].notna(), None)

        df = df[[
            "id_periode", "kode_produk", "id_produk_supplier", "id_matriks", "kategori_matriks",
            "rata_rata_penjualan", "std_penjualan", "lead_time", "service_level",
            "safety_stock", "reorder_point", "stok_saat_ini", "stok_satuan", "status_reorder",
            "tanggal_mulai_data", "tanggal_akhir_data",
        ]]
        with self.engine.begin() as conn:
            conn.execute(
                text("DELETE FROM rekomendasi_rop WHERE id_periode = :p"),
                {"p": self.id_periode},
            )
            df.to_sql("rekomendasi_rop", conn, if_exists="append", index=False)

            jumlah = conn.execute(
                text("SELECT COUNT(*) FROM rekomendasi_rop WHERE id_periode = :p"),
                {"p": self.id_periode},
            ).scalar()
            print(f"Tersimpan di MySQL: {jumlah} baris (id_periode {self.id_periode})")
        return self

    def simpan_snapshot_simulasi(self):
        """Simpan stok dan status simulasi; pertahankan seluruh dasar ROP periode aktif."""
        kolom_dasar = [
            "id_periode", "kode_produk", "id_produk_supplier", "id_matriks",
            "kategori_matriks", "rata_rata_penjualan", "std_penjualan", "lead_time",
            "service_level", "safety_stock", "reorder_point", "tanggal_mulai_data",
            "tanggal_akhir_data", "stok_saat_ini", "stok_satuan", "status_reorder",
        ]
        dasar = pd.read_sql(
            text("SELECT " + ", ".join(kolom_dasar) +
                 " FROM rekomendasi_rop WHERE id_periode = :p"),
            self.engine,
            params={"p": self.id_periode},
        )
        if dasar.empty:
            raise ValueError(
                "Belum ada ROP tahunan untuk periode ABC aktif. Jalankan 'Analisis Ulang ROP Saja' "
                "terlebih dahulu sebelum simulasi tanggal."
            )

        # Tolak simulasi jika baris tersimpan ternyata berasal dari simulasi sebelumnya.
        # Dengan begitu data Agustus tidak akan dianggap sebagai baseline tahunan.
        mulai_tersimpan = pd.to_datetime(dasar["tanggal_mulai_data"], errors="coerce").dt.normalize()
        akhir_tersimpan = pd.to_datetime(dasar["tanggal_akhir_data"], errors="coerce").dt.normalize()
        if (
            mulai_tersimpan.isna().any()
            or akhir_tersimpan.isna().any()
            or not mulai_tersimpan.eq(self.tgl_periode_mulai).all()
            or not akhir_tersimpan.eq(self.tgl_periode_akhir).all()
        ):
            raise ValueError(
                "ROP tersimpan bukan hasil periode ABC tahunan yang aktif. "
                "Jalankan 'Analisis Ulang ROP Saja' satu kali untuk membentuk baseline tahunan, "
                "lalu ulangi simulasi."
            )

        stok = self.df_rop[["kode_produk", "stok_saat_ini", "stok_satuan"]].copy()
        hasil = dasar.merge(stok, on="kode_produk", how="left", suffixes=("_dasar", "_simulasi"))
        hasil["stok_saat_ini"] = hasil["stok_saat_ini_simulasi"]
        hasil["stok_satuan"] = hasil["stok_satuan_simulasi"]

        def status_simulasi(row):
            if pd.isna(row["stok_saat_ini"]):
                return "Data stok tidak ada"
            reorder_point = pd.to_numeric(row["reorder_point"], errors="coerce")
            if pd.isna(reorder_point):
                return "Data ROP tidak ada"
            if reorder_point > 0 and float(row["stok_saat_ini"]) <= reorder_point:
                return "Reorder"
            return "Aman"

        hasil["status_reorder"] = hasil.apply(status_simulasi, axis=1)
        with self.engine.begin() as conn:
            for row in hasil.itertuples(index=False):
                stok_sekarang = None if pd.isna(row.stok_saat_ini) else float(row.stok_saat_ini)
                stok_satuan = None if pd.isna(row.stok_satuan) else str(row.stok_satuan)
                conn.execute(text("""
                    UPDATE rekomendasi_rop
                    SET stok_saat_ini = :stok,
                        stok_satuan = :stok_satuan,
                        status_reorder = :status,
                        waktu_snapshot = NOW()
                    WHERE id_periode = :periode AND kode_produk = :kode
                """), {
                    "stok": stok_sekarang,
                    "stok_satuan": stok_satuan,
                    "status": row.status_reorder,
                    "periode": self.id_periode,
                    "kode": row.kode_produk,
                })

        # CSV dan ringkasan juga menampilkan ROP tahunan yang dipertahankan,
        # dipadukan dengan stok/status dari snapshot simulasi.
        self.df_rop = hasil.drop(columns=["stok_saat_ini_dasar", "stok_satuan_dasar",
                                         "stok_saat_ini_simulasi", "stok_satuan_simulasi"])
        print(
            f"Snapshot simulasi {self.tgl_mulai.date()} s/d {self.tgl_akhir.date()} "
            f"memperbarui stok/status {len(hasil)} produk. Statistik tahunan, Safety Stock, "
            "dan ROP tidak diubah."
        )
        return self

    # ---------- Jalankan semua ----------
    def jalankan(self):
        (self.siapkan_tabel()
             .tentukan_periode()
             .muat_data()
             .siapkan_supplier()
             .hitung_statistik_penjualan()
             .hitung_stok_saat_ini()
             .hitung_safety_stock_rop()
             .simpan_ke_sql()
             .simpan_csv())
        return self.df_rop

    def ringkasan(self):
        pd.options.display.float_format = "{:,.2f}".format
        pd.options.display.width = 220
        pd.options.display.max_columns = None

        d = self.df_rop
        print(" SAFETY STOCK & REORDER POINT ")
        print(d[[
            "kode_produk", "kategori_matriks", "rata_rata_penjualan", "std_penjualan",
            "lead_time", "safety_stock", "reorder_point", "stok_saat_ini", "stok_satuan",
            "status_reorder",
        ]].head(15))
        print(f"\nPeriode                  : {self.tgl_mulai.date()} s/d {self.tgl_akhir.date()} (id {self.id_periode})")
        print(f"Total produk             : {len(d)}")
        print(f"Data stok dipakai dari   : {self.df_stok['tanggal'].min().date()} s/d {self.tgl_akhir.date()}")
        print(f"Produk dengan stok = 0   : {int((d['stok_saat_ini'] == 0).sum())}")
        print("Status reorder:")
        print(d["status_reorder"].value_counts())
        print("\nStatus reorder per kategori matriks:")
        print(pd.crosstab(d["kategori_matriks"], d["status_reorder"]))
        print("\nRata-rata per kategori matriks:")
        print(d.groupby("kategori_matriks")[["service_level", "safety_stock", "reorder_point"]].mean().round(2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hitung rekomendasi reorder point.")
    parser.add_argument("--tanggal-mulai", help="Tanggal mulai inklusif (YYYY-MM-DD)")
    parser.add_argument("--tanggal-akhir", help="Tanggal akhir inklusif (YYYY-MM-DD)")
    args = parser.parse_args()
    analisis = AnalisisSafetyStockROP(
        db_url=buat_mysql_url(),
        tanggal_mulai=args.tanggal_mulai,
        tanggal_akhir=args.tanggal_akhir,
    )
    analisis.jalankan()
    analisis.ringkasan()
