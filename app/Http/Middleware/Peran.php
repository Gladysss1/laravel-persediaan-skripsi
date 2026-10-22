<?php

namespace App\Http\Middleware;

use Closure;

class Peran
{
    public function handle($request, Closure $next, ...$peran)
    {
        $u = session('user');
        if (!$u) {
            return redirect()->route('login');
        }
        if (!is_array($u) || empty($u['role'])) {
            $request->session()->invalidate();
            $request->session()->regenerateToken();
            return redirect()->route('login');
        }
        if ($peran && !in_array($u['role'], $peran, true)) {
            abort(403, 'Anda tidak punya akses ke halaman ini.');
        }
        return $next($request);
    }
}
