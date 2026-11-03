import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from etl_config import buat_mysql_url

# total_qty_real sudah bertanda: positif = stok masuk, negatif = stok keluar
KOLOM_QTY = "total_qty_real"

# Kuantitas SELALU dalam satuan terkecil (pcs) supaya pembilang dan penyebut TOR sepadan.
#
# Sumber kuantitas penjualan:
#   "detail_penjualan" = SUM(total_qty) di tabel detail_penjualan
#                        (total_qty = nTotQty; isi lewat penjualan.py)
#   "stok"             = transaksi AJL di tabel stok
SUMBER_QTY_JUAL = "detail_penjualan"

# Rata-rata persediaan selalu dari tabel stok: semua transaksi
# (ABL pembelian, AJL penjualan, AAJ adjustment, ARG retur jual, ARB retur beli)
# membentuk saldo lewat tanda total_qty_real.
PREFIX_PENJUALAN = "AJL"
PREFIX_RETUR_JUAL = "ARG"

# True  = penjualan bersih (dikurangi retur jual ARG)
# False = penjualan kotor
KURANGI_RETUR_JUAL = False

# ---------- Batas klasifikasi FSN (berdasarkan TOR per tahun) ----------
#   TOR >  BATAS_FAST                  -> F (Fast-Moving)
#   BATAS_SLOW <= TOR <= BATAS_FAST    -> S (Slow-Moving)
#   TOR <  BATAS_SLOW                  -> N (Non-Moving)
BATAS_FAST = 12
BATAS_SLOW = 4

# True = TOR disetarakan ke 12 bulan (TOR x 365 / jumlah hari periode),
#        jadi TOR bisa dibaca sebagai "perputaran per tahun" berapa pun panjang periodenya.
# False = TOR apa adanya untuk seluruh periode.
NORMALISASI_TAHUNAN = True

# Untuk TOR, rata-rata stok di bawah 1 pcs menggunakan denominator minimum 1 pcs.
# Ini mencegah rata-rata pecahan yang sangat kecil membuat TOR dan kelas F melonjak.
BATAS_PERSEDIAAN_MINIM = 1


def tentukan_kelas_fsn(tor):
    if tor > BATAS_FAST:
        return "F"  # Fast-Moving
    elif tor >= BATAS_SLOW:
        return "S"  # Slow-Moving
    else:
        return "N"  # Non-Moving


