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
  const [testnet, setTestnet] = useState(true);
  const [conectado, setConectado] = useState(false);
  const [modoConexion, setModoConexion] = useState<string>('');
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
      setModoConexion(r.data.modo || '');
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
        testnet,
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

        {!conectado && (
          <>
            {/* Selector Testnet / Real */}
            <div className="flex gap-3 mb-4">
              <button
                onClick={() => setTestnet(true)}
                className={`flex-1 px-4 py-3 rounded-lg font-medium transition-colors ${
                  testnet ? 'bg-emerald-600 text-white' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                }`}
              >
                🧪 Práctica (Testnet)
              </button>
              <button
                onClick={() => setTestnet(false)}
                className={`flex-1 px-4 py-3 rounded-lg font-medium transition-colors ${
                  !testnet ? 'bg-emerald-600 text-white' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                }`}
              >
                💵 Real
              </button>
            </div>

            {testnet ? (
              <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-3 text-sm text-blue-300 mb-4 space-y-1">
                <p className="font-semibold text-blue-200">Cómo obtener tus llaves de práctica (dinero ficticio):</p>
                <ol className="list-decimal list-inside space-y-1">
                  <li>Entra a <a href="https://testnet.binance.vision/" target="_blank" rel="noreferrer" className="underline">testnet.binance.vision</a> e inicia sesión con GitHub.</li>
                  <li>Pulsa <b>Generate HMAC_SHA256 Key</b>.</li>
                  <li>Copia la <b>API Key</b> y el <b>Secret</b> (el secret solo se muestra una vez).</li>
                  <li>Pégalos abajo. El saldo ficticio se crea solo.</li>
                </ol>
              </div>
            ) : (
              <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 text-sm text-amber-400 mb-4">
                ⚠️ Crea la API Key en Binance con permisos de <b>lectura + Spot Trading</b> y
                <b> SIN retiro (withdraw)</b>. El bot nunca retira fondos.
              </div>
            )}
          </>
        )}

        {conectado ? (
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-emerald-400">
              <span>✅</span> Cuenta conectada y cifrada
              {modoConexion && (
                <span className={`ml-2 px-2 py-0.5 rounded text-xs ${
                  modoConexion === 'testnet' ? 'bg-blue-500/20 text-blue-300' : 'bg-amber-500/20 text-amber-300'
                }`}>
                  {modoConexion === 'testnet' ? '🧪 Testnet' : '💵 Real'}
                </span>
              )}
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
