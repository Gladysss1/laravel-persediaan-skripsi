<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Hash;

class AuthController extends Controller
{
    public function form()
    {
        return session('user') ? redirect()->route('dashboard') : view('login');
    }

    public function masuk(Request $r)
    {
        $kredensial = $r->validate([
            'username' => ['required', 'string', 'max:50'],
            'password' => ['required', 'string', 'max:255'],
        ]);
        $u = DB::table('users')->where('username', trim($kredensial['username']))->first();
        if (!$u || !Hash::check($kredensial['password'], $u->password)) {
            return back()->withInput($r->only('username'))->with('gagal', 'Username atau password salah.');
        }
        $r->session()->regenerate();
        session(['user' => ['id' => $u->id_user, 'nama' => $u->nama, 'role' => $u->role]]);
        return redirect()->route('dashboard');
    }

    public function keluar(Request $r)
    {
        $r->session()->invalidate();
        $r->session()->regenerateToken();
        return redirect()->route('login');
    }
}
