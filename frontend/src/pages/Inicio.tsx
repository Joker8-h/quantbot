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

export default function Inicio() {
  const { user } = useAuth();
  const [balance, setBalance] = useState<BalanceData | null>(null);
  const [system, setSystem] = useState<SystemStatus | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get('/balance'),
      api.get('/system/status'),
      api.get('/trades?limit=10'),
    ]).then(([balRes, sysRes, tradesRes]) => {
      setBalance(balRes.data);
      setSystem(sysRes.data);
      setTrades(tradesRes.data);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-400">Cargando...</div>
      </div>
    );
  }

  const formatCurrency = (value: number) => {
    const symbol = balance?.currency === 'COP' ? 'COP' : 'USD';
    return `${symbol} ${value.toLocaleString('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  const PnLCard = ({ label, value }: { label: string; value: number }) => (
    <div className="bg-[#1e293b] p-4 rounded-xl border border-[#334155]">
      <div className="text-sm text-slate-400">{label}</div>
      <div className={`text-xl font-bold ${value >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
        {value >= 0 ? '+' : ''}{formatCurrency(value)}
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Inicio</h1>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${system?.is_running ? 'bg-emerald-400' : 'bg-red-400'}`}></span>
          <span className="text-sm text-slate-400">{system?.is_running ? 'Activo' : 'Pausado'}</span>
        </div>
      </div>

      {/* Balance Principal */}
      <div className="bg-[#1e293b] p-6 rounded-xl border border-[#334155]">
        <div className="text-sm text-slate-400 mb-1">Balance Total</div>
        <div className="text-4xl font-bold text-white">{formatCurrency(balance?.total_balance || 0)}</div>
        <div className="text-sm text-slate-400 mt-1">Disponible: {formatCurrency(balance?.available || 0)}</div>
      </div>

      {/* PnL Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <PnLCard label="Hoy" value={balance?.today_pnl || 0} />
        <PnLCard label="Esta Semana" value={balance?.week_pnl || 0} />
        <PnLCard label="Este Mes" value={balance?.month_pnl || 0} />
        <PnLCard label="Total" value={balance?.total_pnl || 0} />
      </div>

      {/* Últimas Operaciones */}
      <div className="bg-[#1e293b] p-6 rounded-xl border border-[#334155]">
        <h2 className="text-lg font-semibold mb-4">Últimas Operaciones</h2>
        {trades.length === 0 ? (
          <div className="text-slate-400 text-center py-8">No hay operaciones aún</div>
        ) : (
          <div className="space-y-3">
            {trades.slice(0, 5).map((trade) => (
              <div key={trade.id} className="flex items-center justify-between py-2 border-b border-slate-700 last:border-0">
                <div className="flex items-center gap-3">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                    trade.side === 'LONG' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
                  }`}>
                    {trade.side}
                  </span>
                  <span className="text-slate-300">{trade.symbol}</span>
                </div>
                <div className="text-right">
                  <div className={`font-medium ${(trade.pnl_usd || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {(trade.pnl_usd || 0) >= 0 ? '+' : ''}{formatCurrency(trade.pnl_usd || 0)}
                  </div>
                  <div className="text-xs text-slate-500">{trade.exit_reason}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

