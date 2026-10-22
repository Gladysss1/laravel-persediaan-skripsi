@extends('layouts.app')
@section('judul', 'Dashboard')
@section('isi')
@if (!empty($analisisNotice))
    <div class="mb-4 p-3 rounded bg-amber-100 text-amber-900" role="status">{{ $analisisNotice }}</div>
@endif
<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
    @foreach ([
        ['Produk Kelas A', $abc['A'] ?? 0, 'text-blue-600'],
        ['Fast Moving', $fsn['F'] ?? 0, 'text-emerald-600'],
        ['Perlu Reorder', $rop['Reorder'] ?? 0, 'text-red-600'],
        ['Total Produk', $abc->sum(), 'text-slate-700'],
    ] as [$l, $v, $c])
        <div class="bg-white rounded shadow p-4">
            <div class="text-sm text-slate-500">{{ $l }}</div>
            <div class="text-3xl font-bold {{ $c }}">{{ number_format($v, 0, ',', '.') }}</div>
        </div>
    @endforeach
</div>

<div class="grid md:grid-cols-3 gap-4 mb-6">
    <div class="bg-white rounded shadow p-4"><div class="font-medium mb-2">Distribusi Kelas ABC</div><canvas id="cAbc"></canvas></div>
    <div class="bg-white rounded shadow p-4"><div class="font-medium mb-2">Distribusi Kategori FSN</div><canvas id="cFsn"></canvas></div>
    <div class="bg-white rounded shadow p-4">
        <div class="font-medium mb-2">Heatmap Matriks ABC-FSN</div>
        @php $maks = max(1, $matriks->max() ?? 1); @endphp
        <div class="grid grid-cols-4 gap-1 text-center text-sm">
            <div></div><div class="font-medium">F</div><div class="font-medium">S</div><div class="font-medium">N</div>
            @foreach (['A', 'B', 'C'] as $a)
                <div class="font-medium self-center">{{ $a }}</div>
                @foreach (['F', 'S', 'N'] as $f)
                    @php $n = $matriks[$a . $f] ?? 0; @endphp
                    <a href="{{ route('matriks', ['kelas' => $a . $f]) }}" class="rounded py-4 text-white font-semibold" style="background: rgba(37,99,235, {{ 0.15 + 0.85 * $n / $maks }})">{{ $n }}</a>
                @endforeach
            @endforeach
        </div>
    </div>
</div>

<div class="bg-white rounded shadow p-4 mb-6">
    <div class="font-medium mb-2">Top 10 Produk Fast-Moving Kelas A (nilai penjualan)</div>
    <canvas id="cTop" height="90"></canvas>
</div>

<div class="bg-white rounded shadow">
    <div class="p-4 font-medium flex justify-between">
        <span>Produk di Bawah ROP (prioritas teratas)</span>
        <a href="{{ route('rop', ['status' => 'Reorder']) }}" class="text-blue-600 text-sm">Lihat semua</a>
    </div>
    <table class="w-full text-sm">
        <thead class="bg-slate-50 text-left"><tr><th class="p-3">Kode</th><th class="p-3">Nama Produk</th><th class="p-3">Kategori</th><th class="p-3">Stok</th><th class="p-3 text-right">ROP (pcs)</th></tr></thead>
        <tbody>
        @forelse ($perlu as $p)
            <tr class="border-t"><td class="p-3">{{ $p->kode_produk }}</td><td class="p-3">{{ $p->nama_produk }}</td><td class="p-3">{{ $p->kategori_matriks }}</td><td class="p-3">{{ $p->stok_satuan }}</td><td class="p-3 text-right">{{ number_format($p->reorder_point, 0, ',', '.') }}</td></tr>
        @empty
            <tr><td colspan="5" class="p-4 text-center text-slate-400">Tidak ada produk yang perlu reorder.</td></tr>
        @endforelse
        </tbody>
    </table>
</div>

<script>
const donut = (id, data, colors) => new Chart(document.getElementById(id), {
    type: 'doughnut',
    data: { labels: Object.keys(data), datasets: [{ data: Object.values(data), backgroundColor: colors }] },
    options: { plugins: { legend: { position: 'bottom' } } }
});
new Chart(document.getElementById('cTop'), {
    type: 'bar',
    data: { labels: @json($top->pluck('nama_produk')->map(fn ($n) => \Illuminate\Support\Str::limit(trim($n), 28))),
            datasets: [{ data: @json($top->pluck('total_penjualan_produk')), backgroundColor: '#2563eb' }] },
    options: { indexAxis: 'y', plugins: { legend: { display: false } } }
});
donut('cAbc', @json($abc), ['#2563eb', '#f59e0b', '#94a3b8']);
donut('cFsn', @json($fsn), ['#10b981', '#f59e0b', '#ef4444']);
</script>
@endsection
