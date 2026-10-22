<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        if (!Schema::hasTable('matriks_abc_fsn')) {
                    Schema::create('matriks_abc_fsn', function (Blueprint $table) {
                        $table->integer('id_matriks')->autoIncrement()->primary();
                        $table->integer('id_abc');
                        $table->integer('id_fsn');
                        $table->string('kode_produk', 50)->nullable()->collation('utf8mb4_0900_ai_ci');
                        $table->char('kategori_matriks', 2)->nullable();
                        $table->string('prioritas_kontrol', 20)->nullable();
                        $table->foreign('id_abc')->references('id_abc')->on('klasifikasi_abc')->cascadeOnDelete();
                        $table->foreign('id_fsn')->references('id_fsn')->on('klasifikasi_fsn')->cascadeOnDelete();
                        $table->foreign('kode_produk')->references('kode_produk')->on('barang');
                    });
                }
    }

    public function down(): void
    {
        Schema::dropIfExists('matriks_abc_fsn');
    }
};
