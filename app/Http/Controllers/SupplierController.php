<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

class SupplierController extends PersediaanBaseController
{
    private const LEAD_TIME_DEFAULT = 7;

    private const Z = [
        '0.9900' => 2.3263478740408408, '0.9750' => 1.959963984540054,
        '0.9500' => 1.6448536269514722, '0.9000' => 1.2815515655446004,
        '0.8000' => 0.8416212335729143,
    ];

    /** Daftar semua supplier; lead time diisi manual dan tidak terkait tanggal transaksi. */
    public function index(Request $r)
    {
        $rows = DB::table('supplier as s')
            ->leftJoinSub(
                DB::table('produk_supplier')
                    ->select('kode_supplier')
                    ->selectRaw('COUNT(DISTINCT kode_produk) AS produk')
                    ->groupBy('kode_supplier'),
                'ps',
                'ps.kode_supplier',
                '=',
                's.kode_supplier'
            )
            ->when($r->filled('q'), function ($q) use ($r) {
                $cari = trim((string) $r->input('q'));
                $q->where(function ($w) use ($cari) {
                    $w->where('s.nama_supplier', 'like', "%{$cari}%")
                        ->orWhere('s.kode_supplier', 'like', "%{$cari}%");
                });
            })
            ->select('s.kode_supplier', 's.nama_supplier', 's.kota', 's.telepon', 's.lead_time')
            ->selectRaw('COALESCE(ps.produk, 0) AS produk')
            ->orderBy('s.nama_supplier')
            ->get();

        return view('supplier', compact('rows'));
    }

    /** Simpan satu supplier (dipertahankan untuk kompatibilitas dengan form lama). */
    public function simpanLeadTime(Request $r, string $kode)
    {
        $data = $r->validate(['lead_time' => ['required', 'integer', 'min:1', 'max:365']]);
        abort_unless(DB::table('supplier')->where('kode_supplier', $kode)->exists(), 404);

        $jumlah = DB::transaction(function () use ($kode, $data) {
            $hari = (int) $data['lead_time'];
            DB::table('supplier')->where('kode_supplier', $kode)->update(['lead_time' => $hari]);
            DB::table('produk_supplier')->where('kode_supplier', $kode)->update(['lead_time' => $hari]);

            return $this->hitungUlangRop([$kode]);
        });

        return back()->with('ok', "Lead time supplier {$kode} disimpan: {$data['lead_time']} hari. {$jumlah} rekomendasi ROP diperbarui.");
    }

    /** Simpan nilai lead time untuk seluruh supplier yang tampil sekaligus. */
    public function simpanSemuaLeadTime(Request $r)
    {
        $data = $r->validate([
            'kode_supplier' => ['required', 'array', 'min:1'],
            'kode_supplier.*' => ['required', 'string', 'distinct'],
            'lead_time' => ['required', 'array', 'min:1'],
            'lead_time.*' => ['required', 'integer', 'min:1', 'max:365'],
        ], [
            'lead_time.*.required' => 'Isi lead time untuk setiap supplier yang ditampilkan.',
            'lead_time.*.integer' => 'Lead time harus berupa jumlah hari bulat.',
            'lead_time.*.min' => 'Lead time minimal 1 hari.',
            'lead_time.*.max' => 'Lead time maksimal 365 hari.',
        ]);

        if (count($data['kode_supplier']) !== count($data['lead_time'])) {
            return back()->withErrors(['lead_time' => 'Jumlah nilai lead time tidak cocok dengan daftar supplier.'])
                ->withInput();
        }

        $kodeSupplier = array_values($data['kode_supplier']);
        $nilaiLeadTime = array_values($data['lead_time']);
        $valid = DB::table('supplier')->whereIn('kode_supplier', $kodeSupplier)->count();
        if ($valid !== count(array_unique($kodeSupplier))) {
            return back()->withErrors(['kode_supplier' => 'Daftar supplier berubah atau memuat kode yang tidak dikenal. Muat ulang halaman.'])
                ->withInput();
        }

        $jumlahRop = DB::transaction(function () use ($kodeSupplier, $nilaiLeadTime) {
            foreach ($kodeSupplier as $index => $kode) {
                $hari = (int) $nilaiLeadTime[$index];
                DB::table('supplier')->where('kode_supplier', $kode)->update(['lead_time' => $hari]);
                // Salin juga ke relasi produk-supplier agar tetap kompatibel dengan data lama.
                DB::table('produk_supplier')->where('kode_supplier', $kode)->update(['lead_time' => $hari]);
            }

            return $this->hitungUlangRop($kodeSupplier);
        });

        return back()->with('ok', count($kodeSupplier) . " lead time supplier tersimpan. {$jumlahRop} rekomendasi ROP diperbarui.");
    }

