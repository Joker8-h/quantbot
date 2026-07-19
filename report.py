import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import sys
sys.stdout.reconfigure(encoding='utf-8')

trades = pd.read_csv('trades.csv')
equity = pd.read_csv('equity_curve.csv')
equity['datetime'] = pd.to_datetime(equity['datetime'])

fig, axes = plt.subplots(3, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [3, 1, 1]})

# 1. Equity Curve
ax1 = axes[0]
ax1.plot(equity['datetime'], equity['equity'], color='#2196F3', linewidth=1)
ax1.axhline(y=10, color='gray', linestyle='--', alpha=0.5, label='Capital Inicial')
ax1.fill_between(equity['datetime'], 10, equity['equity'], 
                  where=equity['equity'] >= 10, alpha=0.3, color='green')
ax1.fill_between(equity['datetime'], 10, equity['equity'], 
                  where=equity['equity'] < 10, alpha=0.3, color='red')
ax1.set_title('QuantBot - Equity Curve (BTC/USDT 1h)', fontsize=14, fontweight='bold')
ax1.set_ylabel('Capital ($)')
ax1.legend()
ax1.grid(True, alpha=0.3)

# 2. Drawdown
peak = equity['equity'].cummax()
drawdown = (equity['equity'] - peak) / peak * 100
ax2 = axes[1]
ax2.fill_between(equity['datetime'], 0, drawdown, color='red', alpha=0.5)
ax2.set_title('Drawdown (%)', fontsize=12)
ax2.set_ylabel('Drawdown %')
ax2.grid(True, alpha=0.3)

# 3. Trade PnL
ax3 = axes[2]
colors = ['green' if x > 0 else 'red' for x in trades['pnl']]
ax3.bar(range(len(trades)), trades['pnl'], color=colors, alpha=0.7)
ax3.axhline(y=0, color='gray', linestyle='-', alpha=0.5)
ax3.set_title('PnL por Operacion', fontsize=12)
ax3.set_xlabel('Operacion #')
ax3.set_ylabel('PnL ($)')
ax3.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('backtest_results.png', dpi=150, bbox_inches='tight')
print('Grafica guardada: backtest_results.png')

# Resumen estadistico
print('\n' + '='*60)
print('  RESUMEN ESTADISTICO DETALLADO')
print('='*60)

print(f'\n--- RENDIMIENTO ---')
print(f'Capital inicial:      ${trades.iloc[0]["entry_price"]*0 + 10:.2f}')
print(f'Capital final:        ${equity["equity"].iloc[-1]:.2f}')
print(f'PnL total:            ${trades["pnl"].sum():.4f}')
print(f'Rentabilidad:         {trades["pnl"].sum()/10*100:.2f}%')
print(f'Anios de datos:       {(equity["datetime"].iloc[-1] - equity["datetime"].iloc[0]).days / 365:.1f}')

print(f'\n--- OPERACIONES ---')
print(f'Total operaciones:    {len(trades)}')
print(f'Ganadoras:            {len(trades[trades["pnl"]>0])} ({len(trades[trades["pnl"]>0])/len(trades)*100:.1f}%)')
print(f'Perdedoras:           {len(trades[trades["pnl"]<=0])} ({len(trades[trades["pnl"]<=0])/len(trades)*100:.1f}%)')
print(f'Win Rate:             {len(trades[trades["pnl"]>0])/len(trades)*100:.1f}%')

print(f'\n--- GANANCIAS ---')
avg_win = trades[trades["pnl"]>0]["pnl"].mean()
avg_loss = trades[trades["pnl"]<=0]["pnl"].mean()
print(f'Ganancia promedio:    ${avg_win:.4f}')
print(f'Perdida promedio:     ${avg_loss:.4f}')
print(f'Mejor trade:          ${trades["pnl"].max():.4f}')
print(f'Peor trade:           ${trades["pnl"].min():.4f}')
print(f'Ratio ganancia/perdida: {abs(avg_win/avg_loss):.2f}')

print(f"\n--- RATIOS ---")
gross_profit = trades[trades["pnl"]>0]["pnl"].sum()
gross_loss = abs(trades[trades["pnl"]<=0]["pnl"].sum())
pf = gross_profit / gross_loss if gross_loss > 0 else 0
print(f'Profit Factor:        {pf:.2f}')

equity_returns = equity['equity'].pct_change().dropna()
if len(equity_returns) > 1 and equity_returns.std() > 0:
    sharpe = (equity_returns.mean() / equity_returns.std()) * (8760**0.5)
else:
    sharpe = 0
print(f'Sharpe Ratio:         {sharpe:.2f}')

peak_eq = equity['equity'].cummax()
dd = (equity['equity'] - peak_eq) / peak_eq
max_dd = dd.min() * 100
print(f'Max Drawdown:         {max_dd:.2f}%')

print(f"\n--- COSTOS ---")
print(f'Fees totales:         ${trades["fee"].sum():.4f}')
print(f'Fees por trade:       ${trades["fee"].mean():.4f}')

print(f"\n--- SALIDAS ---")
for reason, count in trades["exit_reason"].value_counts().items():
    print(f'  {reason:<20} {count} ({count/len(trades)*100:.1f}%)')

# Analisis por anio
trades['year'] = pd.to_datetime(trades['entry_time']).dt.year
print(f"\n--- RENDIMIENTO POR ANIO ---")
for year, group in trades.groupby('year'):
    yr_pnl = group['pnl'].sum()
    yr_trades = len(group)
    yr_wr = len(group[group['pnl']>0]) / yr_trades * 100 if yr_trades > 0 else 0
    print(f'  {year}: PnL=${yr_pnl:.4f} | Trades={yr_trades} | WR={yr_wr:.0f}%')
