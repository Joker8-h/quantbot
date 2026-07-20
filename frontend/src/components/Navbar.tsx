import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import { getCurrency, setCurrency } from '../currency';

const navItems = [
  { path: '/inversion', label: 'Inversión', icon: '📊' },
  { path: '/modos', label: 'Modos', icon: '🎚️' },
  { path: '/', label: 'Inicio', icon: '🏠' },
  { path: '/ganancias', label: 'Ganancias', icon: '💰' },
  { path: '/sistema', label: 'Sistema', icon: '⚙️' },
  { path: '/cuenta', label: 'Cuenta', icon: '👤' },
  { path: '/alertas', label: 'Alertas', icon: '🔔' },
];

export default function Navbar() {
  const { user, logout, isAdmin } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const currency = getCurrency();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const toggleCurrency = () => {
    setCurrency(currency === 'USD' ? 'COP' : 'USD');
    navigate(0); // refrescar para aplicar
  };

  return (
    <nav className="bg-[#1e293b] border-b border-[#334155] px-4 py-3">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <div className="flex items-center gap-6">
          <Link to="/" className="text-xl font-bold text-emerald-400">
            QuantBot
          </Link>
          <div className="hidden md:flex items-center gap-4">
            {navItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  location.pathname === item.path
                    ? 'bg-emerald-600 text-white'
                    : 'text-slate-300 hover:bg-slate-700'
                }`}
              >
                {item.label}
              </Link>
            ))}
            {isAdmin && (
              <Link
                to="/admin"
                className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  location.pathname === '/admin'
                    ? 'bg-emerald-600 text-white'
                    : 'text-slate-300 hover:bg-slate-700'
                }`}
              >
                Admin
              </Link>
            )}
          </div>
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={toggleCurrency}
            className="px-3 py-1.5 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
            title="Cambiar divisa"
          >
            {currency === 'USD' ? '💵 USD' : '💴 COP'}
          </button>
          <span className="text-sm text-slate-400">{user?.name}</span>
          <button
            onClick={handleLogout}
            className="px-3 py-1.5 text-sm text-slate-300 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
          >
            Salir
          </button>
        </div>
      </div>
    </nav>
  );
}

