<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        if (!Schema::hasTable('detail_penjualan')) {
                    Schema::create('detail_penjualan', function (Blueprint $table) {
                        $table->integer('id_detail_jual')->autoIncrement()->primary();
                        $table->string('no_penjualan', 50)->nullable();
                        $table->date('tanggal')->nullable()->index();
                        $table->string('nama_pelanggan', 150)->nullable();
                        $table->string('kota', 100)->nullable();
                        $table->string('kode_produk', 50)->nullable();
                        $table->string('nama_produk', 150)->nullable();
                        $table->decimal('jumlah', 18, 2)->nullable();
                        $table->string('satuan', 20)->nullable();
                        $table->decimal('isi', 18, 2)->nullable();
                        $table->decimal('total_qty', 18, 2)->nullable();
                        $table->decimal('harga_satuan', 18, 2)->nullable();
                        $table->decimal('subtotal', 18, 2)->nullable();
                        $table->foreign('kode_produk')->references('kode_produk')->on('barang');
                    });
                }
    }

    public function down(): void
    {
        Schema::dropIfExists('detail_penjualan');
    }
};
