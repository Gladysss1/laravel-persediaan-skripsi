@extends('layouts.app')
@section('judul', 'Supplier & Lead Time')
@section('isi')
<form method="GET" action="{{ route('supplier') }}" class="mb-4 flex gap-2">
    <input name="q" value="{{ request('q') }}" placeholder="Cari supplier" class="border rounded px-3 py-2 w-72 bg-white">
    <button class="bg-blue-600 text-white rounded px-4">Cari</button>
    @if (request('q'))
        <a href="{{ route('supplier') }}" class="border rounded px-4 py-2">Tampilkan semua</a>
    @endif
</form>



@if ($rows->isNotEmpty())
    <form method="POST" action="{{ route('supplier.simpan-semua') }}">
        @csrf
        <div class="mb-3 flex items-center justify-between gap-3">
            <div class="text-sm text-slate-600">{{ $rows->count() }} supplier ditampilkan. Isi semua kolom lead time sebelum menyimpan.</div>
            <button class="rounded bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800">Simpan Semua Lead Time</button>
        </div>

        <div class="overflow-x-auto rounded bg-white shadow">
            <table class="w-full text-sm">
                <thead class="bg-slate-50 text-left">
                    <tr>
                        <th class="p-3">Kode</th>
                        <th class="p-3">Supplier</th>
                        <th class="p-3">Kota</th>
                        <th class="p-3">Telepon</th>
                        <th class="p-3 text-right">Jml Produk</th>
                        <th class="p-3">Lead Time (hari)</th>
                    </tr>
                </thead>
                <tbody>
                    @foreach ($rows as $s)
                        <tr class="border-t">
                            <td class="p-3">
                                {{ $s->kode_supplier }}
                                <input type="hidden" name="kode_supplier[]" value="{{ $s->kode_supplier }}">
                            </td>
                            <td class="p-3">{{ $s->nama_supplier }}</td>
                            <td class="p-3">{{ $s->kota }}</td>
                            <td class="p-3">{{ $s->telepon }}</td>
                            <td class="p-3 text-right">{{ $s->produk }}</td>
                            <td class="p-3">
                                <input
                                    type="number"
                                    name="lead_time[]"
                                    value="{{ old('lead_time.' . $loop->index, $s->lead_time) }}"
                                    min="1"
                                    max="365"
                                    required
                                    inputmode="numeric"
                                    aria-label="Lead time {{ $s->nama_supplier }} dalam hari"
                                    class="w-28 rounded border px-2 py-1"
                                    placeholder="Contoh: 7"
                                >
                            </td>
                        </tr>
                    @endforeach
                </tbody>
            </table>
        </div>

        <div class="mt-3 flex justify-end">
            <button class="rounded bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800">Simpan Semua Lead Time</button>
        </div>
    </form>
@else
    <div class="rounded bg-white p-6 text-center text-slate-500 shadow">Supplier tidak ditemukan.</div>
@endif
@endsection
