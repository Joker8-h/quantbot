import React, { useState, useEffect } from 'react';
import api from '../api';
import { useAuth } from '../AuthContext';

interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

interface Invitation {
  id: string;
  email: string;
  used: boolean;
  expires_at: string;
  created_at: string;
}

export default function Admin() {
  const { isAdmin } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [inviteEmail, setInviteEmail] = useState('');
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!isAdmin) return;
    Promise.all([
      api.get('/admin/users'),
      api.get('/admin/invitations'),
    ]).then(([usersRes, invRes]) => {
      setUsers(usersRes.data);
      setInvitations(invRes.data);
      setLoading(false);
    });
  }, [isAdmin]);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await api.post('/admin/invite', { email: inviteEmail });
      setMessage(`Invitación enviada a ${inviteEmail}`);
      setInviteEmail('');
      setInvitations([res.data, ...invitations]);
    } catch (err: any) {
      setMessage(err.response?.data?.detail || 'Error');
    }
  };

  if (!isAdmin) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-red-400">Acceso denegado. Se requiere rol de administrador.</div>
      </div>
    );
  }

  if (loading) {
    return <div className="flex items-center justify-center h-64 text-slate-400">Cargando...</div>;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Admin</h1>

      {/* Invite Form */}
      <div className="bg-[#1e293b] p-6 rounded-xl border border-[#334155]">
        <h2 className="text-lg font-semibold mb-4">Invitar Usuario</h2>
        <form onSubmit={handleInvite} className="flex gap-3">
          <input
            type="email"
            placeholder="email@ejemplo.com"
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            className="flex-1 px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-emerald-500"
            required
          />
          <button
            type="submit"
            className="px-6 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-medium rounded-lg transition-colors"
          >
            Invitar
          </button>
        </form>
        {message && (
          <div className={`mt-3 text-sm ${message.includes('Error') ? 'text-red-400' : 'text-emerald-400'}`}>
            {message}
          </div>
        )}
      </div>

      {/* Users List */}
      <div className="bg-[#1e293b] p-6 rounded-xl border border-[#334155]">
        <h2 className="text-lg font-semibold mb-4">Usuarios ({users.length})</h2>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-left text-sm text-slate-400 border-b border-slate-700">
                <th className="pb-2">Nombre</th>
                <th className="pb-2">Email</th>
                <th className="pb-2">Rol</th>
                <th className="pb-2">Estado</th>
                <th className="pb-2">Registro</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-slate-700/50 hover:bg-slate-800/50">
                  <td className="py-3 font-medium">{u.name}</td>
                  <td className="py-3 text-sm text-slate-400">{u.email}</td>
                  <td className="py-3">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                      u.role === 'admin' ? 'bg-purple-500/20 text-purple-400' : 'bg-slate-500/20 text-slate-400'
                    }`}>
                      {u.role}
                    </span>
                  </td>
                  <td className="py-3">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                      u.is_active ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
                    }`}>
                      {u.is_active ? 'Activo' : 'Inactivo'}
                    </span>
                  </td>
                  <td className="py-3 text-sm text-slate-400">
                    {u.created_at?.substring(0, 10) || '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Invitations */}
      <div className="bg-[#1e293b] p-6 rounded-xl border border-[#334155]">
        <h2 className="text-lg font-semibold mb-4">Invitaciones ({invitations.length})</h2>
        {invitations.length === 0 ? (
          <div className="text-slate-400 text-center py-4">No hay invitaciones</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-sm text-slate-400 border-b border-slate-700">
                  <th className="pb-2">Email</th>
                  <th className="pb-2">Estado</th>
                  <th className="pb-2">Expira</th>
                  <th className="pb-2">Creada</th>
                </tr>
              </thead>
              <tbody>
                {invitations.map((inv) => (
                  <tr key={inv.id} className="border-b border-slate-700/50">
                    <td className="py-3">{inv.email}</td>
                    <td className="py-3">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                        inv.used ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'
                      }`}>
                        {inv.used ? 'Usada' : 'Pendiente'}
                      </span>
                    </td>
                    <td className="py-3 text-sm text-slate-400">{inv.expires_at?.substring(0, 10)}</td>
                    <td className="py-3 text-sm text-slate-400">{inv.created_at?.substring(0, 10)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
