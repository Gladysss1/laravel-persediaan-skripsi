<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        if (!Schema::hasTable('barang_detail')) {
                    Schema::create('barang_detail', function (Blueprint $table) {
                        $table->integer('id_barang_detail')->autoIncrement()->primary();
                        $table->string('kode_produk', 50);
                        $table->string('no_id', 10);
                        $table->string('satuan', 20)->nullable();
                        $table->decimal('harga_satuan', 18, 2)->nullable();
                        $table->decimal('isi', 18, 2)->nullable();
                        $table->unique(['kode_produk', 'no_id'], 'uq_barang_detail');
                        $table->foreign('kode_produk')->references('kode_produk')->on('barang');
                    });
                }
    }

    public function down(): void
    {
        Schema::dropIfExists('barang_detail');
    }
};
