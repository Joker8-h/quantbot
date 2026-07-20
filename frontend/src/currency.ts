import api from './api';

// Tasa de cambio USD -> COP (se actualiza desde el backend)
let USD_TO_COP_RATE = 4200;

export async function fetchRate() {
  try {
    const r = await api.get('/config/rate');
    if (r.data?.rate) USD_TO_COP_RATE = r.data.rate;
  } catch {
    // usar valor por defecto
  }
  return USD_TO_COP_RATE;
}

export function getRate() {
  return USD_TO_COP_RATE;
}

// Devuelve la moneda preferida del usuario (USD por defecto)
export function getCurrency(): 'USD' | 'COP' {
  const c = localStorage.getItem('currency');
  return c === 'COP' ? 'COP' : 'USD';
}

export function setCurrency(c: 'USD' | 'COP') {
  localStorage.setItem('currency', c);
  window.dispatchEvent(new Event('currency-changed'));
}

// Convierte USD a la moneda preferida y formatea
export function formatMoney(usd: number): string {
  const cur = getCurrency();
  if (cur === 'COP') {
    const cop = usd * USD_TO_COP_RATE;
    return `COP ${cop.toLocaleString('es-CO', { maximumFractionDigits: 0 })}`;
  }
  return `USD ${usd.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

// Para valores que ya vienen en la moneda actual del usuario
export function formatCurrencyRaw(value: number, currency: 'USD' | 'COP' = 'USD'): string {
  if (currency === 'COP') {
    return `COP ${value.toLocaleString('es-CO', { maximumFractionDigits: 0 })}`;
  }
  return `USD ${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