class AnalisisFSN:
    """Menghitung klasifikasi FSN (Fast, Slow, Non-moving) dari MySQL,
    lalu menyimpan hasilnya ke tabel periode_analisis dan klasifikasi_fsn.

    - Kuantitas penjualan  : SUM(total_qty) detail_penjualan, dalam pcs
                             (atau AJL di tabel stok, lihat SUMBER_QTY_JUAL)
    - Rata-rata persediaan : rata-rata saldo berjalan dari tabel stok, dalam pcs
    - TOR                  : kuantitas penjualan / rata-rata persediaan
                             (disetarakan ke 12 bulan bila NORMALISASI_TAHUNAN = True)
    """

    def __init__(self, db_url):
        self.engine = create_engine(db_url)
        self.df_stok = None
        self.df_fsn = None
        self.df_fsn_dikecualikan = None
        self.qty_jual = None
        self.id_periode = None
        self.tgl_mulai = None
        self.tgl_akhir = None

    # ---------- 1. Buat tabel (kalau belum ada) ----------
    def siapkan_tabel(self):
        with self.engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS periode_analisis (
                    id_periode INT AUTO_INCREMENT PRIMARY KEY,
                    tanggal_mulai DATE NOT NULL,
                    tanggal_akhir DATE NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS klasifikasi_fsn (
                    id_fsn INT AUTO_INCREMENT PRIMARY KEY,
                    id_periode INT NOT NULL,
                    kode_produk VARCHAR(50) NOT NULL,
                    total_kuantitas_penjualan DECIMAL(18,2),
                    rata_rata_persediaan DECIMAL(18,2),
                    tor DECIMAL(18,4),
                    kelas_fsn CHAR(1),
                    FOREIGN KEY (id_periode) REFERENCES periode_analisis(id_periode),
                    FOREIGN KEY (kode_produk) REFERENCES barang(kode_produk)
                )
            """))
            # kalau tabel lama sudah ada tapi belum punya kolom tor, tambahkan
            ada_tor = conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = 'klasifikasi_fsn' "
                "AND column_name = 'tor'"
            )).scalar()
            if not ada_tor:
                conn.execute(text(
                    "ALTER TABLE klasifikasi_fsn ADD COLUMN tor DECIMAL(18,4) AFTER rata_rata_persediaan"
                ))
        return self

    # ---------- 2. Muat data stok dari MySQL ----------
    def muat_data(self, tgl_mulai=None, tgl_akhir=None):
        """Ambil data dari tabel stok. Rentang: tanggal >= tgl_mulai dan tanggal < tgl_akhir."""
        query = f"""
            SELECT id_stok, no_transaksi, tanggal, kode_produk, nama_produk,
                   {KOLOM_QTY} AS qty
            FROM stok
        """
        params = {}
        if tgl_mulai and tgl_akhir:
            query += " WHERE tanggal >= :mulai AND tanggal < :akhir"
            params = {"mulai": tgl_mulai, "akhir": tgl_akhir}

        df = pd.read_sql(text(query), self.engine, params=params)
        if df.empty:
            raise ValueError("Tidak ada data stok pada rentang tanggal tersebut.")

        df["tanggal"] = pd.to_datetime(df["tanggal"])
        df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0)
        df["no_transaksi"] = df["no_transaksi"].astype(str).str.strip().str.upper()

        self.df_stok = df

        # kuantitas penjualan dari detail_penjualan (kolom total_qty = pcs)
        if SUMBER_QTY_JUAL == "detail_penjualan":
            q_jual = "SELECT kode_produk, SUM(total_qty) AS qty_jual FROM detail_penjualan"
            if tgl_mulai and tgl_akhir:
                q_jual += " WHERE tanggal >= :mulai AND tanggal < :akhir"
            q_jual += " GROUP BY kode_produk"
            df_jual = pd.read_sql(text(q_jual), self.engine, params=params)
            df_jual["qty_jual"] = pd.to_numeric(df_jual["qty_jual"], errors="coerce").fillna(0)
            if df_jual.empty or (df_jual["qty_jual"] == 0).all():
                raise ValueError(
                    "total_qty di detail_penjualan kosong. Jalankan penjualan.py dulu "
                    "supaya kolom total_qty terisi."
                )
            self.qty_jual = df_jual.set_index("kode_produk")["qty_jual"]

        self.tgl_mulai = pd.to_datetime(tgl_mulai).date() if tgl_mulai else df["tanggal"].min().date()
        # tgl_akhir eksklusif, jadi tanggal terakhir periode = sehari sebelumnya
        self.tgl_akhir = (
            (pd.to_datetime(tgl_akhir) - pd.Timedelta(days=1)).date()
            if tgl_akhir else df["tanggal"].max().date()
        )
        return self

    # ---------- 3. Hitung klasifikasi FSN ----------
    def hitung_fsn(self):
        df = self.df_stok.copy()
        df["awalan"] = df["no_transaksi"].str.extract(r"^([A-Z]+)")[0]

        # qty sudah bertanda (+ masuk, - keluar), jadi semua jenis transaksi
        # (ABL, AJL, AAJ, ARG, ARB, dst.) ikut membentuk saldo persediaan
        df["gerak"] = df["qty"]

        # saldo persediaan berjalan per produk (urut tanggal, lalu id_stok)
        df = df.sort_values(["kode_produk", "tanggal", "id_stok"])
        df["saldo"] = df.groupby("kode_produk")["gerak"].cumsum()

        # stok awal tidak ada di data, jadi diperkirakan supaya saldo tidak pernah negatif
        stok_awal = (-df.groupby("kode_produk")["saldo"].transform("min")).clip(lower=0)
        df["persediaan"] = df["saldo"] + stok_awal

        rata_persediaan = df.groupby("kode_produk")["persediaan"].mean()
        retur = df[df["awalan"] == PREFIX_RETUR_JUAL].groupby("kode_produk")["qty"].sum()
        if SUMBER_QTY_JUAL == "detail_penjualan":
            # total_qty dari detail_penjualan (pcs), produk tanpa penjualan = 0
            total_jual = self.qty_jual.reindex(rata_persediaan.index).fillna(0)
            tanpa_stok = self.qty_jual.index.difference(rata_persediaan.index)
            if len(tanpa_stok) > 0:
                print(
                    f"Peringatan: {len(tanpa_stok)} produk terjual tetapi tidak punya data di tabel stok "
                    f"({self.qty_jual[tanpa_stok].sum():,.0f} pcs), tidak ikut dianalisis FSN."
                )
            if KURANGI_RETUR_JUAL:
                total_jual = (total_jual - retur.reindex(total_jual.index).fillna(0)).clip(lower=0)
        else:
            # penjualan = stok keluar AJL (pcs); qty negatif dibalik jadi positif
            keluar = df[df["awalan"] == PREFIX_PENJUALAN].groupby("kode_produk")["qty"].sum()
            if KURANGI_RETUR_JUAL:
                keluar = keluar.add(retur, fill_value=0)
            total_jual = (-keluar).clip(lower=0).reindex(rata_persediaan.index).fillna(0)
        nama = df.groupby("kode_produk")["nama_produk"].first()

        # frekuensi = jumlah transaksi penjualan (no_transaksi AJL unik) per produk dalam periode
        frekuensi = (
            df[df["awalan"] == PREFIX_PENJUALAN]
            .groupby("kode_produk")["no_transaksi"].nunique()
            .reindex(rata_persediaan.index).fillna(0).astype(int)
        )

        df_fsn = pd.DataFrame({
            "nama_produk": nama,
            "Total_Qty_Jual": total_jual,
            "Frekuensi_Jual": frekuensi,
            "Rata_Persediaan": rata_persediaan,
        }).reset_index()

        # produk yang tidak pernah terjual = 0 (bukan 1)
        df_fsn["Total_Qty_Jual"] = df_fsn["Total_Qty_Jual"].fillna(0)

        # Produk dengan rata-rata persediaan <= 1 pcs tidak dimasukkan ke
        # klasifikasi FSN karena TOR-nya tidak representatif (penyebut terlalu kecil).
        df_fsn["Persediaan_Minim"] = df_fsn["Rata_Persediaan"] <= BATAS_PERSEDIAAN_MINIM
        self.df_fsn_dikecualikan = df_fsn[df_fsn["Persediaan_Minim"]].copy()
        df_fsn = df_fsn[~df_fsn["Persediaan_Minim"]].copy()

        # Nilai rata-rata persediaan yang lolos filter tetap memakai nilai asli.
        denominator_tor = df_fsn["Rata_Persediaan"].clip(lower=BATAS_PERSEDIAAN_MINIM)

        # TOR = Total Kuantitas Penjualan / Rata-rata Persediaan (minimum 1 pcs)
        df_fsn["TOR"] = df_fsn["Total_Qty_Jual"] / denominator_tor

        # setarakan ke 12 bulan supaya TOR = perputaran per tahun
        self.jumlah_hari = (self.tgl_akhir - self.tgl_mulai).days + 1
        if NORMALISASI_TAHUNAN:
            df_fsn["TOR"] = df_fsn["TOR"] * 365 / self.jumlah_hari

        df_fsn["Kelas_FSN"] = df_fsn["TOR"].apply(tentukan_kelas_fsn)
        self.df_fsn = df_fsn.sort_values("TOR", ascending=False).reset_index(drop=True)
        return self

    # ---------- 4. Simpan cadangan ke CSV ----------
    def simpan_csv(self, path_output="Data_Klasifikasi_FSN.csv"):
        self.df_fsn.to_csv(path_output, index=False, encoding="utf-8-sig")
        if self.df_fsn_dikecualikan is not None:
            path_dikecualikan = Path(path_output).with_name("Data_FSN_Persediaan_Minim_Dikecualikan.csv")
            self.df_fsn_dikecualikan.to_csv(path_dikecualikan, index=False, encoding="utf-8-sig")
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
                text("DELETE FROM klasifikasi_fsn WHERE id_periode = :p"),
                {"p": self.id_periode},
            )

            df_sql = self.df_fsn[
                ["kode_produk", "Total_Qty_Jual", "Rata_Persediaan", "TOR", "Kelas_FSN"]
            ].copy()

            # kode_produk harus ada di tabel barang (foreign key). Kalau ada satu saja yang
            # tidak ada, seluruh insert gagal dan di-rollback sehingga tidak ada yang tersimpan.
            kode_barang = {
                str(r[0]).strip() for r in conn.execute(text("SELECT kode_produk FROM barang"))
            }
            df_sql["kode_produk"] = df_sql["kode_produk"].astype(str).str.strip()
            tidak_ada = df_sql[~df_sql["kode_produk"].isin(kode_barang)]
            if len(tidak_ada) > 0:
                print(
                    f"Peringatan: {len(tidak_ada)} produk tidak ada di tabel barang, tidak disimpan: "
                    + ", ".join(tidak_ada["kode_produk"].head(10))
                )
                df_sql = df_sql[df_sql["kode_produk"].isin(kode_barang)]

            df_sql.insert(0, "id_periode", self.id_periode)
            df_sql["Rata_Persediaan"] = df_sql["Rata_Persediaan"].round(2)
            df_sql["TOR"] = df_sql["TOR"].round(4)
            df_sql = df_sql.rename(columns={
                "Total_Qty_Jual": "total_kuantitas_penjualan",
                "Rata_Persediaan": "rata_rata_persediaan",
                "TOR": "tor",
                "Kelas_FSN": "kelas_fsn",
            })
            df_sql.to_sql("klasifikasi_fsn", conn, if_exists="append", index=False)

            jumlah = conn.execute(
                text("SELECT COUNT(*) FROM klasifikasi_fsn WHERE id_periode = :p"),
                {"p": self.id_periode},
            ).scalar()
            print(f"Tersimpan di MySQL: {jumlah} baris (id_periode {self.id_periode})")
        return self

    # ---------- Jalankan semua ----------
    def jalankan(self, tgl_mulai=None, tgl_akhir=None):
        self.siapkan_tabel()
        self.muat_data(tgl_mulai, tgl_akhir)
        self.hitung_fsn()
        self.simpan_csv()
        self.simpan_ke_sql()
        return self.df_fsn

    def ringkasan(self):
        pd.options.display.float_format = "{:,.2f}".format
        pd.options.display.width = 200
        pd.options.display.max_columns = None

        print(" KLASIFIKASI FSN ")
        print(self.df_fsn[[
            "kode_produk", "nama_produk", "Total_Qty_Jual", "Frekuensi_Jual",
            "Rata_Persediaan", "TOR", "Kelas_FSN",
        ]].head(15))
        print(f"\nTotal produk dianalisis : {len(self.df_fsn)}")
        print(f"Periode                 : {self.tgl_mulai} s/d {self.tgl_akhir} ({self.jumlah_hari} hari)")
        print(f"id_periode yang dipakai : {self.id_periode}")
        print(f"Batas                   : F > {BATAS_FAST} | S >= {BATAS_SLOW} | N < {BATAS_SLOW}"
              f" (TOR {'per tahun' if NORMALISASI_TAHUNAN else 'per periode'})")
        jumlah_dikecualikan = len(self.df_fsn_dikecualikan) if self.df_fsn_dikecualikan is not None else 0
        print(f"Produk dikecualikan     : {jumlah_dikecualikan} (rata-rata persediaan <= {BATAS_PERSEDIAAN_MINIM} pcs; lihat Data_FSN_Persediaan_Minim_Dikecualikan.csv)")
        print("\nJumlah baris stok per awalan no_transaksi:")
        print(self.df_stok["no_transaksi"].str.extract(r"^([A-Z]+)")[0].value_counts())
        print("Jumlah produk per kelas:")
        print(self.df_fsn["Kelas_FSN"].value_counts())


if __name__ == "__main__":
    analisis = AnalisisFSN(db_url=buat_mysql_url())
    # kosongkan tgl_mulai/tgl_akhir kalau mau pakai seluruh data di tabel stok
    analisis.jalankan(tgl_mulai="2025-07-01", tgl_akhir="2026-08-01")
    analisis.ringkasan()
