import { useState, useEffect } from 'react';
import api from '../api';

interface AlertConfig {
  [key: string]: {
    whatsapp: boolean;
    telegram: boolean;
  };
}

interface Contact {
  phone: string | null;
  telegram_chat_id: string | null;
}

export default function Alertas() {
  const [alerts, setAlerts] = useState<AlertConfig>({});
  const [contact, setContact] = useState<Contact>({ phone: null, telegram_chat_id: null });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testingTelegram, setTestingTelegram] = useState(false);
  const [telegramMessage, setTelegramMessage] = useState('');
  const [testingWhatsapp, setTestingWhatsapp] = useState(false);
  const [whatsappMessage, setWhatsappMessage] = useState('');
  const [whatsappStatus, setWhatsappStatus] = useState<string>('checking');

  const alertTypes = [
    { key: 'trade_closed', label: 'Operación Cerrada', desc: 'Cuando se cierra una operación' },
    { key: 'daily_profit', label: 'Resumen Diario', desc: 'Resumen de ganancias del día' },
    { key: 'weekly_report', label: 'Reporte Semanal', desc: 'Estadísticas de la semana' },
    { key: 'system_pause', label: 'Sistema Pausado', desc: 'Cuando el sistema se pausa automáticamente' },
    { key: 'large_loss', label: 'Pérdida Grande', desc: 'Cuando una pérdida supera el umbral' },
    { key: 'system_error', label: 'Error del Sistema', desc: 'Cuando hay un error en el sistema' },
  ];

  useEffect(() => {
    api.get('/alerts').then((res) => {
      setAlerts(res.data.alerts);
      setContact(res.data.contact);
      setLoading(false);
    });
    api.get('/alerts/whatsapp-status').then((res) => {
      setWhatsappStatus(res.data.status || 'offline');
    }).catch(() => setWhatsappStatus('offline'));
  }, []);

  const toggleAlert = async (alertType: string, channel: string) => {
    setSaving(true);
    try {
      const isActive = !alerts[alertType]?.[channel as 'whatsapp' | 'telegram'];
      await api.put('/alerts/toggle', { alert_type: alertType, channel, is_active: isActive });
      setAlerts({
        ...alerts,
        [alertType]: {
          ...alerts[alertType],
          [channel]: isActive,
        },
      });
    } finally {
      setSaving(false);
    }
  };

  const updateContact = async (field: string, value: string) => {
    await api.put('/alerts/contact', { [field]: value });
    setContact({ ...contact, [field]: value });
  };

  const testTelegram = async () => {
    setTestingTelegram(true);
    setTelegramMessage('');
    try {
      await api.post('/alerts/test-telegram');
      setTelegramMessage('✅ Mensaje enviado! Revisa tu Telegram.');
    } catch (err) {
      setTelegramMessage('❌ Error al enviar. Verifica la configuración.');
    } finally {
      setTestingTelegram(false);
    }
  };

  const testWhatsapp = async () => {
    setTestingWhatsapp(true);
    setWhatsappMessage('');
    try {
      await api.post('/alerts/test-whatsapp');
      setWhatsappMessage('✅ Mensaje enviado! Revisa tu WhatsApp.');
    } catch (err) {
      setWhatsappMessage('❌ Error al enviar. Verifica que el servicio esté corriendo.');
    } finally {
      setTestingWhatsapp(false);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64 text-slate-400">Cargando...</div>;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Alertas</h1>

      {/* Contact Info */}
      <div className="bg-[#1e293b] p-6 rounded-xl border border-[#334155]">
        <h2 className="text-lg font-semibold mb-4">Información de Contacto</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-slate-400 mb-1">Teléfono WhatsApp</label>
            <input
              type="text"
              placeholder="+57 300 123 4567"
              value={contact.phone || ''}
              onChange={(e) => updateContact('phone', e.target.value)}
              className="w-full px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-emerald-500"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1">Chat ID Telegram</label>
            <input
              type="text"
              placeholder="123456789"
              value={contact.telegram_chat_id || ''}
              onChange={(e) => updateContact('telegram_chat_id', e.target.value)}
              className="w-full px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-emerald-500"
            />
          </div>
        </div>
      </div>

      {/* Alerts Table */}
      <div className="bg-[#1e293b] p-6 rounded-xl border border-[#334155]">
        <h2 className="text-lg font-semibold mb-4">Configuración de Alertas</h2>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-left text-sm text-slate-400 border-b border-slate-700">
                <th className="pb-2">Alerta</th>
                <th className="pb-2">Descripción</th>
                <th className="pb-2 text-center">WhatsApp</th>
                <th className="pb-2 text-center">Telegram</th>
              </tr>
            </thead>
            <tbody>
              {alertTypes.map((at) => (
                <tr key={at.key} className="border-b border-slate-700/50 hover:bg-slate-800/50">
                  <td className="py-3 font-medium">{at.label}</td>
                  <td className="py-3 text-sm text-slate-400">{at.desc}</td>
                  <td className="py-3 text-center">
                    <button
                      onClick={() => toggleAlert(at.key, 'whatsapp')}
                      disabled={saving}
                      className={`w-10 h-6 rounded-full transition-colors ${
                        alerts[at.key]?.whatsapp ? 'bg-emerald-500' : 'bg-slate-600'
                      }`}
                    >
                      <div className={`w-4 h-4 bg-white rounded-full transition-transform mx-1 ${
                        alerts[at.key]?.whatsapp ? 'translate-x-4' : 'translate-x-0'
                      }`}></div>
                    </button>
                  </td>
                  <td className="py-3 text-center">
                    <button
                      onClick={() => toggleAlert(at.key, 'telegram')}
                      disabled={saving}
                      className={`w-10 h-6 rounded-full transition-colors ${
                        alerts[at.key]?.telegram ? 'bg-emerald-500' : 'bg-slate-600'
                      }`}
                    >
                      <div className={`w-4 h-4 bg-white rounded-full transition-transform mx-1 ${
                        alerts[at.key]?.telegram ? 'translate-x-4' : 'translate-x-0'
                      }`}></div>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Channel Status */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-[#1e293b] p-6 rounded-xl border border-[#334155]">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 bg-green-500 rounded-lg flex items-center justify-center text-white text-xl">📱</div>
            <div>
              <div className="font-medium">WhatsApp Web</div>
              <div className={`text-sm ${whatsappStatus === 'ready' ? 'text-emerald-400' : 'text-amber-400'}`}>
                {whatsappStatus === 'ready' ? 'Conectado' : whatsappStatus === 'checking' ? 'Verificando...' : 'Desconectado'}
              </div>
            </div>
          </div>
          {whatsappStatus === 'ready' ? (
            <button
              onClick={testWhatsapp}
              disabled={testingWhatsapp}
              className="w-full py-2 bg-green-600 hover:bg-green-700 text-white font-medium rounded-lg transition-colors disabled:opacity-50"
            >
              {testingWhatsapp ? 'Enviando...' : 'Probar WhatsApp'}
            </button>
          ) : (
            <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 text-sm text-amber-400">
              Servicio offline. Ejecutá <code>cd whatsapp-service && npm start</code> y escaneá el QR.
            </div>
          )}
          {whatsappMessage && (
            <div className={`mt-3 text-sm ${whatsappMessage.includes('✅') ? 'text-emerald-400' : 'text-red-400'}`}>
              {whatsappMessage}
            </div>
          )}
        </div>
        <div className="bg-[#1e293b] p-6 rounded-xl border border-[#334155]">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 bg-blue-500 rounded-lg flex items-center justify-center text-white text-xl">✈️</div>
            <div>
              <div className="font-medium">Telegram Bot</div>
              <div className="text-sm text-emerald-400">Configurado y activo</div>
            </div>
          </div>
          <button
            onClick={testTelegram}
            disabled={testingTelegram}
            className="w-full py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors disabled:opacity-50"
          >
            {testingTelegram ? 'Enviando...' : 'Probar Telegram'}
          </button>
          {telegramMessage && (
            <div className={`mt-3 text-sm ${telegramMessage.includes('✅') ? 'text-emerald-400' : 'text-red-400'}`}>
              {telegramMessage}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

