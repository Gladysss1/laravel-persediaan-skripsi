<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        if (!Schema::hasTable('stok')) {
                    Schema::create('stok', function (Blueprint $table) {
                        $table->integer('id_stok')->autoIncrement()->primary();
                        $table->string('no_transaksi', 50)->nullable();
                        $table->date('tanggal')->nullable()->index();
                        $table->string('kode_produk', 50)->nullable();
                        $table->string('nama_produk', 150)->nullable();
                        $table->decimal('total_qty', 18, 2)->nullable();
                        $table->decimal('total_qty_real', 18, 2)->nullable();
                        $table->decimal('qty_1', 18, 2)->nullable();
                        $table->string('satuan', 20)->nullable();
                        $table->decimal('nisi', 18, 2)->nullable();
                        $table->decimal('qty_2', 18, 2)->nullable();
                        $table->string('satuan_2', 20)->nullable();
                        $table->decimal('qty_3', 18, 2)->nullable();
                        $table->decimal('nisi_2', 18, 2)->nullable();
                        $table->string('satuan_3', 20)->nullable();
                        $table->foreign('kode_produk')->references('kode_produk')->on('barang');
                    });
                }
    }

    public function down(): void
    {
        Schema::dropIfExists('stok');
    }
};
