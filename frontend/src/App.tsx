import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './AuthContext';
import Navbar from './components/Navbar';
import Login from './pages/Login';
import Inicio from './pages/Inicio';
import Inversion from './pages/Inversion';
import Ganancias from './pages/Ganancias';
import Sistema from './pages/Sistema';
import Cuenta from './pages/Cuenta';
import Alertas from './pages/Alertas';
import Admin from './pages/Admin';
import Modos from './pages/Modos';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" />;
  return (
    <div className="min-h-screen bg-[#0f172a]">
      <Navbar />
      <main className="max-w-7xl mx-auto px-4 py-6">{children}</main>
    </div>
  );
}

function AppRoutes() {
  const { user } = useAuth();

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" /> : <Login />} />
      <Route path="/inversion" element={<ProtectedRoute><Inversion /></ProtectedRoute>} />
      <Route path="/" element={<ProtectedRoute><Inicio /></ProtectedRoute>} />
      <Route path="/ganancias" element={<ProtectedRoute><Ganancias /></ProtectedRoute>} />
      <Route path="/sistema" element={<ProtectedRoute><Sistema /></ProtectedRoute>} />
      <Route path="/cuenta" element={<ProtectedRoute><Cuenta /></ProtectedRoute>} />
      <Route path="/modos" element={<ProtectedRoute><Modos /></ProtectedRoute>} />
      <Route path="/alertas" element={<ProtectedRoute><Alertas /></ProtectedRoute>} />
      <Route path="/admin" element={<ProtectedRoute><Admin /></ProtectedRoute>} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}

