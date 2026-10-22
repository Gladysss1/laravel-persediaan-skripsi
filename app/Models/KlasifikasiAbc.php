<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class KlasifikasiAbc extends Model
{
    protected $table = 'klasifikasi_abc';
    protected $primaryKey = 'id_abc';
    public $timestamps = false;
    protected $guarded = [];

    public function periode() { return $this->belongsTo(PeriodeAnalisis::class, 'id_periode', 'id_periode'); }
    public function barang() { return $this->belongsTo(Barang::class, 'kode_produk', 'kode_produk'); }
    public function matriks() { return $this->hasOne(MatriksAbcFsn::class, 'id_abc', 'id_abc'); }
}
