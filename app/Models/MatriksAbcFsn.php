<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class MatriksAbcFsn extends Model
{
    protected $table = 'matriks_abc_fsn';
    protected $primaryKey = 'id_matriks';
    public $timestamps = false;
    protected $guarded = [];

    public function klasifikasiAbc() { return $this->belongsTo(KlasifikasiAbc::class, 'id_abc', 'id_abc'); }
    public function klasifikasiFsn() { return $this->belongsTo(KlasifikasiFsn::class, 'id_fsn', 'id_fsn'); }
    public function barang() { return $this->belongsTo(Barang::class, 'kode_produk', 'kode_produk'); }
    public function rekomendasiRop() { return $this->hasOne(RekomendasiRop::class, 'id_matriks', 'id_matriks'); }
}
