import makeWASocket, { useMultiFileAuthState } from "@whiskeysockets/baileys";
import qrcode from "qrcode-terminal";
import axios from "axios";

const BASE_URL = process.env.LITELLM_PROXY_URL;
const API_KEY = process.env.LITELLM_MASTER_KEY;

// AUTO SWITCH MODEL
function getModel(text) {
  if (text.startsWith("/pro")) return "gemini-pro";
  if (text.startsWith("/fast")) return "groq-fast";
  return "gemini-flash";
}

async function askAI(text) {
  const model = getModel(text);

  const res = await axios.post(
    `${BASE_URL}/chat/completions`,
    {
      model,
      messages: [{ role: "user", content: text }]
    },
    {
      headers: {
        Authorization: `Bearer ${API_KEY}`
      }
    }
  );

  return res.data.choices[0].message.content;
}

async function startBot() {
  const { state, saveCreds } = await useMultiFileAuthState("auth");

  const sock = makeWASocket({ auth: state });

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("connection.update", ({ qr, connection }) => {
    if (qr) {
      console.log("Scan QR ini:");
      qrcode.generate(qr, { small: true });
    }

    if (connection === "open") {
      console.log("✅ WhatsApp connected");
    }
  });

  sock.ev.on("messages.upsert", async ({ messages }) => {
    const msg = messages[0];
    if (!msg.message) return;

    const text = msg.message.conversation || msg.message.extendedTextMessage?.text;
    if (!text) return;

    try {
      const reply = await askAI(text);

      await sock.sendMessage(msg.key.remoteJid, { text: reply });
    } catch (err) {
      await sock.sendMessage(msg.key.remoteJid, { text: "Error: " + err.message });
    }
  });
}

startBot();
