import { useState, useEffect } from 'react';
import api from '../api';

interface PortfolioData {
  symbol: string;
  precio: number;
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

  const cargar = () => {
    api.get('/portfolio').then((res) => {
      setData(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => { cargar(); }, []);

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

  const fmt = (v: number) => `$${v.toLocaleString('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  const gananciaColor = (data.ganancia || 0) >= 0 ? 'text-emerald-400' : 'text-red-400';

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold">Mi Inversión</h1>

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

      {/* Próxima compra */}
      <div className="bg-[#1e293b] p-4 rounded-xl border border-[#334155] flex items-center justify-between">
        <div>
          <div className="text-sm text-slate-400">Próxima compra programada</div>
          <div className="text-white font-medium">{data.proxima_compra}</div>
        </div>
        <div className="text-sm text-slate-400">Precio actual: {fmt(data.precio)}</div>
      </div>

      {/* Acciones */}
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

      <p className="text-xs text-slate-500 text-center leading-relaxed">
        No intentamos adivinar el mercado. Invertimos con disciplina (DCA) y reducimos el
        riesgo de tomar malas decisiones emocionales. La IA solo avisa cuando el riesgo es alto.
      </p>
    </div>
  );
}

