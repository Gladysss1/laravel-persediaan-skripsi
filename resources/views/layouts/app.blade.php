<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>@yield('judul') - Pengendalian Persediaan</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
</head>
<body class="bg-slate-100 text-slate-800">
@php $role = session('user.role'); @endphp
<div class="flex min-h-screen">
    <aside class="w-60 bg-slate-900 text-slate-200 p-4 shrink-0 flex flex-col">
        <div class="font-bold text-white">CV Jaya Abadi Jaya</div>
        <div class="text-xs text-slate-400 mb-6">Pengendalian Persediaan</div>
        @php
            $menu = ['dashboard' => 'Dashboard', 'abc' => 'Klasifikasi ABC', 'fsn' => 'Analisis FSN', 'matriks' => 'Matriks ABC-FSN', 'rop' => 'Rekomendasi ROP', 'penjualan' => 'Laporan Penjualan'];
            if ($role === 'admin_stok') $menu['riwayat'] = 'Riwayat Proses';
            if (in_array($role, ['admin_stok', 'owner'])) $menu['penanganan'] = 'Penanganan Produk';
            if ($role === 'admin_pembelian') $menu['supplier'] = 'Supplier & Lead Time';
        @endphp
        @foreach ($menu as $r => $l)
            <a href="{{ route($r) }}" class="block px-3 py-2 rounded mb-1 {{ request()->routeIs($r) ? 'bg-blue-600 text-white' : 'hover:bg-slate-800' }}">{{ $l }}</a>
        @endforeach

        @if ($role === 'admin_stok')
            <form method="POST" action="{{ route('etl') }}" class="mt-6 space-y-2" onsubmit="return mulaiProsesEtl(event, this)">
                @csrf
                <button name="mode" value="rop_aktif" class="w-full bg-emerald-600 hover:bg-emerald-700 text-white rounded px-3 py-2 text-sm">Analisis Ulang ROP Saja</button>
                <button name="mode" value="analisis" class="w-full bg-blue-700 hover:bg-blue-800 text-white rounded px-3 py-2 text-sm">Analisis Tahunan dari Data MySQL</button>
                <button name="mode" value="penuh" class="w-full bg-slate-700 hover:bg-slate-600 text-white rounded px-3 py-2 text-sm">Tarik Data + Analisis ABC, FSN, Matriks & ROP</button>
                <div class="rounded border border-slate-700 p-2 space-y-2">
                    <div class="text-xs font-medium text-slate-200">Simulasi ROP per rentang tanggal</div>
                    <label class="block text-xs text-slate-400">Dari
                        <input type="date" name="tanggal_mulai" value="2026-08-01" class="mt-1 w-full rounded px-2 py-1 text-slate-800">
                    </label>
                    <label class="block text-xs text-slate-400">Sampai (termasuk)
                        <input type="date" name="tanggal_akhir" value="2026-08-19" class="mt-1 w-full rounded px-2 py-1 text-slate-800">
                    </label>
                    <button name="mode" value="simulasi_rop" class="w-full bg-amber-600 hover:bg-amber-700 text-white rounded px-3 py-2 text-sm">Tarik & Simulasikan ROP</button>
                    <div class="text-xs text-slate-400">Menarik pergerakan stok pada rentang ini dan memperbarui stok serta status reorder. Data penjualan, rata-rata tahunan, Safety Stock, ROP, ABC, FSN, dan matriks tetap.</div>
                </div>
                <div id="proses" class="hidden text-xs text-amber-300">Memproses, mohon tunggu...</div>
            </form>
        @endif

        <div class="mt-auto pt-6 text-sm">
            <div class="text-white">{{ session('user.nama') }}</div>
            <div class="text-xs text-slate-400 mb-2">{{ str_replace('_', ' ', $role) }}</div>
            <form method="POST" action="{{ route('logout') }}">@csrf<button class="text-xs underline text-slate-300">Keluar</button></form>
        </div>
    </aside>
    <main class="flex-1 p-6 min-w-0">
        <div class="flex items-center justify-between mb-4">
            <h1 class="text-xl font-semibold">@yield('judul')</h1>
            @if ($periode)
                <span class="text-sm text-slate-500">Periode: {{ \Carbon\Carbon::parse($periode->tanggal_mulai)->format('d M Y') }} s/d {{ \Carbon\Carbon::parse($periode->tanggal_akhir)->format('d M Y') }}</span>
            @endif
        </div>
        @if (session('ok')) <div class="mb-4 p-3 rounded bg-emerald-100 text-emerald-800">{{ session('ok') }}</div> @endif
        @if (session('gagal')) <div class="mb-4 p-3 rounded bg-red-100 text-red-800" role="alert">{{ session('gagal') }}</div> @endif
        @if ($errors->any()) <div class="mb-4 p-3 rounded bg-red-100 text-red-800" role="alert">{{ $errors->first() }}</div> @endif
        @yield('isi')
    </main>
</div>
<script>
function mulaiProsesEtl(event, form) {
    const pemicu = event.submitter;
    form.querySelectorAll('button').forEach((button) => {
        if (button !== pemicu) button.disabled = true;
    });
    document.getElementById('proses').classList.remove('hidden');
    return true;
}
</script>
</body>
</html>
