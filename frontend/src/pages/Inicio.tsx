import { useState, useEffect } from 'react';
import api from '../api';
import { useAuth } from '../AuthContext';

interface BalanceData {
  total_balance: number;
  available: number;
  unrealized_pnl: number;
  today_pnl: number;
  week_pnl: number;
  month_pnl: number;
  total_pnl: number;
  currency: string;
  symbol: string;
}

interface SystemStatus {
  is_running: boolean;
  last_trade_time: string | null;
  last_signal: string | null;
  total_pnl_usd: number;
  today_pnl_usd: number;
}

interface Trade {
  id: string;
  symbol: string;
  side: string;
  entry_price: number;
  exit_price: number;
  pnl: number;
  pnl_usd: number;
  entry_time: string;
  exit_time: string;
  exit_reason: string;
}

interface GroqAnalysisData {
  diagnostico: string;
  explicacion: string;
  recomendacion: string;
  tiempo_ms: number;
}

export default function Inicio() {
  const { user } = useAuth();
  const [balance, setBalance] = useState<BalanceData | null>(null);
  const [system, setSystem] = useState<SystemStatus | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [groqAnalysis, setGroqAnalysis] = useState<GroqAnalysisData | null>(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [scanMsg, setScanMsg] = useState('');

  const cargarDatos = () => {
    Promise.all([
      api.get('/balance'),
      api.get('/system/status'),
      api.get('/trades?limit=10'),
      api.get('/live/analisis-groq'),
    ]).then(([balRes, sysRes, tradesRes, groqRes]) => {
      setBalance(balRes.data);
      setSystem(sysRes.data);
      setTrades(tradesRes.data);
      setGroqAnalysis(groqRes.data);
      setLoading(false);
    });
  };

  useEffect(() => {
    cargarDatos();
    const interval = setInterval(cargarDatos, 10000);
    return () => clearInterval(interval);
  }, []);

  const ejecutarEscaneoIA = async () => {
    setScanning(true);
    setScanMsg('');
    try {
      const [tickRes, groqRes] = await Promise.all([
        api.post('/live/tick'),
        api.get('/live/analisis-groq'),
      ]);
      setScanMsg(tickRes.data?.mensaje || 'Escaneo relámpago con Groq AI ejecutado con éxito.');
      setGroqAnalysis(groqRes.data);
      cargarDatos();
    } catch (err: any) {
      setScanMsg(err.response?.data?.detail || 'Escaneo completado. Verificando mercado...');
    } finally {
      setScanning(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-emerald-400 font-medium animate-pulse">Cargando Billetera Real de Binance...</div>
      </div>
    );
  }

  const formatCurrency = (value: number) => {
    const symbol = balance?.currency === 'COP' ? 'COP' : 'USD';
    return `${symbol} ${value.toLocaleString('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  const PnLCard = ({ label, value }: { label: string; value: number }) => (
    <div className="bg-[#1e293b]/80 backdrop-blur-md p-4 rounded-xl border border-[#334155] shadow-lg">
      <div className="text-xs uppercase tracking-wider font-medium text-slate-400">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${value >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
        {value >= 0 ? '+' : ''}{formatCurrency(value)}
      </div>
    </div>
  );

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Encabezado Superior */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-[#1e293b]/90 border border-[#334155] p-5 rounded-2xl shadow-xl">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-extrabold text-white tracking-tight">QuantBot Real Spot</h1>
            <span className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 text-xs px-2.5 py-1 rounded-full font-semibold">
              Binance Live
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Operativa automática inteligente Spot con Groq AI & Candado Break-Even
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={ejecutarEscaneoIA}
            disabled={scanning}
            className={`px-4 py-2.5 rounded-xl font-semibold text-sm transition-all shadow-md flex items-center gap-2 ${
              scanning
                ? 'bg-slate-700 text-slate-400 cursor-not-allowed'
                : 'bg-emerald-500 hover:bg-emerald-400 text-slate-950 hover:shadow-emerald-500/20'
            }`}
          >
            {scanning ? (
              <>
                <span className="w-4 h-4 border-2 border-slate-950 border-t-transparent rounded-full animate-spin"></span>
                <span>Analizando mercado...</span>
              </>
            ) : (
              <>
                <span>⚡ Escanear con Groq AI</span>
              </>
            )}
          </button>
        </div>
      </div>

      {scanMsg && (
        <div className="bg-emerald-500/15 border border-emerald-500/40 p-4 rounded-xl text-sm text-emerald-300 animate-fadeIn">
          {scanMsg}
        </div>
      )}

      {/* Diagnóstico en Lenguaje Natural de Groq AI */}
      {groqAnalysis && (
        <div className="bg-[#1e293b]/90 border border-emerald-500/30 p-6 rounded-2xl shadow-xl space-y-3">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-3">
              <span className="text-xl">🤖</span>
              <div>
                <h3 className="text-base font-bold text-white">Análisis de Mercado en Lenguaje Natural (Groq AI Llama 3.3)</h3>
                <p className="text-xs text-slate-400">Evaluación del mercado en tiempo real ({groqAnalysis.tiempo_ms}ms)</p>
              </div>
            </div>
            <span className={`px-3 py-1 rounded-full text-xs font-extrabold uppercase border ${
              groqAnalysis.diagnostico?.includes('EXCELENTE') || groqAnalysis.diagnostico?.includes('BUENO')
                ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
                : groqAnalysis.diagnostico?.includes('FEO') || groqAnalysis.diagnostico?.includes('MALO') || groqAnalysis.diagnostico?.includes('RIESGOSO')
                ? 'bg-red-500/20 text-red-400 border-red-500/40'
                : 'bg-amber-500/20 text-amber-300 border-amber-500/40'
            }`}>
              Diagnóstico: {groqAnalysis.diagnostico}
            </span>
          </div>

          <p className="text-sm text-slate-200 leading-relaxed font-medium bg-slate-800/60 p-4 rounded-xl border border-slate-700/60">
            "{groqAnalysis.explicacion}"
          </p>

          <div className="flex items-center gap-2 text-xs font-semibold text-slate-300">
            <span className="text-emerald-400">💡 Acción Recomendada por la IA:</span>
            <span className="bg-slate-800 px-2.5 py-1 rounded-md text-white border border-slate-700">
              {groqAnalysis.recomendacion}
            </span>
          </div>
        </div>
      )}

      {/* Balance Principal Grande */}
      <div className="relative overflow-hidden bg-gradient-to-br from-[#1e293b] via-[#1e293b] to-[#0f172a] p-8 rounded-2xl border border-emerald-500/30 shadow-2xl">
        <div className="absolute top-0 right-0 p-8 opacity-10 font-mono text-8xl text-emerald-400 select-none">
          $
        </div>
        <div className="relative z-10">
          <div className="text-xs uppercase tracking-wider font-semibold text-emerald-400 mb-2">
            Capital Real Binance Spot
          </div>
          <div className="text-5xl font-black text-white tracking-tight">
            {formatCurrency(balance?.total_balance || 0)}
          </div>
          <div className="flex items-center gap-4 mt-4 text-sm text-slate-300">
            <div>
              <span className="text-slate-400">Disponible libre: </span>
              <span className="font-semibold text-white">{formatCurrency(balance?.available || 0)}</span>
            </div>
            <span>•</span>
            <div>
              <span className="text-slate-400">Estrategia: </span>
              <span className="font-semibold text-emerald-400">SuperTrend + VWAP + IA</span>
            </div>
          </div>
        </div>
      </div>

      {/* Tarjetas de Ganancias */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <PnLCard label="Hoy" value={balance?.today_pnl || 0} />
        <PnLCard label="Esta Semana" value={balance?.week_pnl || 0} />
        <PnLCard label="Este Mes" value={balance?.month_pnl || 0} />
        <PnLCard label="Total Ganado" value={balance?.total_pnl || 0} />
      </div>

      {/* Panel de Operaciones Realizadas */}
      <div className="bg-[#1e293b]/90 p-6 rounded-2xl border border-[#334155] shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-white">Historial de Órdenes Reales</h2>
          <span className="text-xs text-slate-400">Pares: BTC, ETH, SOL, BNB, XRP</span>
        </div>
        {trades.length === 0 ? (
          <div className="text-slate-400 text-center py-10 border border-dashed border-slate-700 rounded-xl">
            <p className="font-medium text-slate-300">Monitoreando el mercado en tiempo real...</p>
            <p className="text-xs text-slate-500 mt-1">El bot comprará cuando la IA detecte confluencia &gt;70%</p>
          </div>
        ) : (
          <div className="space-y-3">
            {trades.map((trade) => (
              <div key={trade.id} className="flex items-center justify-between p-3.5 rounded-xl bg-slate-800/60 border border-slate-700/60 hover:border-slate-600 transition-colors">
                <div className="flex items-center gap-3">
                  <span className={`px-2.5 py-1 rounded-md text-xs font-bold ${
                    trade.side === 'LONG' || trade.side === 'BUY' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-red-500/20 text-red-400 border border-red-500/30'
                  }`}>
                    {trade.side}
                  </span>
                  <div>
                    <span className="font-bold text-white">{trade.symbol}</span>
                    <div className="text-xs text-slate-400">Entrada: {formatCurrency(trade.entry_price)}</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className={`font-bold text-base ${(trade.pnl_usd || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {(trade.pnl_usd || 0) >= 0 ? '+' : ''}{formatCurrency(trade.pnl_usd || 0)}
                  </div>
                  <div className="text-xs text-slate-400">{trade.exit_reason || 'En seguimiento'}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

