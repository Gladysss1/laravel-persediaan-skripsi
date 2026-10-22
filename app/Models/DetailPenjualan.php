<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class DetailPenjualan extends Model
{
    protected $table = 'detail_penjualan';
    protected $primaryKey = 'id_detail_jual';
    public $timestamps = false;
    protected $guarded = [];
    protected $casts = ['tanggal' => 'date'];

    public function barang() { return $this->belongsTo(Barang::class, 'kode_produk', 'kode_produk'); }
}
