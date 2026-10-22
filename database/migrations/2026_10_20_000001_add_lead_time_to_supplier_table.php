<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        if (!Schema::hasTable('supplier')) {
            return;
        }

        if (!Schema::hasColumn('supplier', 'lead_time')) {
            Schema::table('supplier', function (Blueprint $table) {
                $table->unsignedSmallInteger('lead_time')->nullable();
            });
        }

        // Preserve any lead times previously entered on product_supplier rows.
        if (Schema::hasTable('produk_supplier') && Schema::hasColumn('produk_supplier', 'lead_time')) {
            $existing = DB::table('produk_supplier')
                ->select('kode_supplier')
                ->selectRaw('MIN(lead_time) as lead_time')
                ->whereNotNull('lead_time')
                ->groupBy('kode_supplier')
                ->get();

            foreach ($existing as $row) {
                DB::table('supplier')
                    ->where('kode_supplier', $row->kode_supplier)
                    ->whereNull('lead_time')
                    ->update(['lead_time' => (int) $row->lead_time]);
            }
        }
    }

    public function down(): void
    {
        if (Schema::hasTable('supplier') && Schema::hasColumn('supplier', 'lead_time')) {
            Schema::table('supplier', function (Blueprint $table) {
                $table->dropColumn('lead_time');
            });
        }
    }
};
