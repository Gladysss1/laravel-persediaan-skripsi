<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class KlasifikasiFsn extends Model
{
    protected $table = 'klasifikasi_fsn';
    protected $primaryKey = 'id_fsn';
    public $timestamps = false;
    protected $guarded = [];

    public function periode() { return $this->belongsTo(PeriodeAnalisis::class, 'id_periode', 'id_periode'); }
    public function barang() { return $this->belongsTo(Barang::class, 'kode_produk', 'kode_produk'); }
    public function matriks() { return $this->hasOne(MatriksAbcFsn::class, 'id_fsn', 'id_fsn'); }
}
