import pandas as pd
import sys
sys.stdout.reconfigure(encoding='utf-8')

trades = pd.read_csv('trades.csv')
print('=== OPERACIONES ===')
print(trades.to_string())
print()
print('=== RESUMEN ===')
print(f'Total: {len(trades)}')
print(f'Todas salieron por stop_loss: {(trades.exit_reason == "stop_loss").all()}')

# Leer el equity curve
eq = pd.read_csv('equity_curve.csv')
print(f'\n=== EQUITY CURVE ===')
print(f'Datos: {len(eq)} registros')
print(f'Capital min: ${eq.equity.min():.4f}')
print(f'Capital max: ${eq.equity.max():.4f}')

# Verificar senales
df = pd.read_csv('data/raw/BTC_USDT_1h.csv')
print(f'\n=== DATOS ===')
print(f'Total velas: {len(df)}')
print(f'Rango: {df.datetime.iloc[0]} a {df.datetime.iloc[-1]}')
