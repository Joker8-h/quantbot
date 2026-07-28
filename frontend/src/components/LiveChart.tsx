import { useState, useEffect, useRef, useMemo } from 'react';

/**
 * Grafico de velas EN VIVO conectado directo al WebSocket publico de Binance.
 *
 * - Historial inicial: REST https://api.binance.com/api/v3/klines
 * - Actualizacion en vivo: wss://stream.binance.com:9443/ws/<sym>@kline_<intv>
 * - Corre 100% en el navegador del usuario: sin backend, sin credenciales.
 *   Las velas son las REALES del mercado (mainnet), las mismas que ve Binance.
 */

interface Vela {
  t: number;   // open time (ms)
  o: number;
  h: number;
  l: number;
  c: number;
}

const SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT'];
const INTERVALOS: { label: string; value: string }[] = [
  { label: '1m', value: '1m' },
  { label: '5m', value: '5m' },
  { label: '15m', value: '15m' },
  { label: '1h', value: '1h' },
];
const LIMITE = 90;

const fmt = (n: number) =>
  n >= 1000
    ? n.toLocaleString('en-US', { maximumFractionDigits: 2 })
    : n.toLocaleString('en-US', { maximumFractionDigits: 4 });

export default function LiveChart() {
  const [symbol, setSymbol] = useState('BTC/USDT');
  const [intervalo, setIntervalo] = useState('1m');
  const [velas, setVelas] = useState<Vela[]>([]);
  const [conectado, setConectado] = useState(false);
  const [error, setError] = useState('');
  const wsRef = useRef<WebSocket | null>(null);

  const binSym = symbol.replace('/', '').toLowerCase();

  useEffect(() => {
    let cancelado = false;
    setError('');
    setVelas([]);
    setConectado(false);

    // 1. Historial inicial via REST
    const cargarHistorial = async () => {
      try {
        const url = `https://api.binance.com/api/v3/klines?symbol=${binSym.toUpperCase()}&interval=${intervalo}&limit=${LIMITE}`;
        const r = await fetch(url);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data: any[] = await r.json();
        if (cancelado) return;
        setVelas(
          data.map((k) => ({
            t: k[0],
            o: parseFloat(k[1]),
            h: parseFloat(k[2]),
            l: parseFloat(k[3]),
            c: parseFloat(k[4]),
          }))
        );
      } catch (e: any) {
        if (!cancelado) setError('No se pudo cargar el historial de Binance.');
      }
    };

    cargarHistorial();

    // 2. Stream en vivo via WebSocket
    const ws = new WebSocket(`wss://stream.binance.com:9443/ws/${binSym}@kline_${intervalo}`);
    wsRef.current = ws;

    ws.onopen = () => !cancelado && setConectado(true);
    ws.onclose = () => !cancelado && setConectado(false);
    ws.onerror = () => !cancelado && setError('Conexión con Binance interrumpida.');

    ws.onmessage = (msg) => {
      if (cancelado) return;
      try {
        const d = JSON.parse(msg.data);
        const k = d.k;
        if (!k) return;
        const nueva: Vela = {
          t: k.t,
          o: parseFloat(k.o),
          h: parseFloat(k.h),
          l: parseFloat(k.l),
          c: parseFloat(k.c),
        };
        setVelas((prev) => {
          if (prev.length === 0) return [nueva];
          const ultima = prev[prev.length - 1];
          if (ultima.t === nueva.t) {
            // misma vela en formacion: reemplazar
            const copia = prev.slice();
            copia[copia.length - 1] = nueva;
            return copia;
          }
          // vela nueva: agregar y recortar
          return [...prev.slice(-(LIMITE - 1)), nueva];
        });
      } catch {
        /* ignorar frames malformados */
      }
    };

    return () => {
      cancelado = true;
      try {
        ws.close();
      } catch {
        /* noop */
      }
    };
  }, [binSym, intervalo]);

  const ultima = velas[velas.length - 1];
  const primeraVisible = velas[0];
  const cambioPct =
    ultima && primeraVisible ? ((ultima.c - primeraVisible.o) / primeraVisible.o) * 100 : 0;
  const subiendo = cambioPct >= 0;

  // Geometria del SVG
  const ancho = 900;
  const alto = 340;
  const padTop = 12;
  const padBot = 24;
  const padRight = 62;

  const { paths, gridLines, minP, maxP } = useMemo(() => {
    if (velas.length === 0) return { paths: [], gridLines: [], minP: 0, maxP: 0 };
    const lows = velas.map((v) => v.l);
    const highs = velas.map((v) => v.h);
    let minP = Math.min(...lows);
    let maxP = Math.max(...highs);
    const margen = (maxP - minP) * 0.08 || maxP * 0.001;
    minP -= margen;
    maxP += margen;

    const areaW = ancho - padRight;
    const areaH = alto - padTop - padBot;
    const n = velas.length;
    const paso = areaW / n;
    const cuerpoW = Math.max(1.5, paso * 0.62);

    const y = (p: number) => padTop + ((maxP - p) / (maxP - minP)) * areaH;

    const paths = velas.map((v, i) => {
      const cx = i * paso + paso / 2;
      const alcista = v.c >= v.o;
      const yO = y(v.o);
      const yC = y(v.c);
      const cuerpoTop = Math.min(yO, yC);
      const cuerpoH = Math.max(1, Math.abs(yC - yO));
      return {
        key: v.t,
        cx,
        wickTop: y(v.h),
        wickBot: y(v.l),
        cuerpoX: cx - cuerpoW / 2,
        cuerpoTop,
        cuerpoW,
        cuerpoH,
        color: alcista ? '#10b981' : '#ef4444',
      };
    });

    const gridLines = Array.from({ length: 5 }, (_, i) => {
      const p = minP + ((maxP - minP) * i) / 4;
      return { p, y: y(p) };
    });

    return { paths, gridLines, minP, maxP };
  }, [velas]);

  return (
    <div className="bg-[#1e293b] p-4 md:p-6 rounded-xl border border-[#334155]">
      {/* Encabezado */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold">Mercado en vivo</h2>
          <span
            className={`flex items-center gap-1.5 text-xs px-2 py-1 rounded-full ${
              conectado ? 'bg-emerald-500/20 text-emerald-400' : 'bg-slate-600/30 text-slate-400'
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${conectado ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'}`} />
            {conectado ? 'En vivo' : 'Conectando...'}
          </span>
        </div>
        {ultima && (
          <div className="text-right">
            <div className="text-2xl font-bold tabular-nums">${fmt(ultima.c)}</div>
            <div className={`text-sm font-medium ${subiendo ? 'text-emerald-400' : 'text-red-400'}`}>
              {subiendo ? '▲' : '▼'} {Math.abs(cambioPct).toFixed(2)}%
            </div>
          </div>
        )}
      </div>

      {/* Selectores */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <div className="flex gap-1">
          {SYMBOLS.map((s) => (
            <button
              key={s}
              onClick={() => setSymbol(s)}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                symbol === s ? 'bg-emerald-600 text-white' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
              }`}
            >
              {s.replace('/USDT', '')}
            </button>
          ))}
        </div>
        <div className="flex gap-1 ml-auto">
          {INTERVALOS.map((iv) => (
            <button
              key={iv.value}
              onClick={() => setIntervalo(iv.value)}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                intervalo === iv.value ? 'bg-blue-600 text-white' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
              }`}
            >
              {iv.label}
            </button>
          ))}
        </div>
      </div>

      {/* Grafico */}
      {error ? (
        <div className="h-[340px] flex items-center justify-center text-sm text-red-400 text-center px-4">
          {error}
        </div>
      ) : velas.length === 0 ? (
        <div className="h-[340px] flex items-center justify-center text-sm text-slate-400">
          Cargando velas...
        </div>
      ) : (
        <div className="overflow-x-auto">
          <svg viewBox={`0 0 ${ancho} ${alto}`} className="w-full" style={{ minWidth: 320 }}>
            {/* Grid + etiquetas de precio */}
            {gridLines.map((g, i) => (
              <g key={i}>
                <line x1={0} y1={g.y} x2={ancho - padRight} y2={g.y} stroke="#334155" strokeWidth={0.5} strokeDasharray="3 3" />
                <text x={ancho - padRight + 6} y={g.y + 4} fill="#64748b" fontSize={11} className="tabular-nums">
                  {fmt(g.p)}
                </text>
              </g>
            ))}
            {/* Velas */}
            {paths.map((p) => (
              <g key={p.key}>
                <line x1={p.cx} y1={p.wickTop} x2={p.cx} y2={p.wickBot} stroke={p.color} strokeWidth={1} />
                <rect x={p.cuerpoX} y={p.cuerpoTop} width={p.cuerpoW} height={p.cuerpoH} fill={p.color} />
              </g>
            ))}
            {/* Linea de precio actual */}
            {ultima && (
              <line
                x1={0}
                y1={padTop + ((maxP - ultima.c) / (maxP - minP)) * (alto - padTop - padBot)}
                x2={ancho - padRight}
                y2={padTop + ((maxP - ultima.c) / (maxP - minP)) * (alto - padTop - padBot)}
                stroke={subiendo ? '#10b981' : '#ef4444'}
                strokeWidth={0.75}
                strokeDasharray="4 2"
                opacity={0.6}
              />
            )}
          </svg>
        </div>
      )}
      <div className="text-xs text-slate-500 mt-2">
        Datos en tiempo real de Binance · {symbol} · velas de {intervalo}. Estas son las mismas velas
        que analiza el motor para decidir sus entradas.
      </div>
    </div>
  );
}