    /** Hitung ulang SS, ROP, dan status produk terkait tanpa mengubah ABC/FSN/matriks. */
    private function hitungUlangRop(array $kodeSupplier): int
    {
        $idPeriode = DB::table('klasifikasi_abc')->max('id_periode');
        if (!$idPeriode || empty($kodeSupplier)) {
            return 0;
        }

        $produk = DB::table('produk_supplier')
            ->whereIn('kode_supplier', $kodeSupplier)
            ->distinct()
            ->pluck('kode_produk');
        $jumlah = 0;

        foreach ($produk->chunk(500) as $kumpulan) {
            // Bila satu produk punya beberapa supplier, tetap pakai lead time tercepat.
            $lead = DB::table('produk_supplier')
                ->whereIn('kode_produk', $kumpulan)
                ->whereNotNull('lead_time')
                ->orderBy('lead_time')
                ->orderBy('id_produk_supplier')
                ->get()
                ->unique('kode_produk')
                ->keyBy('kode_produk');

            $rows = DB::table('rekomendasi_rop')
                ->where('id_periode', $idPeriode)
                ->whereIn('kode_produk', $kumpulan)
                ->get();

            foreach ($rows as $row) {
                $pasangan = $lead[$row->kode_produk] ?? null;
                $leadTime = $pasangan ? (int) $pasangan->lead_time : self::LEAD_TIME_DEFAULT;
                $serviceLevel = (float) $row->service_level;
                if ($serviceLevel <= 0 || $serviceLevel >= 1) {
                    $serviceLevel = 0.95;
                }

                $safetyStock = (int) ceil($this->nilaiZ($serviceLevel) * (float) $row->std_penjualan * sqrt($leadTime));
                $reorderPoint = (int) ceil((float) $row->rata_rata_penjualan * $leadTime + $safetyStock);

                if ($row->stok_saat_ini === null) {
                    $status = 'Data stok tidak ada';
                } elseif ($reorderPoint > 0 && (float) $row->stok_saat_ini <= $reorderPoint) {
                    $status = 'Reorder';
                } else {
                    $status = 'Aman';
                }

                DB::table('rekomendasi_rop')->where('id_rop', $row->id_rop)->update([
                    'id_produk_supplier' => $pasangan->id_produk_supplier ?? null,
                    'lead_time' => $leadTime,
                    'safety_stock' => $safetyStock,
                    'reorder_point' => $reorderPoint,
                    'status_reorder' => $status,
                ]);
                $jumlah++;
            }
        }

        return $jumlah;
    }

    private function nilaiZ(float $p): float
    {
        $nilaiDibulatkan = number_format($p, 4, '.', '');
        if (isset(self::Z[$nilaiDibulatkan])) {
            return self::Z[$nilaiDibulatkan];
        }

        // Approximation inverse normal CDF (Acklam).
        $a = [-39.69683028665376, 220.9460984245205, -275.9285104469687, 138.3577518672690, -30.66479806614716, 2.506628277459239];
        $b = [-54.47609879822406, 161.5858368580409, -155.6989798598866, 66.80131188771972, -13.28068155288572];
        $c = [-0.007784894002430293, -0.3223964580411365, -2.400758277161838, -2.549732539343734, 4.374664141464968, 2.938163982698783];
        $d = [0.007784695709041462, 0.3224671290700398, 2.445134137142996, 3.754408661907416];

        if ($p < 0.02425) {
            $q = sqrt(-2 * log($p));
            return ((((($c[0] * $q + $c[1]) * $q + $c[2]) * $q + $c[3]) * $q + $c[4]) * $q + $c[5]) / (((($d[0] * $q + $d[1]) * $q + $d[2]) * $q + $d[3]) * $q + 1);
        }
        if ($p > 1 - 0.02425) {
            $q = sqrt(-2 * log(1 - $p));
            return -((((($c[0] * $q + $c[1]) * $q + $c[2]) * $q + $c[3]) * $q + $c[4]) * $q + $c[5]) / (((($d[0] * $q + $d[1]) * $q + $d[2]) * $q + $d[3]) * $q + 1);
        }

        $q = $p - 0.5;
        $r = $q * $q;
        return ((((($a[0] * $r + $a[1]) * $r + $a[2]) * $r + $a[3]) * $r + $a[4]) * $r + $a[5]) * $q
            / ((((($b[0] * $r + $b[1]) * $r + $b[2]) * $r + $b[3]) * $r + $b[4]) * $r + 1);
    }
}
