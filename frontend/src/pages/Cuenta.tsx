import { useState, useEffect } from 'react';
import api from '../api';
import { useAuth } from '../AuthContext';

export default function Cuenta() {
  const { user } = useAuth();
  const [currency, setCurrency] = useState(user?.currency_preference || 'USD');
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  // Binance
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [conectado, setConectado] = useState(false);
  const [saldoUsdt, setSaldoUsdt] = useState<number | null>(null);
  const [conectando, setConectando] = useState(false);
  const [probando, setProbando] = useState(false);
  const [resultadoPrueba, setResultadoPrueba] = useState('');

  useEffect(() => {
    cargarEstado();
  }, []);

  const cargarEstado = async () => {
    try {
      const r = await api.get('/exchange/status');
      setConectado(!!r.data.conectado);
    } catch {
      setConectado(false);
    }
  };

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

  const conectar = async () => {
    setConectando(true);
    setMessage('');
    try {
      const r = await api.post('/exchange/connect', {
        api_key: apiKey,
        api_secret: apiSecret,
        exchange: 'binance',
        paper: true,
      });
      setConectado(true);
      setSaldoUsdt(r.data.saldo_usdt);
      setApiKey('');
      setApiSecret('');
      setMessage(r.data.mensaje || 'Conectado');
    } catch (err: any) {
      setMessage(err.response?.data?.detail || 'Error al conectar');
    } finally {
      setConectando(false);
    }
  };

  const desconectar = async () => {
    try {
      await api.delete('/exchange/disconnect');
      setConectado(false);
      setSaldoUsdt(null);
      setMessage('Conexión eliminada');
    } catch {
      setMessage('Error al desconectar');
    }
  };

  const pruebaCompra = async () => {
    setProbando(true);
    setResultadoPrueba('');
    try {
      const r = await api.post('/exchange/test-buy?symbol=BTC/USDT&monto_usd=10&paper=true');
      setResultadoPrueba(JSON.stringify(r.data, null, 2));
    } catch (err: any) {
      setResultadoPrueba(err.response?.data?.detail || 'Error en prueba');
    } finally {
      setProbando(false);
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
        <h2 className="text-lg font-semibold mb-4">Conexión con Binance</h2>

        <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 text-sm text-amber-400 mb-4">
          ⚠️ Crea la API Key en Binance con permisos de <b>lectura + Spot Trading</b> y
          <b> SIN retiro (withdraw)</b>. El bot nunca retira fondos.
        </div>

        {conectado ? (
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-emerald-400">
              <span>✅</span> Cuenta conectada y cifrada
            </div>
            {saldoUsdt !== null && (
              <div className="text-sm text-slate-300">Saldo disponible: ${saldoUsdt.toFixed(2)} USDT</div>
            )}
            <div className="flex gap-3">
              <button
                onClick={pruebaCompra}
                disabled={probando}
                className="px-5 py-3 rounded-lg bg-blue-600 hover:bg-blue-500 font-medium"
              >
                {probando ? 'Probando...' : 'Prueba de compra (PAPER $10)'}
              </button>
              <button
                onClick={desconectar}
                className="px-5 py-3 rounded-lg bg-red-600 hover:bg-red-500 font-medium"
              >
                Desconectar
              </button>
            </div>
            {resultadoPrueba && (
              <pre className="bg-slate-900 p-3 rounded-lg text-xs text-slate-300 overflow-auto whitespace-pre-wrap">
                {resultadoPrueba}
              </pre>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            <input
              type="password"
              placeholder="Binance API Key"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="w-full px-4 py-3 rounded-lg bg-slate-800 border border-slate-600 text-white"
            />
            <input
              type="password"
              placeholder="Binance API Secret"
              value={apiSecret}
              onChange={(e) => setApiSecret(e.target.value)}
              className="w-full px-4 py-3 rounded-lg bg-slate-800 border border-slate-600 text-white"
            />
            <button
              onClick={conectar}
              disabled={conectando || !apiKey || !apiSecret}
              className="px-6 py-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 font-medium disabled:opacity-50"
            >
              {conectando ? 'Conectando...' : 'Conectar Binance'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
