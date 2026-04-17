#!/usr/bin/env python3
"""
Telegram Bot Integration untuk Nanobot
- Chat dengan AI Agent
- Install/manage skills dari ClawHub via Telegram
"""

import os
import json
import asyncio
import logging
import aiohttp
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================
# CONFIGURATION
# ============================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
NANOBOT_API_URL = os.environ.get("NANOBOT_API_URL", "http://localhost:8080")
LITELLM_API_URL = os.environ.get("LITELLM_API_URL", "http://localhost:4000")
LITELLM_MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY", "")
ALLOWED_USER_IDS = os.environ.get("ALLOWED_TELEGRAM_USERS", "").split(",")
CLAWHUB_API_URL = os.environ.get("CLAWHUB_API_URL", "https://clawhub.com/api")

# ============================================
# SKILL MANAGER - Install skills dari ClawHub
# ============================================
class SkillManager:
    def __init__(self):
        self.installed_skills = {}
        self.skills_dir = os.environ.get("NANOBOT_SKILLS_DIR", "./skills")
        self._load_installed_skills()
    
    def _load_installed_skills(self):
        """Load daftar skill yang sudah terinstall"""
        skills_file = os.path.join(self.skills_dir, "installed.json")
        if os.path.exists(skills_file):
            with open(skills_file, "r") as f:
                self.installed_skills = json.load(f)
    
    def _save_installed_skills(self):
        """Simpan daftar skill yang terinstall"""
        os.makedirs(self.skills_dir, exist_ok=True)
        skills_file = os.path.join(self.skills_dir, "installed.json")
        with open(skills_file, "w") as f:
            json.dump(self.installed_skills, f, indent=2)
    
    async def search_skills(self, query: str) -> list:
        """Cari skill di ClawHub"""
        async with aiohttp.ClientSession() as session:
            try:
                # Search via ClawHub API
                async with session.get(
                    f"{CLAWHUB_API_URL}/skills/search",
                    params={"q": query},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        # Fallback: search via nanobot internal
                        return await self._search_via_nanobot(query)
            except Exception as e:
                logger.error(f"Error searching skills: {e}")
                return await self._search_via_nanobot(query)
    
    async def _search_via_nanobot(self, query: str) -> list:
        """Search skills via nanobot's built-in skill system"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{NANOBOT_API_URL}/api/skills/search",
                    json={"query": query},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
            except Exception:
                pass
        return []
    
    async def install_skill(self, skill_name: str, skill_url: str = None) -> dict:
        """Install skill dari ClawHub ke Nanobot"""
        result = {"success": False, "message": "", "skill_name": skill_name}
        
        try:
            async with aiohttp.ClientSession() as session:
                # Method 1: Install via Nanobot API
                payload = {
                    "action": "install",
                    "skill_name": skill_name,
                }
                if skill_url:
                    payload["source_url"] = skill_url
                
                async with session.post(
                    f"{NANOBOT_API_URL}/api/skills/install",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result["success"] = True
                        result["message"] = f"✅ Skill '{skill_name}' berhasil diinstall!"
                        
                        # Simpan ke daftar installed
                        self.installed_skills[skill_name] = {
                            "installed_at": datetime.now().isoformat(),
                            "source": skill_url or "clawhub",
                            "status": "active"
                        }
                        self._save_installed_skills()
                    else:
                        error_text = await resp.text()
                        result["message"] = f"❌ Gagal install: {error_text}"
                        
                        # Method 2: Fallback - install via CLI command
                        result = await self._install_via_cli(skill_name)
        
        except Exception as e:
            logger.error(f"Error installing skill: {e}")
            result["message"] = f"❌ Error: {str(e)}"
            # Try CLI fallback
            result = await self._install_via_cli(skill_name)
        
        return result
    
    async def _install_via_cli(self, skill_name: str) -> dict:
        """Fallback: Install skill via CLI command"""
        result = {"success": False, "message": "", "skill_name": skill_name}
        
        try:
            process = await asyncio.create_subprocess_exec(
                "nanobot", "skill", "install", skill_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.getcwd()
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=120
            )
            
            if process.returncode == 0:
                result["success"] = True
                result["message"] = f"✅ Skill '{skill_name}' berhasil diinstall via CLI!\n\n{stdout.decode()}"
                self.installed_skills[skill_name] = {
                    "installed_at": datetime.now().isoformat(),
                    "source": "clawhub-cli",
                    "status": "active"
                }
                self._save_installed_skills()
            else:
                result["message"] = f"❌ Gagal: {stderr.decode()}"
        
        except asyncio.TimeoutError:
            result["message"] = "❌ Timeout saat install skill"
        except FileNotFoundError:
            result["message"] = "❌ Nanobot CLI tidak ditemukan"
        except Exception as e:
            result["message"] = f"❌ Error: {str(e)}"
        
        return result
    
    async def uninstall_skill(self, skill_name: str) -> dict:
        """Uninstall skill"""
        result = {"success": False, "message": "", "skill_name": skill_name}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{NANOBOT_API_URL}/api/skills/uninstall",
                    json={"skill_name": skill_name},
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    if resp.status == 200:
                        result["success"] = True
                        result["message"] = f"✅ Skill '{skill_name}' berhasil diuninstall!"
                        if skill_name in self.installed_skills:
                            del self.installed_skills[skill_name]
                            self._save_installed_skills()
        except Exception as e:
            result["message"] = f"❌ Error: {str(e)}"
        
        return result
    
    def list_installed(self) -> dict:
        """List semua skill yang terinstall"""
        return self.installed_skills


# ============================================
# AI CHAT - Chat dengan Nanobot via LiteLLM
# ============================================
class NanobotChat:
    def __init__(self):
        self.conversation_history = {}  # per user
    
    async def chat(self, user_id: str, message: str, model: str = "gemini-flash") -> str:
        """Kirim pesan ke Nanobot via LiteLLM"""
        
        # Initialize conversation history
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []
        
        # Tambah pesan user ke history
        self.conversation_history[user_id].append({
            "role": "user",
            "content": message
        })
        
        # Keep only last 20 messages
        if len(self.conversation_history[user_id]) > 20:
            self.conversation_history[user_id] = self.conversation_history[user_id][-20:]
        
        try:
            # Pertama, coba kirim ke Nanobot API langsung
            response = await self._chat_via_nanobot(user_id, message)
            if response:
                return response
            
            # Fallback: kirim langsung ke LiteLLM
            response = await self._chat_via_litellm(user_id, message, model)
            return response
            
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return f"❌ Error: {str(e)}"
    
    async def _chat_via_nanobot(self, user_id: str, message: str) -> str:
        """Chat via Nanobot's own API"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{NANOBOT_API_URL}/api/chat",
                    json={
                        "message": message,
                        "session_id": f"telegram_{user_id}",
                        "context": self.conversation_history.get(user_id, [])
                    },
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        reply = data.get("response", data.get("message", ""))
                        self.conversation_history[user_id].append({
                            "role": "assistant",
                            "content": reply
                        })
                        return reply
        except Exception as e:
            logger.warning(f"Nanobot API not available: {e}")
        return None
    
    async def _chat_via_litellm(self, user_id: str, message: str, model: str) -> str:
        """Chat langsung via LiteLLM Proxy"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LITELLM_MASTER_KEY}"
        }
        
        system_prompt = """Kamu adalah Nanobot AI Agent yang berjalan di Telegram. 
Kamu bisa membantu user dengan berbagai tugas termasuk:
- Menjawab pertanyaan
- Menginstall skills dari ClawHub
- Browsing internet (jika skill tersedia)
- Analisis data
- Dan banyak lagi

Jawab dalam bahasa yang sama dengan user. Jika user berbicara bahasa Indonesia, jawab dalam bahasa Indonesia."""

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.conversation_history[user_id])
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{LITELLM_API_URL}/v1/chat/completions",
                headers=headers,
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 4096,
                },
                timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    reply = data["choices"][0]["message"]["content"]
                    self.conversation_history[user_id].append({
                        "role": "assistant",
                        "content": reply
                    })
                    return reply
                else:
                    error = await resp.text()
                    return f"❌ LiteLLM Error ({resp.status}): {error}"
    
    def clear_history(self, user_id: str):
        """Clear conversation history"""
        self.conversation_history[user_id] = []


# ============================================
# INTENT DETECTION - Deteksi maksud user
# ============================================
class IntentDetector:
    """Deteksi apakah user ingin install skill, chat biasa, dll"""
    
    INSTALL_KEYWORDS = [
        "install skill", "install skills", "pasang skill",
        "tambah skill", "add skill", "install", "pasang",
        "download skill", "ambil skill"
    ]
    
    UNINSTALL_KEYWORDS = [
        "uninstall skill", "hapus skill", "remove skill",
        "delete skill", "buang skill"
    ]
    
    LIST_KEYWORDS = [
        "list skill", "daftar skill", "skill apa saja",
        "skills installed", "skill terinstall", "lihat skill"
    ]
    
    SEARCH_KEYWORDS = [
        "cari skill", "search skill", "temukan skill",
        "skill untuk", "ada skill"
    ]
    
    @staticmethod
    def detect(message: str) -> dict:
        msg_lower = message.lower().strip()
        
        # Check install intent
        for keyword in IntentDetector.INSTALL_KEYWORDS:
            if keyword in msg_lower:
                # Extract skill name
                skill_name = msg_lower
                for kw in IntentDetector.INSTALL_KEYWORDS:
                    skill_name = skill_name.replace(kw, "")
                skill_name = skill_name.strip().strip('"\'')
                
                # Common skill mappings
                skill_mappings = {
                    "browsing": "web-browsing",
                    "browse": "web-browsing",
                    "web": "web-browsing",
                    "search": "web-search",
                    "code": "code-execution",
                    "coding": "code-execution",
                    "python": "python-executor",
                    "file": "file-management",
                    "image": "image-generation",
                    "gambar": "image-generation",
                    "translate": "translation",
                    "terjemah": "translation",
                    "math": "math-solver",
                    "matematika": "math-solver",
                    "calendar": "calendar-integration",
                    "email": "email-integration",
                    "database": "database-query",
                    "api": "api-caller",
                    "scraping": "web-scraping",
                    "pdf": "pdf-reader",
                    "youtube": "youtube-integration",
                }
                
                # Map common names
                for key, value in skill_mappings.items():
                    if key in skill_name:
                        skill_name = value
                        break
                
                if not skill_name:
                    skill_name = None
                
                return {
                    "intent": "install_skill",
                    "skill_name": skill_name,
                    "original_message": message
                }
        
        # Check uninstall intent
        for keyword in IntentDetector.UNINSTALL_KEYWORDS:
            if keyword in msg_lower:
                skill_name = msg_lower
                for kw in IntentDetector.UNINSTALL_KEYWORDS:
                    skill_name = skill_name.replace(kw, "")
                return {
                    "intent": "uninstall_skill",
                    "skill_name": skill_name.strip(),
                    "original_message": message
                }
        
        # Check list intent
        for keyword in IntentDetector.LIST_KEYWORDS:
            if keyword in msg_lower:
                return {
                    "intent": "list_skills",
                    "original_message": message
                }
        
        # Check search intent
        for keyword in IntentDetector.SEARCH_KEYWORDS:
            if keyword in msg_lower:
                query = msg_lower
                for kw in IntentDetector.SEARCH_KEYWORDS:
                    query = query.replace(kw, "")
                return {
                    "intent": "search_skills",
                    "query": query.strip(),
                    "original_message": message
                }
        
        # Default: chat biasa
        return {
            "intent": "chat",
            "original_message": message
        }


# ============================================
# TELEGRAM HANDLERS
# ============================================
skill_manager = SkillManager()
nanobot_chat = NanobotChat()

def is_authorized(user_id: int) -> bool:
    """Check if user is authorized"""
    if not ALLOWED_USER_IDS or ALLOWED_USER_IDS == [""]:
        return True  # Allow all if not configured
    return str(user_id) in ALLOWED_USER_IDS


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /start"""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Anda tidak memiliki akses.")
        return
    
    welcome_text = """
🤖 **Selamat datang di Nanobot AI Agent!**

Saya adalah AI Agent yang terhubung dengan:
• 🧠 **Google Gemini** (Flash 2.5 & Pro) via LiteLLM
• 🔧 **ClawHub Skills** - Install kemampuan baru

**Perintah yang tersedia:**
/start - Tampilkan pesan ini
/help - Bantuan lengkap
/skills - Lihat skills terinstall
/install <nama> - Install skill
/uninstall <nama> - Hapus skill
/search <query> - Cari skill di ClawHub
/model <flash|pro> - Ganti model AI
/clear - Hapus riwayat percakapan
/status - Cek status sistem

**Cara install skill via chat:**
Cukup ketik: _"install skill browsing dari clawhub"_

**Langsung chat aja!** Saya siap membantu 😊
"""
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /help"""
    help_text = """
📚 **Panduan Penggunaan Nanobot**

**1. Chat Biasa:**
Langsung ketik pesan, saya akan menjawab menggunakan AI.

**2. Install Skill:**
• `/install web-browsing`
• Atau ketik: _"install skill browsing"_
• Atau: _"coba kamu install skills browsing yang di clawhub"_

**3. Model AI:**
• `/model flash` - Gunakan Gemini 2.5 Flash (cepat)
• `/model pro` - Gunakan Gemini Pro (lebih pintar)
• Default: Flash (otomatis fallback ke model lain jika gagal)

**4. Skill Management:**
• `/skills` - Lihat skill terinstall
• `/search browsing` - Cari skill
• `/uninstall web-browsing` - Hapus skill

**5. Tips:**
• Saya secara otomatis mendeteksi jika Anda ingin install skill
• Jika satu API key limit, otomatis pindah ke key lain
• Jika model Pro gagal, otomatis fallback ke Flash
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def skills_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /skills - list installed skills"""
    if not is_authorized(update.effective_user.id):
        return
    
    installed = skill_manager.list_installed()
    
    if not installed:
        await update.message.reply_text(
            "📭 Belum ada skill yang terinstall.\n\n"
            "Gunakan `/search <query>` untuk mencari skill\n"
            "Atau `/install <nama_skill>` untuk install.",
            parse_mode="Markdown"
        )
        return
    
    text = "🔧 **Skills Terinstall:**\n\n"
    for name, info in installed.items():
        status_emoji = "✅" if info.get("status") == "active" else "⏸️"
        text += f"{status_emoji} **{name}**\n"
        text += f"   📅 Installed: {info.get('installed_at', 'N/A')[:10]}\n"
        text += f"   📦 Source: {info.get('source', 'N/A')}\n\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")


async def install_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /install <skill_name>"""
    if not is_authorized(update.effective_user.id):
        return
    
    if not context.args:
        await update.message.reply_text(
            "❓ Gunakan: `/install <nama_skill>`\n"
            "Contoh: `/install web-browsing`",
            parse_mode="Markdown"
        )
        return
    
    skill_name = " ".join(context.args)
    
    # Kirim pesan "sedang menginstall"
    status_msg = await update.message.reply_text(
        f"⏳ Sedang menginstall skill **{skill_name}**...\n"
        f"Mencari di ClawHub...",
        parse_mode="Markdown"
    )
    
    # Install skill
    result = await skill_manager.install_skill(skill_name)
    
    await status_msg.edit_text(
        result["message"],
        parse_mode="Markdown"
    )


async def uninstall_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /uninstall <skill_name>"""
    if not is_authorized(update.effective_user.id):
        return
    
    if not context.args:
        await update.message.reply_text("❓ Gunakan: `/uninstall <nama_skill>`", parse_mode="Markdown")
        return
    
    skill_name = " ".join(context.args)
    result = await skill_manager.uninstall_skill(skill_name)
    await update.message.reply_text(result["message"])


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /search <query>"""
    if not is_authorized(update.effective_user.id):
        return
    
    if not context.args:
        await update.message.reply_text("❓ Gunakan: `/search <query>`", parse_mode="Markdown")
        return
    
    query = " ".join(context.args)
    status_msg = await update.message.reply_text(f"🔍 Mencari skill: **{query}**...", parse_mode="Markdown")
    
    results = await skill_manager.search_skills(query)
    
    if not results:
        await status_msg.edit_text(f"😕 Tidak ditemukan skill untuk: **{query}**", parse_mode="Markdown")
        return
    
    text = f"🔍 **Hasil pencarian: {query}**\n\n"
    keyboard = []
    
    for i, skill in enumerate(results[:10]):
        name = skill.get("name", f"skill-{i}")
        desc = skill.get("description", "No description")[:100]
        text += f"**{i+1}. {name}**\n   {desc}\n\n"
        keyboard.append([
            InlineKeyboardButton(f"📥 Install {name}", callback_data=f"install:{name}")
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await status_msg.edit_text(text, parse_mode="Markdown", reply_markup=reply_markup)


async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /model <flash|pro>"""
    if not is_authorized(update.effective_user.id):
        return
    
    if not context.args:
        await update.message.reply_text(
            "🧠 **Pilih Model:**\n"
            "• `/model flash` - Gemini 2.5 Flash (cepat, 3 API keys)\n"
            "• `/model pro` - Gemini Pro (lebih pintar, 2 API keys)\n"
            "• `/model auto` - Otomatis (Pro → fallback ke Flash)",
            parse_mode="Markdown"
        )
        return
    
    model_choice = context.args[0].lower()
    model_map = {
        "flash": "gemini-flash",
        "pro": "gemini-pro",
        "auto": "gemini-auto"
    }
    
    if model_choice not in model_map:
        await update.message.reply_text("❓ Pilihan: flash, pro, atau auto")
        return
    
    # Save preference per user
    context.user_data["model"] = model_map[model_choice]
    await update.message.reply_text(
        f"✅ Model diganti ke **{model_choice.upper()}** ({model_map[model_choice]})",
        parse_mode="Markdown"
    )


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /clear"""
    user_id = str(update.effective_user.id)
    nanobot_chat.clear_history(user_id)
    await update.message.reply_text("🗑️ Riwayat percakapan dihapus!")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /status"""
    if not is_authorized(update.effective_user.id):
        return
    
    status_text = "📊 **Status Sistem:**\n\n"
    
    # Check LiteLLM
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{LITELLM_API_URL}/health",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    status_text += "✅ LiteLLM Proxy: Online\n"
                    health = await resp.json()
                    status_text += f"   Models: {health.get('healthy_count', 'N/A')} healthy\n"
                else:
                    status_text += "⚠️ LiteLLM Proxy: Degraded\n"
    except:
        status_text += "❌ LiteLLM Proxy: Offline\n"
    
    # Check Nanobot
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{NANOBOT_API_URL}/health",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    status_text += "✅ Nanobot: Online\n"
                else:
                    status_text += "⚠️ Nanobot: Degraded\n"
    except:
        status_text += "❌ Nanobot: Offline\n"
    
    # Skills info
    installed_count = len(skill_manager.list_installed())
    status_text += f"\n🔧 Skills installed: {installed_count}\n"
    
    # Model info
    current_model = context.user_data.get("model", "gemini-flash")
    status_text += f"🧠 Current model: {current_model}\n"
    
    await update.message.reply_text(status_text, parse_mode="Markdown")


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith("install:"):
        skill_name = data.split(":", 1)[1]
        await query.edit_message_text(
            f"⏳ Menginstall **{skill_name}**...",
            parse_mode="Markdown"
        )
        result = await skill_manager.install_skill(skill_name)
        await query.edit_message_text(result["message"], parse_mode="Markdown")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk semua pesan text (bukan command)"""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Anda tidak memiliki akses.")
        return
    
    user_id = str(update.effective_user.id)
    message = update.message.text
    
    # Detect intent
    intent = IntentDetector.detect(message)
    
    if intent["intent"] == "install_skill":
        # User ingin install skill
        skill_name = intent.get("skill_name")
        
        if not skill_name:
            await update.message.reply_text(
                "🤔 Skill apa yang ingin diinstall?\n"
                "Contoh: _\"install skill web-browsing\"_",
                parse_mode="Markdown"
            )
            return
        
        status_msg = await update.message.reply_text(
            f"⏳ Sedang menginstall skill **{skill_name}** dari ClawHub...",
            parse_mode="Markdown"
        )
        
        result = await skill_manager.install_skill(skill_name)
        await status_msg.edit_text(result["message"], parse_mode="Markdown")
    
    elif intent["intent"] == "uninstall_skill":
        skill_name = intent.get("skill_name", "").strip()
        if skill_name:
            result = await skill_manager.uninstall_skill(skill_name)
            await update.message.reply_text(result["message"])
    
    elif intent["intent"] == "list_skills":
        # Reuse skills command
        await skills_command(update, context)
    
    elif intent["intent"] == "search_skills":
        query = intent.get("query", "")
        if query:
            context.args = query.split()
            await search_command(update, context)
    
    else:
        # Chat biasa dengan AI
        model = context.user_data.get("model", "gemini-flash")
        
        # Show typing indicator
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing"
        )
        
        reply = await nanobot_chat.chat(user_id, message, model)
        
        # Split long messages (Telegram limit 4096 chars)
        if len(reply) > 4096:
            parts = [reply[i:i+4096] for i in range(0, len(reply), 4096)]
            for part in parts:
                await update.message.reply_text(part, parse_mode="Markdown")
        else:
            try:
                await update.message.reply_text(reply, parse_mode="Markdown")
            except Exception:
                # Fallback tanpa markdown jika parse error
                await update.message.reply_text(reply)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Error: {context.error}", exc_info=context.error)
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Terjadi error. Silakan coba lagi."
        )


# ============================================
# MAIN
# ============================================
def main():
    """Start the bot"""
    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not set!")
        return
    
    print("🤖 Starting Nanobot Telegram Bot...")
    
    # Build application
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("skills", skills_command))
    app.add_handler(CommandHandler("install", install_command))
    app.add_handler(CommandHandler("uninstall", uninstall_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("model", model_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_error_handler(error_handler)
    
    # Start polling
    print("✅ Bot is running!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
