<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        if (!Schema::hasTable('rekomendasi_rop')) {
                    Schema::create('rekomendasi_rop', function (Blueprint $table) {
                        $table->integer('id_rop')->autoIncrement()->primary();
                        $table->integer('id_periode');
                        $table->string('kode_produk', 50);
                        $table->integer('id_produk_supplier')->nullable();
                        $table->integer('id_matriks')->nullable();
                        $table->char('kategori_matriks', 2)->nullable();
                        $table->decimal('rata_rata_penjualan', 18, 2)->nullable();
                        $table->decimal('std_penjualan', 18, 2)->nullable();
                        $table->integer('lead_time')->nullable();
                        $table->decimal('service_level', 5, 4)->nullable();
                        $table->integer('safety_stock')->nullable();
                        $table->integer('reorder_point')->nullable();
                        $table->decimal('stok_saat_ini', 18, 2)->nullable();
                        $table->string('stok_satuan', 100)->nullable();
                        $table->string('status_reorder', 30)->nullable();
                        $table->date('tanggal_mulai_data')->nullable();
                        $table->date('tanggal_akhir_data')->nullable();
                        $table->dateTime('waktu_snapshot')->nullable();
                        $table->foreign('id_periode')->references('id_periode')->on('periode_analisis');
                        $table->foreign('kode_produk')->references('kode_produk')->on('barang');
                        $table->foreign('id_produk_supplier')->references('id_produk_supplier')->on('produk_supplier')->nullOnDelete();
                        $table->foreign('id_matriks')->references('id_matriks')->on('matriks_abc_fsn')->nullOnDelete();
                    });
                }
        
                if (Schema::hasTable('rekomendasi_rop')) {
                    foreach (['tanggal_mulai_data', 'tanggal_akhir_data'] as $kolom) {
                        if (!Schema::hasColumn('rekomendasi_rop', $kolom)) {
                            Schema::table('rekomendasi_rop', function (Blueprint $table) use ($kolom) {
                                $table->date($kolom)->nullable();
                            });
                        }
                    }
                }
    }

    public function down(): void
    {
        Schema::dropIfExists('rekomendasi_rop');
    }
};
