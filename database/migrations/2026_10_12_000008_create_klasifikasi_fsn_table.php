<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        if (!Schema::hasTable('klasifikasi_fsn')) {
                    Schema::create('klasifikasi_fsn', function (Blueprint $table) {
                        $table->integer('id_fsn')->autoIncrement()->primary();
                        $table->integer('id_periode');
                        $table->string('kode_produk', 50)->nullable()->collation('utf8mb4_0900_ai_ci');
                        $table->decimal('total_kuantitas_penjualan', 18, 2)->nullable();
                        $table->decimal('rata_rata_persediaan', 18, 2)->nullable();
                        $table->decimal('tor', 18, 4)->nullable();
                        $table->char('kelas_fsn', 1)->nullable();
                        $table->foreign('id_periode')->references('id_periode')->on('periode_analisis');
                        $table->foreign('kode_produk')->references('kode_produk')->on('barang');
                    });
                }
    }

    public function down(): void
    {
        Schema::dropIfExists('klasifikasi_fsn');
    }
};
