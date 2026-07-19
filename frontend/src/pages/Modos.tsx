import { useState } from 'react';
import api from '../api';

const MODOS = [
  {
    id: 'conservador',
    emoji: '🟢',
    nombre: 'Conservador',
    descripcion: 'DCA automático + Buy & Hold + filtro de riesgo por IA. No vende automáticamente.',
    puedeReal: true,
  },
  {
    id: 'moderado',
    emoji: '🟡',
    nombre: 'Moderado',
    descripcion: 'DCA en varios activos (BTC/ETH/SOL) + rebalanceo periódico de exposición.',
    puedeReal: true,
  },
  {
    id: 'experimental',
    emoji: '🔴',
    nombre: 'Experimental',
    descripcion: 'Estrategias activas. SOLO simulación (paper trading). No usa dinero real.',
    puedeReal: false,
  },
];

export default function Modos() {
  const [modo, setModo] = useState<string>(localStorage.getItem('quantbot_modo') || 'conservador');
  const [msg, setMsg] = useState('');

  const seleccionar = (id: string) => {
    setModo(id);
    localStorage.setItem('quantbot_modo', id);
    setMsg(`Modo ${id} seleccionado. Se aplica en Mi Inversión.`);
    // Refrescar para que Inversion lea el nuevo modo
    window.dispatchEvent(new Event('modo-cambiado'));
  };

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold">Modos de Inversión</h1>

      <div className="bg-[#1e293b] border border-[#334155] p-4 rounded-xl text-sm text-slate-300">
        <b className="text-white">Filosofía honesta:</b> tras probar 7 familias de estrategias activas
        (2019–2026) en BTC/ETH/SOL, <b>ninguna mostró ventaja real</b> (profit factor 0.12–0.67).
        Por eso el sistema invierte con disciplina (DCA + hold) y solo simula lo activo.
      </div>

      {msg && <div className="bg-[#1e293b] border border-[#334155] px-4 py-2 rounded-lg text-sm text-emerald-400">{msg}</div>}

      <div className="space-y-4">
        {MODOS.map((m) => (
          <div
            key={m.id}
            className={`p-5 rounded-xl border cursor-pointer transition-colors ${
              modo === m.id
                ? 'border-emerald-500 bg-emerald-500/5'
                : 'border-[#334155] bg-[#1e293b] hover:border-slate-500'
            }`}
            onClick={() => seleccionar(m.id)}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-2xl">{m.emoji}</span>
                <div>
                  <div className="font-semibold text-white">{m.nombre}</div>
                  <div className="text-sm text-slate-400 mt-1">{m.descripcion}</div>
                </div>
              </div>
              <div className={`px-3 py-1 rounded-full text-xs ${
                modo === m.id ? 'bg-emerald-600 text-white' : 'bg-slate-700 text-slate-400'
              }`}>
                {modo === m.id ? 'Activo' : 'Seleccionar'}
              </div>
            </div>
            <div className="mt-3 text-xs">
              {m.puedeReal ? (
                <span className="text-emerald-400">✓ Puede operar con dinero real (tú decides)</span>
              ) : (
                <span className="text-amber-400">⚠ Solo simulación, sin dinero real</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
