import React, { useState, useEffect } from 'react';
import api from '../api';
import { useAuth } from '../AuthContext';

export default function Cuenta() {
  const { user } = useAuth();
  const [currency, setCurrency] = useState(user?.currency_preference || 'USD');
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  const handleCurrencyChange = async (newCurrency: string) => {
    setSaving(true);
    try {
      await api.put(`/auth/currency?currency=${newCurrency}`);
      setCurrency(newCurrency);
      setMessage('Moneda actualizada');
      setTimeout(() => setMessage(''), 2000);
    } catch (err) {
      setMessage('Error al actualizar');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Cuenta</h1>

      {/* User Info */}
      <div className="bg-[#1e293b] p-6 rounded-xl border border-[#334155]">
        <h2 className="text-lg font-semibold mb-4">Información del Usuario</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-slate-800/50 p-4 rounded-lg">
            <div className="text-sm text-slate-400">Nombre</div>
            <div className="text-lg font-medium mt-1">{user?.name}</div>
          </div>
          <div className="bg-slate-800/50 p-4 rounded-lg">
            <div className="text-sm text-slate-400">Email</div>
            <div className="text-lg font-medium mt-1">{user?.email}</div>
          </div>
          <div className="bg-slate-800/50 p-4 rounded-lg">
            <div className="text-sm text-slate-400">Rol</div>
            <div className="text-lg font-medium mt-1 capitalize">{user?.role}</div>
          </div>
          <div className="bg-slate-800/50 p-4 rounded-lg">
            <div className="text-sm text-slate-400">Moneda</div>
            <div className="text-lg font-medium mt-1">{currency}</div>
          </div>
        </div>
      </div>

      {/* Currency Preference */}
      <div className="bg-[#1e293b] p-6 rounded-xl border border-[#334155]">
        <h2 className="text-lg font-semibold mb-4">Preferencias</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-slate-400 mb-2">Moneda de Visualización</label>
            <div className="flex gap-3">
              <button
                onClick={() => handleCurrencyChange('USD')}
                disabled={saving}
                className={`px-6 py-3 rounded-lg font-medium transition-colors ${
                  currency === 'USD'
                    ? 'bg-emerald-600 text-white'
                    : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                }`}
              >
                USD ($)
              </button>
              <button
                onClick={() => handleCurrencyChange('COP')}
                disabled={saving}
                className={`px-6 py-3 rounded-lg font-medium transition-colors ${
                  currency === 'COP'
                    ? 'bg-emerald-600 text-white'
                    : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                }`}
              >
                COP ($)
              </button>
            </div>
            {message && (
              <div className={`mt-2 text-sm ${message.includes('Error') ? 'text-red-400' : 'text-emerald-400'}`}>
                {message}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Exchange Connection */}
      <div className="bg-[#1e293b] p-6 rounded-xl border border-[#334155]">
        <h2 className="text-lg font-semibold mb-4">Conexión con Exchange</h2>
        <div className="bg-slate-800/50 p-4 rounded-lg">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 bg-yellow-500 rounded-lg flex items-center justify-center text-black font-bold">B</div>
            <div>
              <div className="font-medium">Binance</div>
              <div className="text-sm text-slate-400">Conecta tu cuenta de Binance</div>
            </div>
          </div>
          <p className="text-sm text-slate-400 mb-3">
            El bot opera automáticamente en tu cuenta de Binance. Necesitas generar una API Key en tu cuenta de Binance.
          </p>
          <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 text-sm text-amber-400">
            ⚠️ Importante: Al crear la API Key, desactiva los permisos de retiro (withdraw) por seguridad.
          </div>
        </div>
      </div>
    </div>
  );
}
