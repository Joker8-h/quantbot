import React, { useState, useEffect } from 'react';
import api from '../api';
import { useAuth } from '../AuthContext';

interface SystemStatus {
  is_running: boolean;
  last_trade_time: string | null;
  last_signal: string | null;
  total_pnl_usd: number;
  today_pnl_usd: number;
}

export default function Sistema() {
  const { user } = useAuth();
  const [system, setSystem] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);

  useEffect(() => {
    api.get('/system/status').then((res) => {
      setSystem(res.data);
      setLoading(false);
    });
  }, []);

  const toggleSystem = async () => {
    setToggling(true);
    try {
      if (system?.is_running) {
        await api.post('/system/pause');
        setSystem({ ...system!, is_running: false });
      } else {
        await api.post('/system/resume');
        setSystem({ ...system!, is_running: true });
      }
    } finally {
      setToggling(false);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64 text-slate-400">Cargando...</div>;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Sistema</h1>

      {/* Status Card */}
      <div className="bg-[#1e293b] p-6 rounded-xl border border-[#334155]">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-lg font-semibold">Estado del Sistema</h2>
            <p className="text-sm text-slate-400">Controla el bot de trading</p>
          </div>
          <div className={`flex items-center gap-2 px-4 py-2 rounded-full ${
            system?.is_running ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
          }`}>
            <span className={`w-2 h-2 rounded-full ${system?.is_running ? 'bg-emerald-400' : 'bg-red-400'}`}></span>
            {system?.is_running ? 'Activo' : 'Pausado'}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 mb-6">
          <div className="bg-slate-800/50 p-4 rounded-lg">
            <div className="text-sm text-slate-400">Última Operación</div>
            <div className="text-lg font-medium mt-1">
              {system?.last_trade_time
                ? new Date(system.last_trade_time).toLocaleString('es-CO')
                : 'Sin operaciones'}
            </div>
          </div>
          <div className="bg-slate-800/50 p-4 rounded-lg">
            <div className="text-sm text-slate-400">Última Señal</div>
            <div className="text-lg font-medium mt-1">
              {system?.last_signal || 'Sin señales'}
            </div>
          </div>
        </div>

        <button
          onClick={toggleSystem}
          disabled={toggling}
          className={`w-full py-3 rounded-lg font-medium transition-colors ${
            system?.is_running
              ? 'bg-red-600 hover:bg-red-700 text-white'
              : 'bg-emerald-600 hover:bg-emerald-700 text-white'
          } disabled:opacity-50`}
        >
          {toggling ? 'Procesando...' : system?.is_running ? 'Pausar Sistema' : 'Activar Sistema'}
        </button>
      </div>

      {/* Config Info */}
      <div className="bg-[#1e293b] p-6 rounded-xl border border-[#334155]">
        <h2 className="text-lg font-semibold mb-4">Configuración Actual</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-slate-800/50 p-4 rounded-lg">
            <div className="text-sm text-slate-400">Par</div>
            <div className="text-lg font-medium mt-1">BTC/USDT</div>
          </div>
          <div className="bg-slate-800/50 p-4 rounded-lg">
            <div className="text-sm text-slate-400">Temporalidad</div>
            <div className="text-lg font-medium mt-1">1H</div>
          </div>
          <div className="bg-slate-800/50 p-4 rounded-lg">
            <div className="text-sm text-slate-400">Capital</div>
            <div className="text-lg font-medium mt-1">USD 100.00</div>
          </div>
          <div className="bg-slate-800/50 p-4 rounded-lg">
            <div className="text-sm text-slate-400">Riesgo por Trade</div>
            <div className="text-lg font-medium mt-1">2%</div>
          </div>
        </div>
      </div>

      {/* Indicadores */}
      <div className="bg-[#1e293b] p-6 rounded-xl border border-[#334155]">
        <h2 className="text-lg font-semibold mb-4">Indicadores</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <div className="bg-slate-800/50 p-4 rounded-lg">
            <div className="text-sm text-slate-400">EMA Rápida</div>
            <div className="text-lg font-medium mt-1">9</div>
          </div>
          <div className="bg-slate-800/50 p-4 rounded-lg">
            <div className="text-sm text-slate-400">EMA Lenta</div>
            <div className="text-lg font-medium mt-1">21</div>
          </div>
          <div className="bg-slate-800/50 p-4 rounded-lg">
            <div className="text-sm text-slate-400">RSI Período</div>
            <div className="text-lg font-medium mt-1">14</div>
          </div>
          <div className="bg-slate-800/50 p-4 rounded-lg">
            <div className="text-sm text-slate-400">ATR Período</div>
            <div className="text-lg font-medium mt-1">14</div>
          </div>
          <div className="bg-slate-800/50 p-4 rounded-lg">
            <div className="text-sm text-slate-400">SL ATR</div>
            <div className="text-lg font-medium mt-1">3.0</div>
          </div>
          <div className="bg-slate-800/50 p-4 rounded-lg">
            <div className="text-sm text-slate-400">TP ATR</div>
            <div className="text-lg font-medium mt-1">1.5</div>
          </div>
        </div>
      </div>
    </div>
  );
}
