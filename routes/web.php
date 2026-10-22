<?php

use App\Http\Controllers\AuthController as A;
use App\Http\Controllers\DashboardController;
use App\Http\Controllers\KlasifikasiAbcController;
use App\Http\Controllers\AnalisisFsnController;
use App\Http\Controllers\MatriksController;
use App\Http\Controllers\RopController;
use App\Http\Controllers\PenjualanController;
use App\Http\Controllers\PenangananController;
use App\Http\Controllers\SupplierController;
use App\Http\Controllers\ProsesDataController;
use App\Http\Middleware\Peran;
use Illuminate\Support\Facades\Route;

Route::get('/login', [A::class, 'form'])->name('login');
Route::post('/login', [A::class, 'masuk'])->name('login.masuk');
Route::post('/logout', [A::class, 'keluar'])->name('logout');

Route::middleware(Peran::class)->group(function () {
    Route::get('/', [DashboardController::class, 'dashboard'])->name('dashboard');
    Route::get('/abc', [KlasifikasiAbcController::class, 'index'])->name('abc');
    Route::get('/fsn', [AnalisisFsnController::class, 'index'])->name('fsn');
    Route::get('/matriks', [MatriksController::class, 'index'])->name('matriks');
    Route::get('/rop', [RopController::class, 'index'])->name('rop');
    Route::get('/penjualan', [PenjualanController::class, 'index'])->name('penjualan');
});

Route::get('/riwayat', [ProsesDataController::class, 'log'])->name('riwayat')->middleware(Peran::class . ':admin_stok');
Route::get('/penanganan', [PenangananController::class, 'index'])->name('penanganan')->middleware(Peran::class . ':admin_stok,owner');
// Admin pembelian: kelola lead time supplier
Route::get('/supplier', [SupplierController::class, 'index'])->name('supplier')->middleware(Peran::class . ':admin_pembelian');
Route::post('/supplier/lead-time', [SupplierController::class, 'simpanSemuaLeadTime'])->name('supplier.simpan-semua')->middleware(Peran::class . ':admin_pembelian');
Route::post('/supplier/{kode}', [SupplierController::class, 'simpanLeadTime'])->name('supplier.simpan')->middleware(Peran::class . ':admin_pembelian');
// Admin operasional stok: memproses data (ETL)
Route::post('/etl', [ProsesDataController::class, 'jalankan'])->name('etl')->middleware(Peran::class . ':admin_stok');


