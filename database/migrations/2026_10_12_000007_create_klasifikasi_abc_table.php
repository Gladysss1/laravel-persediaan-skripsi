<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        if (!Schema::hasTable('klasifikasi_abc')) {
                    Schema::create('klasifikasi_abc', function (Blueprint $table) {
                        $table->integer('id_abc')->autoIncrement()->primary();
                        $table->integer('id_periode');
                        $table->string('kode_produk', 50);
                        $table->string('nama_produk', 100)->nullable();
                        $table->integer('qty_terjual')->nullable();
                        $table->decimal('harga_satuan', 18, 2)->nullable();
                        $table->decimal('total_penjualan_produk', 18, 2)->nullable();
                        $table->decimal('total_penjualan_semua_produk', 18, 2)->nullable();
                        $table->decimal('persentase_nilai', 8, 4)->nullable();
                        $table->decimal('persentase_kumulatif', 8, 4)->nullable();
                        $table->char('kelas_abc', 1)->nullable();
                        $table->foreign('id_periode')->references('id_periode')->on('periode_analisis');
                        $table->foreign('kode_produk')->references('kode_produk')->on('barang');
                    });
                }
    }

    public function down(): void
    {
        Schema::dropIfExists('klasifikasi_abc');
    }
};
