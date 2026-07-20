import { useState, useEffect } from 'react';
import api from '../api';
import { formatMoney } from '../currency';

interface ActivoData {
  symbol: string;
  precio: number;
  riesgo: string;
  riesgo_emoji: string;
  capital_invertido: number;
  valor_actual: number;
  ganancia_pct: number;
  peso_pct: number;
}

interface PortfolioData {
  symbol?: string;
  multi?: boolean;
  activos?: ActivoData[];
  precio?: number;
  riesgo: string;
  riesgo_emoji: string;
  accion: string;
  razon: string;
  capital_invertido: number;
  valor_actual: number;
  ganancia: number;
  ganancia_pct: number;
  pausado: boolean;
  proxima_compra: string;
  total_compras: number;
  // Modo Experimental (paper trading)
  paper?: boolean;
  capital_inicial?: number;
  valor_final?: number;
  retorno_pct?: number;
  retorno_hold_pct?: number;
  valor_hold?: number;
  supero_hold?: boolean;
  drawdown_pct?: number;
  trades?: number;
  advertencia?: string;
  ventana_dias?: number;
}

const RIESGO_COLOR: Record<string, string> = {
  low: 'text-emerald-400',
  medium: 'text-yellow-400',
  high: 'text-red-400',
};

const RIESGO_BG: Record<string, string> = {
  low: 'bg-emerald-500/10 border-emerald-500/30',
  medium: 'bg-yellow-500/10 border-yellow-500/30',
  high: 'bg-red-500/10 border-red-500/30',
};

