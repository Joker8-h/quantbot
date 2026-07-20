import { useState, useEffect } from 'react';
import api from '../api';

interface Hoy {
  ganancia: number;
  perdida: number;
  neto: number;
  operaciones: number;
  abiertas: number;
  promedio: number;
}

interface PosicionAbierta {
  symbol: string;
  entry_price: number;
  quantity: number;
  entry_time: string | null;
}

interface Trade {
  id: string;
  symbol: string;
  side: string;
  entry_price: number;
  exit_price: number | null;
  pnl_usd: number | null;
  exit_reason: string | null;
  status: string;
  entry_time: string | null;
  exit_time: string | null;
}

interface Estado {
  conectado_testnet: boolean;
  is_running: boolean;
  symbol: string;
  monto_usd: number;
  max_trades_dia: number;
  max_perdida_pct_dia: number;
  last_trade_time: string | null;
  last_signal: string | null;
  total_pnl_usd: number;
  total_operaciones: number;
  hoy: Hoy;
  posicion_abierta: PosicionAbierta | null;
}

const money = (n: number | null | undefined) =>
  n === null || n === undefined ? '—' : `$${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function Paper() {
  const [estado, setEstado] = useState<Estado | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');

  const cargar = async () => {
    try {
      const [e, t] = await Promise.all([
        api.get('/paper/status'),
        api.get('/trades?limit=20'),
      ]);
      setEstado(e.data);
      setTrades(t.data);
    } catch {
      /* noop */
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    cargar();
    const id = setInterval(cargar, 30000);
    return () => clearInterval(id);
  }, []);

  const toggle = async () => {
    if (!estado) return;
    setBusy(true);
    setMsg('');
    try {
      const r = await api.post(estado.is_running ? '/paper/stop' : '/paper/start');
      setMsg(r.data.mensaje || '');
      await cargar();
    } catch (err: any) {
      setMsg(err.response?.data?.detail || 'Error');
    } finally {
      setBusy(false);
    }
  };

  const tickAhora = async () => {
    setBusy(true);
    setMsg('');
    try {
      const r = await api.post('/paper/tick');
      const res = r.data.resultado;
      setMsg(`Ciclo ejecutado: ${res.accion} — ${res.razon}`);
      await cargar();
    } catch (err: any) {
      setMsg(err.response?.data?.detail || 'Error');
    } finally {
      setBusy(false);
    }
  };

  const reporte = async () => {
    setBusy(true);
    setMsg('');
    try {
      const r = await api.post('/paper/report');
      setMsg(r.data.ok ? 'Resumen enviado a Telegram ✅' : 'No se pudo enviar');
    } catch (err: any) {
      setMsg(err.response?.data?.detail || 'Error');
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64 text-slate-400">Cargando...</div>;
  }

  const running = estado?.is_running;
  const neto = estado?.hoy.neto ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">🧪 Modo Paper Trading</h1>
        <div
          className={`flex items-center gap-2 px-4 py-2 rounded-full ${
            running ? 'bg-emerald-500/20 text-emerald-400' : 'bg-slate-600/30 text-slate-400'
          }`}
        >
          <span className={`w-2 h-2 rounded-full ${running ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'}`}></span>
          {running ? 'Activo' : 'Pausado'}
        </div>
      </div>

      <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 text-sm text-amber-400">
        💡 Dinero <b>ficticio</b> (Spot Testnet de Binance). Ideal para practicar sin riesgo.
        Las estrategias activas no han demostrado ventaja histórica: esto es educativo.
      </div>

      {!estado?.conectado_testnet && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-sm text-red-300">
          No tienes una cuenta <b>Testnet</b> conectada. Ve a <b>Cuenta → Conexión con Binance</b>,
          elige <b>Práctica (Testnet)</b> y pega tus llaves de testnet.binance.vision.
        </div>
      )}

      {/* Metricas del dia */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-[#1e293b] p-4 rounded-xl border border-[#334155]">
          <div className="text-sm text-slate-400">Ganancia hoy</div>
          <div className="text-xl font-bold mt-1 text-emerald-400">{money(estado?.hoy.ganancia)}</div>
        </div>
        <div className="bg-[#1e293b] p-4 rounded-xl border border-[#334155]">
          <div className="text-sm text-slate-400">Pérdida hoy</div>
          <div className="text-xl font-bold mt-1 text-red-400">{money(estado?.hoy.perdida)}</div>
        </div>
        <div className="bg-[#1e293b] p-4 rounded-xl border border-[#334155]">
          <div className="text-sm text-slate-400">Neto hoy</div>
          <div className={`text-xl font-bold mt-1 ${neto >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            {money(neto)}
          </div>
        </div>
        <div className="bg-[#1e293b] p-4 rounded-xl border border-[#334155]">
          <div className="text-sm text-slate-400">Operaciones hoy</div>
          <div className="text-xl font-bold mt-1">{estado?.hoy.operaciones}</div>
        </div>
      </div>

      {/* Resumen general */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-[#1e293b] p-4 rounded-xl border border-[#334155]">
          <div className="text-sm text-slate-400">P&L total</div>
          <div className={`text-lg font-medium mt-1 ${(estado?.total_pnl_usd ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            {money(estado?.total_pnl_usd)}
          </div>
        </div>
        <div className="bg-[#1e293b] p-4 rounded-xl border border-[#334155]">
          <div className="text-sm text-slate-400">Total operaciones</div>
          <div className="text-lg font-medium mt-1">{estado?.total_operaciones}</div>
        </div>
        <div className="bg-[#1e293b] p-4 rounded-xl border border-[#334155]">
          <div className="text-sm text-slate-400">Promedio/op hoy</div>
          <div className="text-lg font-medium mt-1">{money(estado?.hoy.promedio)}</div>
        </div>
        <div className="bg-[#1e293b] p-4 rounded-xl border border-[#334155]">
          <div className="text-sm text-slate-400">Última señal</div>
          <div className="text-lg font-medium mt-1">{estado?.last_signal || '—'}</div>
        </div>
      </div>

      {/* Posicion abierta */}
      {estado?.posicion_abierta && (
        <div className="bg-[#1e293b] p-6 rounded-xl border border-emerald-600/40">
          <h2 className="text-lg font-semibold mb-3">Posición abierta</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
            <div>
              <div className="text-slate-400">Par</div>
              <div className="font-medium mt-1">{estado.posicion_abierta.symbol}</div>
            </div>
            <div>
              <div className="text-slate-400">Precio de entrada</div>
              <div className="font-medium mt-1">{money(estado.posicion_abierta.entry_price)}</div>
            </div>
            <div>
              <div className="text-slate-400">Cantidad</div>
              <div className="font-medium mt-1">{estado.posicion_abierta.quantity}</div>
            </div>
          </div>
        </div>
      )}

      {/* Controles */}
      <div className="bg-[#1e293b] p-6 rounded-xl border border-[#334155] space-y-4">
        <div className="flex flex-wrap gap-3">
          <button
            onClick={toggle}
            disabled={busy || !estado?.conectado_testnet}
            className={`px-5 py-3 rounded-lg font-medium transition-colors disabled:opacity-50 ${
              running ? 'bg-red-600 hover:bg-red-700 text-white' : 'bg-emerald-600 hover:bg-emerald-700 text-white'
            }`}
          >
            {busy ? 'Procesando...' : running ? 'Pausar motor' : 'Activar motor'}
          </button>
          <button
            onClick={tickAhora}
            disabled={busy || !running}
            className="px-5 py-3 rounded-lg bg-blue-600 hover:bg-blue-500 font-medium disabled:opacity-50"
          >
            Ejecutar ciclo ahora
          </button>
          <button
            onClick={reporte}
            disabled={busy}
            className="px-5 py-3 rounded-lg bg-slate-700 hover:bg-slate-600 font-medium disabled:opacity-50"
          >
            Enviar resumen a Telegram
          </button>
        </div>
        {msg && <div className="text-sm text-emerald-400">{msg}</div>}
        <div className="text-xs text-slate-500">
          Par: {estado?.symbol} · Compra: {money(estado?.monto_usd)} · Límite diario: {estado?.max_trades_dia} ops /
          −{estado?.max_perdida_pct_dia}%
        </div>
      </div>

      {/* Historial */}
      <div className="bg-[#1e293b] p-6 rounded-xl border border-[#334155]">
        <h2 className="text-lg font-semibold mb-4">Últimas operaciones</h2>
        {trades.length === 0 ? (
          <div className="text-sm text-slate-400">Aún no hay operaciones.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-slate-400 text-left border-b border-slate-700">
                  <th className="py-2 pr-4">Par</th>
                  <th className="py-2 pr-4">Entrada</th>
                  <th className="py-2 pr-4">Salida</th>
                  <th className="py-2 pr-4">P&L</th>
                  <th className="py-2 pr-4">Estado</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t) => (
                  <tr key={t.id} className="border-b border-slate-800">
                    <td className="py-2 pr-4">{t.symbol}</td>
                    <td className="py-2 pr-4">{money(t.entry_price)}</td>
                    <td className="py-2 pr-4">{money(t.exit_price)}</td>
                    <td className={`py-2 pr-4 ${(t.pnl_usd ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {t.pnl_usd === null ? '—' : money(t.pnl_usd)}
                    </td>
                    <td className="py-2 pr-4">
                      <span
                        className={`px-2 py-0.5 rounded text-xs ${
                          t.status === 'open' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-slate-600/30 text-slate-300'
                        }`}
                      >
                        {t.status === 'open' ? 'Abierta' : 'Cerrada'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
