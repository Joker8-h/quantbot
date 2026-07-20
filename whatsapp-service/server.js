const { Client, LocalAuth } = require('whatsapp-web.js');
const express = require('express');
const cors = require('cors');
const qrcode = require('qrcode-terminal');

const app = express();
app.use(cors());
app.use(express.json());

let client = null;
let qrCode = null;
let isReady = false;

function initClient() {
    client = new Client({
        authStrategy: new LocalAuth({ dataPath: './auth_data' }),
        puppeteer: {
            headless: true,
            executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || undefined,
            args: ['--no-sandbox', '--disable-setuid-sandbox'],
        },
    });

    client.on('qr', (qr) => {
        console.log('QR Code received:');
        qrcode.generate(qr, { small: true });
        qrCode = qr;
        isReady = false;
    });

    client.on('ready', () => {
        console.log('WhatsApp client is ready!');
        isReady = true;
        qrCode = null;
    });

    client.on('authenticated', () => {
        console.log('Authenticated');
    });

    client.on('auth_failure', (msg) => {
        console.error('Auth failure:', msg);
        isReady = false;
    });

    client.on('disconnected', (reason) => {
        console.log('Client disconnected:', reason);
        isReady = false;
        qrCode = null;
    });

    client.initialize();
}

// Health check
app.get('/health', (req, res) => {
    res.json({ status: 'ok', whatsapp: isReady });
});

// Get QR code
app.get('/qr', (req, res) => {
    if (isReady) {
        res.json({ status: 'ready', qr: null });
    } else if (qrCode) {
        res.json({ status: 'waiting', qr: qrCode });
    } else {
        res.json({ status: 'initializing', qr: null });
    }
});

// Send message
app.post('/send', async (req, res) => {
    if (!isReady) {
        return res.status(503).json({ error: 'WhatsApp not ready' });
    }

    const { phone, message } = req.body;

    if (!phone || !message) {
        return res.status(400).json({ error: 'phone and message required' });
    }

    // Format phone (remove +, spaces, dashes)
    const chatId = phone.replace(/[^0-9]/g, '') + '@c.us';

    try {
        await client.sendMessage(chatId, message);
        console.log(`Message sent to ${phone}`);
        res.json({ success: true });
    } catch (err) {
        console.error('Send error:', err.message);
        res.status(500).json({ error: err.message });
    }
});

// Send to predefined group/contact (for QuantBot alerts)
app.post('/alert', async (req, res) => {
    if (!isReady) {
        return res.status(503).json({ error: 'WhatsApp not ready' });
    }

    const { message, groupId } = req.body;
    const target = groupId || process.env.WHATSAPP_GROUP_ID || process.env.WHATSAPP_PHONE;

    if (!target) {
        return res.status(400).json({ error: 'No target configured. Set WHATSAPP_GROUP_ID or WHATSAPP_PHONE' });
    }

    const chatId = target.includes('@') ? target : target.replace(/[^0-9]/g, '') + '@c.us';

    try {
        await client.sendMessage(chatId, message);
        console.log(`Alert sent to ${target}`);
        res.json({ success: true });
    } catch (err) {
        console.error('Alert error:', err.message);
        res.status(500).json({ error: err.message });
    }
});

// QR page
app.get('/', (req, res) => {
    res.send(`
        <html>
        <head><title>QuantBot WhatsApp</title></head>
        <body style="background:#0f172a;color:#f1f5f9;font-family:sans-serif;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0">
            <div style="text-align:center">
                <h1 style="color:#10b981">QuantBot WhatsApp</h1>
                <div id="status">Cargando...</div>
                <div id="qr" style="margin-top:20px"></div>
            </div>
            <script>
                async function check() {
                    const r = await fetch('/qr');
                    const d = await r.json();
                    if (d.status === 'ready') {
                        document.getElementById('status').innerHTML = '<span style="color:#10b981">✅ Conectado!</span>';
                        document.getElementById('qr').innerHTML = '';
                    } else if (d.qr) {
                        document.getElementById('status').innerHTML = 'Escaneá el código QR con tu teléfono:';
                        document.getElementById('qr').innerHTML = '<img src="https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=' + encodeURIComponent(d.qr) + '">';
                    } else {
                        document.getElementById('status').innerHTML = '⏳ Inicializando...';
                    }
                }
                check();
                setInterval(check, 3000);
            </script>
        </body>
        </html>
    `);
});

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
    console.log(`WhatsApp service running on port ${PORT}`);
    initClient();
});