export default function Inversion() {
  const [data, setData] = useState<PortfolioData | null>(null);
  const [loading, setLoading] = useState(true);
  const [pausando, setPausando] = useState(false);
  const [msg, setMsg] = useState('');
  const [modo, setModo] = useState<string>(localStorage.getItem('quantbot_modo') || 'conservador');

  const cargar = () => {
    setLoading(true);
    const params = modo === 'moderado'
      ? `/portfolio?modo=moderado&symbols=BTC/USDT,ETH/USDT,SOL/USDT`
      : `/portfolio?modo=${modo}`;
    api.get(params).then((res) => {
      setData(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => {
    cargar();
    const onCambio = () => setModo(localStorage.getItem('quantbot_modo') || 'conservador');
    window.addEventListener('modo-cambiado', onCambio);
    return () => window.removeEventListener('modo-cambiado', onCambio);
  }, []);

  const togglePausa = () => {
    setPausando(true);
    api.post(`/dca/pause?pausado=${!data?.pausado}`).then(() => {
      setPausando(false);
      setMsg(data?.pausado ? 'Inversión reanudada' : 'Inversión pausada');
      cargar();
    });
  };

  const ejecutarCompra = () => {
    api.post('/dca/execute').then((r) => {
      setMsg(r.data.ok ? `Compra de $${r.data.compra.monto_usd} registrada` : r.data.mensaje);
      cargar();
    });
  };

  if (loading || !data) {
    return <div className="flex items-center justify-center h-64"><div className="text-slate-400">Cargando...</div></div>;
  }

  const fmt = (v: number) => formatMoney(v);
  const gananciaColor = (data.ganancia || 0) >= 0 ? 'text-emerald-400' : 'text-red-400';

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold">Mi Inversión</h1>

      <div className="flex gap-2">
        {['conservador', 'moderado', 'experimental'].map((m) => (
          <button
            key={m}
            onClick={() => { setModo(m); localStorage.setItem('quantbot_modo', m); cargar(); }}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-colors ${
              modo === m ? 'bg-emerald-600 text-white' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
            }`}
          >
            {m}
          </button>
        ))}
      </div>

      {msg && <div className="bg-[#1e293b] border border-[#334155] px-4 py-2 rounded-lg text-sm text-slate-300">{msg}</div>}

      {/* Estado de riesgo */}
      <div className={`p-5 rounded-xl border ${RIESGO_BG[data.riesgo] || 'border-[#334155]'}`}>
        <div className="flex items-center gap-3">
          <span className="text-3xl">{data.riesgo_emoji}</span>
          <div>
            <div className={`text-lg font-bold ${RIESGO_COLOR[data.riesgo] || 'text-white'}`}>
              Riesgo {data.riesgo === 'low' ? 'normal' : data.riesgo === 'medium' ? 'medio' : 'alto'}
            </div>
            <div className="text-sm text-slate-300">{data.accion}</div>
          </div>
        </div>
        {data.razon && <div className="text-xs text-slate-400 mt-3">🤖 {data.razon}</div>}
      </div>

      {/* Valor de la inversión */}
      <div className="bg-[#1e293b] p-6 rounded-xl border border-[#334155] text-center">
        <div className="text-sm text-slate-400 mb-1">Mi Inversión ({data.symbol})</div>
        <div className="text-4xl font-bold text-white">{fmt(data.valor_actual)}</div>
        <div className={`text-lg font-semibold mt-2 ${gananciaColor}`}>
          {(data.ganancia || 0) >= 0 ? '+' : ''}{fmt(data.ganancia)} ({data.ganancia_pct}%)
        </div>
        <div className="text-xs text-slate-500 mt-2">
          Invertido: {fmt(data.capital_invertido)} · {data.total_compras} compras acumuladas
        </div>
      </div>

      {/* Distribución multi-activo (Modo Moderado) */}
      {data.multi && data.activos && (
        <div className="bg-[#1e293b] p-5 rounded-xl border border-[#334155]">
          <div className="text-sm text-slate-400 mb-3">Distribución de exposición</div>
          <div className="space-y-3">
            {data.activos.map((a) => (
              <div key={a.symbol}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-white font-medium">{a.symbol}</span>
                  {(() => {
                    const gp = a.ganancia_pct ?? 0;
                    return <span className="text-slate-400">{a.peso_pct}% · {gp >= 0 ? '+' : ''}{gp}%</span>;
                  })()}
                </div>
                <div className="w-full bg-slate-800 rounded-full h-2">
                  <div
                    className="bg-emerald-500 h-2 rounded-full"
                    style={{ width: `${Math.max(a.peso_pct ?? 0, 3)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Próxima compra */}
      <div className="bg-[#1e293b] p-4 rounded-xl border border-[#334155] flex items-center justify-between">
        <div>
          <div className="text-sm text-slate-400">Próxima compra programada</div>
          <div className="text-white font-medium">{data.proxima_compra}</div>
        </div>
        <div className="text-sm text-slate-400">Precio actual: {fmt(data.precio ?? 0)}</div>
      </div>

      {/* Modo Experimental: simulación PAPER */}
      {modo === 'experimental' && data.paper && (
        <div className="space-y-4">
          <div className="bg-red-500/10 border border-red-500/30 p-4 rounded-xl">
            <div className="text-sm font-semibold text-red-300">🔴 Modo Experimental · Solo simulación</div>
            <div className="text-xs text-slate-300 mt-1">{data.advertencia}</div>
          </div>

          <div className="bg-[#1e293b] p-6 rounded-xl border border-[#334155] text-center">
            <div className="text-sm text-slate-400 mb-1">Resultado simulado ({data.symbol})</div>
            <div className="text-4xl font-bold text-white">{fmt(data.valor_final ?? 0)}</div>
            <div className={`text-lg font-semibold mt-2 ${(data.retorno_pct ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              {(data.retorno_pct ?? 0) >= 0 ? '+' : ''}{data.retorno_pct}%
            </div>
            <div className="text-xs text-slate-500 mt-2">
              Capital inicial: {fmt(data.capital_inicial ?? 0)} · {data.trades} operaciones simuladas
            </div>
          </div>

          <div className="bg-[#1e293b] p-5 rounded-xl border border-[#334155] space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-400">Estrategia activa (90 días)</span>
              <span className={(data.retorno_pct ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                {data.retorno_pct}%
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Solo comprar y mantener</span>
              <span className={(data.retorno_hold_pct ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                {data.retorno_hold_pct}%
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Caída máxima (drawdown)</span>
              <span className="text-red-400">{data.drawdown_pct}%</span>
            </div>
            <div className="pt-2 border-t border-[#334155] text-xs text-slate-400">
              {data.supero_hold
                ? 'En este periodo la estrategia superó al hold, pero históricamente no ha demostrado ventaja sostenida.'
                : 'En este periodo la estrategia no superó al simple hold.'}
            </div>
          </div>
        </div>
      )}

      {/* Acciones (solo conservador/moderado) */}
      {modo !== 'experimental' && (
      <div className="flex gap-3">
        <button
          onClick={ejecutarCompra}
          disabled={data.pausado}
          className="flex-1 px-4 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 disabled:text-slate-400 rounded-xl font-medium transition-colors"
        >
          Comprar ahora (DCA)
        </button>
        <button
          onClick={togglePausa}
          disabled={pausando}
          className="flex-1 px-4 py-3 bg-slate-700 hover:bg-slate-600 rounded-xl font-medium transition-colors"
        >
          {data.pausado ? 'Reanudar inversión' : 'Pausar inversión'}
        </button>
      </div>
      )}

      <p className="text-xs text-slate-500 text-center leading-relaxed">
        No intentamos adivinar el mercado. Invertimos con disciplina (DCA) y reducimos el
        riesgo de tomar malas decisiones emocionales. La IA solo avisa cuando el riesgo es alto.
      </p>
    </div>
  );
}

