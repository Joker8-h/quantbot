import { useState, useEffect } from 'react';
import api from '../api';
import { useAuth } from '../AuthContext';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

interface Stats {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  profit_factor: number;
  gross_profit: number;
  gross_loss: number;
}

interface Trade {
  id: string;
  symbol: string;
  side: string;
  entry_price: number;
  exit_price: number;
  pnl: number;
  pnl_usd: number;
  fee: number;
  entry_time: string;
  exit_time: string;
  exit_reason: string;
}

export default function Ganancias() {
  const { user } = useAuth();
  const [stats, setStats] = useState<Stats | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get('/stats'),
      api.get('/trades?limit=100'),
    ]).then(([statsRes, tradesRes]) => {
      setStats(statsRes.data);
      setTrades(tradesRes.data);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return <div className="flex items-center justify-center h-64 text-slate-400">Cargando...</div>;
  }

  const formatCurrency = (value: number) => {
    return `USD ${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  // Prepare monthly data for chart
  const monthlyData: Record<string, number> = {};
  trades.forEach((t) => {
    if (t.exit_time) {
      const month = t.exit_time.substring(0, 7);
      monthlyData[month] = (monthlyData[month] || 0) + (t.pnl_usd || 0);
    }
  });
  const chartData = Object.entries(monthlyData).map(([month, pnl]) => ({ month, pnl }));

  // Win/Loss pie
  const pieData = [
    { name: 'Ganadas', value: stats?.winning_trades || 0, color: '#10b981' },
    { name: 'Perdidas', value: stats?.losing_trades || 0, color: '#ef4444' },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Ganancias</h1>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-[#1e293b] p-4 rounded-xl border border-[#334155]">
          <div className="text-sm text-slate-400">Total Operaciones</div>
          <div className="text-2xl font-bold">{stats?.total_trades || 0}</div>
        </div>
        <div className="bg-[#1e293b] p-4 rounded-xl border border-[#334155]">
          <div className="text-sm text-slate-400">Win Rate</div>
          <div className="text-2xl font-bold text-emerald-400">{stats?.win_rate || 0}%</div>
        </div>
        <div className="bg-[#1e293b] p-4 rounded-xl border border-[#334155]">
          <div className="text-sm text-slate-400">Profit Factor</div>
          <div className="text-2xl font-bold">{stats?.profit_factor || 0}</div>
        </div>
        <div className="bg-[#1e293b] p-4 rounded-xl border border-[#334155]">
          <div className="text-sm text-slate-400">Ganancia Bruta</div>
          <div className="text-2xl font-bold text-emerald-400">{formatCurrency(stats?.gross_profit || 0)}</div>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-[#1e293b] p-6 rounded-xl border border-[#334155]">
          <h2 className="text-lg font-semibold mb-4">PnL Mensual</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <XAxis dataKey="month" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 12 }} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
                  labelStyle={{ color: '#94a3b8' }}
                />
                <Bar dataKey="pnl" fill="#10b981" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-[#1e293b] p-6 rounded-xl border border-[#334155]">
          <h2 className="text-lg font-semibold mb-4">Win/Loss</h2>
          <div className="h-64 flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={80}
                  dataKey="value"
                  label={({ name, value }) => `${name}: ${value}`}
                >
                  {pieData.map((entry, index) => (
                    <Cell key={index} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Recent Trades Table */}
      <div className="bg-[#1e293b] p-6 rounded-xl border border-[#334155]">
        <h2 className="text-lg font-semibold mb-4">Historial de Operaciones</h2>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-left text-sm text-slate-400 border-b border-slate-700">
                <th className="pb-2">Fecha</th>
                <th className="pb-2">Tipo</th>
                <th className="pb-2">Entrada</th>
                <th className="pb-2">Salida</th>
                <th className="pb-2">Razón</th>
                <th className="pb-2 text-right">PnL</th>
              </tr>
            </thead>
            <tbody>
              {trades.slice(0, 20).map((trade) => (
                <tr key={trade.id} className="border-b border-slate-700/50 hover:bg-slate-800/50">
                  <td className="py-3 text-sm">{trade.exit_time?.substring(0, 10) || '-'}</td>
                  <td className="py-3">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                      trade.side === 'LONG' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
                    }`}>
                      {trade.side}
                    </span>
                  </td>
                  <td className="py-3 text-sm">${trade.entry_price?.toLocaleString()}</td>
                  <td className="py-3 text-sm">${trade.exit_price?.toLocaleString()}</td>
                  <td className="py-3 text-sm text-slate-400">{trade.exit_reason}</td>
                  <td className={`py-3 text-sm text-right font-medium ${(trade.pnl_usd || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {(trade.pnl_usd || 0) >= 0 ? '+' : ''}{formatCurrency(trade.pnl_usd || 0)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

