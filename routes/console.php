<?php

use Illuminate\Support\Facades\Schedule;

// Scheduler dipanggil tiap menit; ETL hanya berjalan pada kelipatan interval
// yang dipilih (contohnya menit 00, 15, 30, 45 untuk interval 15 menit).
Schedule::command('rop:refresh-snapshot')
    ->everyMinute()
    ->when(function () {
        $interval = max(1, (int) config('etl.rop_auto_refresh.interval_minutes', 15));

        return config('etl.rop_auto_refresh.enabled', false)
            && now()->minute % $interval === 0;
    })
    ->withoutOverlapping();
