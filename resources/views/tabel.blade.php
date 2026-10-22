@extends('layouts.app')
@section('judul', $judul)
@section('isi')
<form method="GET" class="mb-4 flex flex-wrap gap-2">
    @unless (isset($tanpaCari))
        <input name="q" value="{{ request('q') }}" placeholder="Cari kode / nama produk" class="border rounded px-3 py-2 w-72 bg-white">
    @endunless
    @isset($filter)
        <select name="{{ $filter[0] }}" class="border rounded px-3 py-2 bg-white">
            <option value="">Semua</option>
            @foreach ($filter[1] as $v => $l)
                <option value="{{ $v }}" @selected(request($filter[0]) === (string) $v)>{{ $l }}</option>
            @endforeach
        </select>
    @endisset
    @unless (isset($tanpaCari)) <button class="bg-blue-600 text-white rounded px-4">Cari</button> @endunless
    <a href="{{ request()->fullUrlWithQuery(['export' => 1, 'page' => null]) }}" class="ml-auto bg-emerald-600 text-white rounded px-4 py-2">Ekspor Excel</a>
</form>

@php
    $badge = [
        'Reorder' => 'bg-red-100 text-red-700', 'Aman' => 'bg-emerald-100 text-emerald-700', 'Berhasil' => 'bg-emerald-100 text-emerald-700', 'Gagal' => 'bg-red-100 text-red-700',
        'A' => 'bg-blue-100 text-blue-700', 'B' => 'bg-amber-100 text-amber-700', 'C' => 'bg-slate-200 text-slate-700',
        'F' => 'bg-emerald-100 text-emerald-700', 'S' => 'bg-amber-100 text-amber-700', 'N' => 'bg-red-100 text-red-700',
    ];
    $kolomBadge = ['status', 'status_reorder', 'kelas_abc', 'kelas_fsn', 'kategori_matriks'];
@endphp

<div class="overflow-x-auto bg-white rounded shadow">
    <table class="w-full text-sm">
        <thead class="bg-slate-50 text-left">
            <tr>@foreach ($kolom as $k => $l)<th class="p-3 whitespace-nowrap {{ in_array($k, $angka) ? 'text-right' : '' }}">{{ $l }}</th>@endforeach</tr>
        </thead>
        <tbody>
        @forelse ($rows as $r)
            <tr class="border-t hover:bg-slate-50">
                @foreach ($kolom as $k => $l)
                    @php $v = $r->$k ?? null; @endphp
                    <td class="p-3 {{ in_array($k, $angka) ? 'text-right' : '' }}">
                        @if (in_array($k, $kolomBadge) && $v !== null)
                            <span class="px-2 py-0.5 rounded text-xs font-medium {{ $badge[$v] ?? $badge[substr($v, 0, 1)] ?? 'bg-slate-100' }}">{{ $v }}</span>
                        @elseif (in_array($k, $angka) && $v !== null)
                            {{ number_format((float) $v, floor((float) $v) == (float) $v ? 0 : 2, ',', '.') }}
                        @else
                            {{ $v ?? '-' }}
                        @endif
                    </td>
                @endforeach
            </tr>
        @empty
            <tr><td colspan="{{ count($kolom) }}" class="p-6 text-center text-slate-400">Data tidak ditemukan.</td></tr>
        @endforelse
        </tbody>
    </table>
</div>
<div class="mt-4">{{ $rows->links() }}</div>
@endsection
