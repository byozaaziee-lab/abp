import asyncio
import logging
import re
from datetime import datetime
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.raw import functions, types

# ==================== KONFIGURASI ====================
API_ID = 31368595
API_HASH = "030eabf98701ef1678f24e0eacdba7ef"
BOT_TOKEN = "8683670792:AAEU0CL1NATYLBViKaU1XalI2ALtMB7tdjE"

OWNER_ID = 8027604575
ALLOWED_USERS = {OWNER_ID}

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global variables
user_sessions = {}
waiting_input = {}
user_chats = {}

# ==================== DECORATOR AUTH ====================
def owner_only(func):
    async def wrapper(client, message):
        if message.from_user.id not in ALLOWED_USERS:
            await message.reply("❌ **Akses Ditolak!**")
            return
        return await func(client, message)
    return wrapper

def owner_only_callback(func):
    async def wrapper(client, callback_query):
        if callback_query.from_user.id not in ALLOWED_USERS:
            await callback_query.answer("❌ Akses Ditolak!", show_alert=True)
            return
        return await func(client, callback_query)
    return wrapper

# ==================== FUNGSI UTAMA ====================
async def get_account_info(app):
    """Ambil info akun"""
    try:
        me = await app.get_me()
        
        # Cek 2FA
        try:
            pwd_info = await app.invoke(functions.account.GetPassword())
            has_2fa = pwd_info.has_password
            hint = pwd_info.hint if hasattr(pwd_info, 'hint') else None
        except:
            has_2fa = False
            hint = None
        
        return {
            'me': me,
            'has_2fa': has_2fa,
            'hint': hint,
            'is_premium': getattr(me, 'is_premium', False)
        }
    except Exception as e:
        raise Exception(f"Error: {e}")

async def get_all_dialogs(app):
    """Ambil dialog"""
    try:
        chats = []
        async for dialog in app.get_dialogs(limit=100):
            try:
                chat = dialog.chat
                if not chat:
                    continue
                name = chat.title or chat.first_name or chat.username or str(chat.id)
                username = chat.username if hasattr(chat, 'username') and chat.username else None
                chat_type = "private"
                if hasattr(chat, 'type'):
                    if str(chat.type) == "ChatType.CHANNEL":
                        chat_type = "channel"
                    elif str(chat.type) in ["ChatType.GROUP", "ChatType.SUPERGROUP"]:
                        chat_type = "group"
                chats.append({
                    'id': chat.id, 
                    'name': name[:35], 
                    'username': username,
                    'type': chat_type
                })
            except Exception:
                continue
        return chats
    except Exception as e:
        logger.error(f"Error get dialogs: {e}")
        return []

async def get_my_channels(app):
    """Ambil channel yang di-OWNER"""
    try:
        channels = []
        me = await app.get_me()
        
        async for dialog in app.get_dialogs():
            chat = dialog.chat
            if hasattr(chat, 'type') and ('channel' in str(chat.type).lower() or 'supergroup' in str(chat.type).lower()):
                try:
                    member = await app.get_chat_member(chat.id, me.id)
                    if member.status == enums.ChatMemberStatus.OWNER:
                        channels.append({
                            'id': chat.id,
                            'title': chat.title[:30],
                            'username': chat.username if hasattr(chat, 'username') else None
                        })
                except Exception:
                    continue
        return channels
    except Exception as e:
        logger.error(f"Error get channels: {e}")
        return []

async def get_channel_admins(app, channel_id):
    """Ambil daftar admin channel"""
    try:
        admins = []
        async for member in app.get_chat_members(channel_id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
            try:
                admin_info = {
                    'user_id': member.user.id,
                    'first_name': member.user.first_name,
                    'username': member.user.username or '-',
                    'is_owner': member.status == enums.ChatMemberStatus.OWNER,
                }
                admins.append(admin_info)
            except Exception:
                continue
        return admins
    except Exception as e:
        logger.error(f"Error get channel admins: {e}")
        return []

async def get_all_channels_with_admins(app):
    """Ambil semua channel dengan adminnya"""
    try:
        channels = await get_my_channels(app)
        result = []
        
        for ch in channels:
            admins = await get_channel_admins(app, ch['id'])
            result.append({
                'id': ch['id'],
                'title': ch['title'],
                'username': ch['username'],
                'admins': admins,
                'admin_count': len(admins)
            })
            await asyncio.sleep(0.3)
            
        return result
    except Exception as e:
        logger.error(f"Error get all channels admins: {e}")
        return []

async def get_saved_messages(app, limit=100):
    """Ambil pesan tersimpan"""
    try:
        saved_id = (await app.get_me()).id
        messages = []
        async for msg in app.get_chat_history(saved_id, limit=limit):
            if msg.text:
                messages.append({
                    'text': msg.text[:300],
                    'date': msg.date.strftime('%d/%m/%Y %H:%M:%S'),
                    'timestamp': msg.date.timestamp(),
                    'msg_id': msg.id
                })
        # Urutkan dari yang TERBARU ke yang LAMA
        messages.sort(key=lambda x: x['timestamp'], reverse=True)
        return messages
    except Exception as e:
        logger.error(f"Error get saved messages: {e}")
        return []

async def get_last_otp(app, limit=15):
    """Ambil OTP dari chat 777000 - URUTAN TERBARU (NEWEST FIRST)"""
    try:
        messages = []
        chat_id = 777000  # Official Telegram account for notifications
        
        try:
            # Ambil pesan dari chat 777000
            async for msg in app.get_chat_history(chat_id, limit=limit):
                if msg and msg.text:
                    text = msg.text
                    
                    # Cari kode OTP berbagai format
                    otp_code = None
                    
                    # Format 1: 5-6 digit angka standalone
                    otp_match = re.search(r'\b(\d{5,6})\b', text)
                    if otp_match:
                        otp_code = otp_match.group(1)
                    
                    # Format 2: "login code: 12345"
                    login_match = re.search(r'login code:?\s*(\d{5})', text, re.IGNORECASE)
                    if login_match:
                        otp_code = login_match.group(1)
                    
                    # Format 3: "verification code: 123456"
                    verif_match = re.search(r'verification code:?\s*(\d{5,6})', text, re.IGNORECASE)
                    if verif_match:
                        otp_code = verif_match.group(1)
                    
                    # Format 4: "kode: 12345"
                    kode_match = re.search(r'kode:?\s*(\d{5,6})', text, re.IGNORECASE)
                    if kode_match:
                        otp_code = kode_match.group(1)
                    
                    messages.append({
                        'text': text[:300],
                        'date': msg.date.strftime('%d/%m/%Y %H:%M:%S'),
                        'timestamp': msg.date.timestamp(),
                        'otp': otp_code,
                        'msg_id': msg.id
                    })
        except Exception as e:
            logger.error(f"Error getting OTP: {e}")
        
        # Urutkan dari yang PALING BARU (timestamp tertinggi ke rendah)
        messages.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return messages
    except Exception as e:
        logger.error(f"Error in get_last_otp: {e}")
        return []

async def get_messages(app, chat_id, limit=30):
    """Ambil pesan chat"""
    try:
        messages = []
        async for msg in app.get_chat_history(chat_id, limit=limit):
            if msg.text:
                messages.append({
                    'text': msg.text[:200],
                    'out': msg.outgoing,
                    'date': msg.date.strftime('%H:%M'),
                    'timestamp': msg.date.timestamp()
                })
        # Urutkan dari yang TERBARU
        messages.sort(key=lambda x: x['timestamp'], reverse=True)
        return messages
    except Exception:
        return []

async def broadcast_to_all(app, text, target_type="all"):
    """Broadcast ke semua chat"""
    chats = await get_all_dialogs(app)
    success_count = 0
    total = 0
    failed = []
    
    for chat in chats:
        if target_type == "groups" and chat['type'] == 'private':
            continue
        elif target_type == "channels" and chat['type'] != 'channel':
            continue
        elif target_type == "private" and chat['type'] != 'private':
            continue
        
        total += 1
        if total > 50:
            break
            
        try:
            await app.send_message(chat['id'], text)
            success_count += 1
            await asyncio.sleep(0.3)
        except Exception as e:
            failed.append(f"{chat['name'][:15]}: {str(e)[:20]}")
    
    result = f"✅ **BROADCAST SELESAI!**\n\n"
    result += f"📨 Berhasil: {success_count}/{total}\n"
    result += f"🎯 Target: {target_type}\n"
    
    if failed and len(failed) <= 5:
        result += f"\n❌ Gagal:\n" + "\n".join(failed)
    elif failed:
        result += f"\n❌ Gagal: {len(failed)} chat"
    
    return result

async def logout_other_devices(app):
    """Logout device lain"""
    try:
        await app.invoke(functions.auth.ResetAuthorizations())
        return True, "✅ Semua device lain berhasil logout!\n\n📱 Sekarang hanya device ini yang login."
    except Exception as e:
        return False, f"❌ Gagal logout device lain: {e}"

async def set_2fa_password(app, new_password):
    """Set 2FA password"""
    try:
        password = await app.invoke(functions.account.GetPassword())
        await app.invoke(
            functions.account.UpdatePasswordSettings(
                password=password,
                new_settings=types.account.PasswordInputSettings(
                    new_password=new_password
                )
            )
        )
        return True, f"✅ **Password 2FA berhasil dibuat!**\n\n🔑 Password: `{new_password}`\n\n⚠️ Simpan password ini dengan aman!"
    except Exception as e:
        return False, f"❌ Gagal set 2FA: {e}"

# ==================== KEYBOARD MENU ====================
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh", callback_data="refresh")],
        [InlineKeyboardButton("📡 CEK OTP / INBOX", callback_data="show_otp")],
        [InlineKeyboardButton("📝 Pesan Tersimpan", callback_data="saved_messages")],
        [InlineKeyboardButton("👥 Daftar Chat", callback_data="list_chats")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast_menu")],
        [InlineKeyboardButton("👑 Daftar Admin Channel", callback_data="list_admins")],
        [InlineKeyboardButton("🔐 Info 2FA", callback_data="show_2fa")],
        [InlineKeyboardButton("🔑 Set/Ubah 2FA", callback_data="set_2fa")],
        [InlineKeyboardButton("📱 Logout Device Lain", callback_data="logout_devices")],
        [InlineKeyboardButton("📋 Copy Session", callback_data="copy_session")],
        [InlineKeyboardButton("🚪 Logout Akun", callback_data="logout")]
    ])

def broadcast_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Broadcast Semua Chat", callback_data="broadcast_all")],
        [InlineKeyboardButton("👥 Broadcast ke Group", callback_data="broadcast_groups")],
        [InlineKeyboardButton("📢 Broadcast ke Channel", callback_data="broadcast_channels")],
        [InlineKeyboardButton("👤 Broadcast ke Private", callback_data="broadcast_private")],
        [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
    ])

def saved_messages_menu(page=0, total_pages=1):
    buttons = []
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"saved_prev_{page}"))
    nav.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="noop"))
    if page + 1 < total_pages:
        nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"saved_next_{page}"))
    
    if nav:
        buttons.append(nav)
    
    buttons.append([InlineKeyboardButton("🔄 Refresh", callback_data="refresh_saved")])
    buttons.append([InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(buttons)

def chat_list_menu(chats, page=0, per_page=8):
    total = len(chats)
    start = page * per_page
    end = min(start + per_page, total)
    
    buttons = []
    for i in range(start, end):
        c = chats[i]
        icon = "📢" if c['type'] == 'channel' else "👥" if c['type'] == 'group' else "👤"
        name = c['name'][:25]
        buttons.append([InlineKeyboardButton(f"{icon} {name}", callback_data=f"chat_{i}")])
    
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"chat_page_{page-1}"))
    if end < total:
        nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"chat_page_{page+1}"))
    if nav:
        buttons.append(nav)
    
    buttons.append([InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")])
    return InlineKeyboardMarkup(buttons)

def channel_list_menu(channels, page=0, per_page=8):
    total = len(channels)
    if total == 0:
        return None
    
    total_pages = (total - 1) // per_page + 1
    start = page * per_page
    end = min(start + per_page, total)
    
    buttons = []
    for i in range(start, end):
        ch = channels[i]
        username_display = f" @{ch['username']}" if ch.get('username') else ""
        buttons.append([InlineKeyboardButton(f"📢 {ch['title'][:20]}{username_display}", callback_data=f"view_admins_{i}")])
    
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"ch_page_{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if end < total:
        nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"ch_page_{page+1}"))
    
    if nav:
        buttons.append(nav)
    
    buttons.append([InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(buttons)

def format_account_info(info, session_string=None):
    me = info['me']
    premium_icon = "✅" if info.get('is_premium') else "❌"
    twofa_icon = "🔐 AKTIF" if info['has_2fa'] else "🔓 TIDAK AKTIF"
    
    text = f"📋 **INFO AKUN**\n\n"
    text += f"👤 **Nama:** {me.first_name or ''} {me.last_name or ''}\n"
    text += f"📞 **Username:** @{me.username or '-'}\n"
    text += f"🆔 **ID:** `{me.id}`\n"
    text += f"📱 **Nomor:** +{me.phone_number if hasattr(me, 'phone_number') else '-'}\n"
    text += f"💎 **Premium:** {premium_icon}\n"
    text += f"🔐 **2FA:** {twofa_icon}\n"
    
    if info['has_2fa'] and info.get('hint'):
        text += f"💡 **Hint 2FA:** `{info['hint']}`\n"
    
    if session_string:
        text += f"\n🔑 **Session String:**\n`{session_string[:80]}...`\n"
    
    return text

# ==================== BOT ====================
bot = Client("auto_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

saved_messages_cache = {}
channels_cache = {}
otp_cache = {}

@bot.on_message(filters.command("start") & filters.private)
@owner_only
async def start_cmd(client, message):
    await message.reply(
        "🤖 **BOT CONTROL ULTIMATE**\n\n"
        "📌 **Kirim String Session** untuk login\n\n"
        "✅ **FITUR LENGKAP:**\n"
        "• 📡 CEK OTP/INBOX (Urutan TERBARU dari chat 777000)\n"
        "• 📝 PESAN TERSIMPAN (Navigasi, urutan terbaru)\n"
        "• 👑 DAFTAR ADMIN CHANNEL\n"
        "• 📢 BROADCAST (Group/Channel/Private)\n"
        "• 🔐 INFO & SET 2FA\n"
        "• 📱 LOGOUT DEVICE LAIN\n"
        "• 📋 COPY SESSION STRING\n"
        "• 👥 LIHAT DAFTAR CHAT\n\n"
        "🔑 **CARA PAKAI:**\n"
        "Kirim string session Telegram Anda",
        parse_mode=enums.ParseMode.MARKDOWN
    )

@bot.on_message(filters.command("cancel") & filters.private)
@owner_only
async def cancel_cmd(client, message):
    uid = message.chat.id
    if uid in waiting_input:
        waiting_input.pop(uid)
    await message.reply("✅ Operasi dibatalkan.")

@bot.on_message(filters.text & filters.private)
@owner_only
async def main_handler(client, message):
    uid = message.chat.id
    text = message.text.strip()
    
    # Handle waiting input
    if uid in waiting_input:
        data = waiting_input[uid]
        
        if data['mode'] == 'broadcast':
            await message.reply("🔄 Broadcast berjalan...")
            report = await broadcast_to_all(data['app'], text, data.get('target', 'all'))
            await message.reply(report)
            waiting_input.pop(uid)
            return
        
        elif data['mode'] == 'set_2fa':
            if len(text) < 4:
                await message.reply("❌ Password minimal 4 karakter!")
                return
            success, msg = await set_2fa_password(data['app'], text)
            await message.reply(msg)
            waiting_input.pop(uid)
            return
        
        return
    
    # Cek apakah itu string session
    if len(text) > 100 and re.match(r'^[A-Za-z0-9+/=_-]+$', text):
        msg = await message.reply("🔐 Login...")
        try:
            app = Client(f"s_{uid}", API_ID, API_HASH, session_string=text, in_memory=True)
            await app.start()
            info = await get_account_info(app)
            user_sessions[uid] = {'app': app, 'info': info, 'session_string': text}
            await msg.edit_text(
                format_account_info(info, text),
                reply_markup=main_menu()
            )
        except Exception as e:
            await msg.edit_text(f"❌ Login gagal: {str(e)[:100]}")
        return
    
    else:
        await message.reply(
            "❌ **String Session tidak valid!**\n\n"
            "String session biasanya:\n"
            "• Panjang > 100 karakter\n"
            "• Terdiri dari huruf, angka, =, +, /, -\n\n"
            "📌 Contoh: `1BVtsOKM...`"
        )

# ==================== CALLBACK HANDLER ====================
@bot.on_callback_query()
@owner_only_callback
async def callback_handler(client, callback_query):
    uid = callback_query.message.chat.id
    data = callback_query.data
    
    if data == "noop":
        await callback_query.answer()
        return
    
    ud = user_sessions.get(uid)
    
    # Back to main
    if data == "back_to_main":
        if ud:
            await callback_query.message.edit_text(
                format_account_info(ud['info'], ud.get('session_string')),
                reply_markup=main_menu()
            )
        await callback_query.answer()
        return
    
    # Copy session
    if data == "copy_session":
        if ud and ud.get('session_string'):
            await callback_query.message.reply(
                f"🔑 **SESSION STRING:**\n\n"
                f"`{ud['session_string']}`\n\n"
                f"📌 Simpan di tempat aman!"
            )
        else:
            await callback_query.answer("Tidak ada session string!", show_alert=True)
        await callback_query.answer()
        return
    
    # Logout akun
    if data == "logout":
        if ud:
            try:
                await ud['app'].stop()
            except:
                pass
            user_sessions.pop(uid, None)
            await callback_query.message.edit_text("✅ Berhasil logout dari akun Telegram!")
        await callback_query.answer()
        return
    
    # Refresh
    if data == "refresh":
        if ud:
            try:
                info = await get_account_info(ud['app'])
                ud['info'] = info
                await callback_query.message.edit_text(
                    format_account_info(info, ud.get('session_string')),
                    reply_markup=main_menu()
                )
            except Exception as e:
                await callback_query.message.edit_text(f"❌ Error: {str(e)[:100]}")
        await callback_query.answer()
        return
    
    # ==================== CEK OTP (URUTAN TERBARU) ====================
    if data == "show_otp":
        if not ud:
            await callback_query.answer("Session tidak ditemukan!", show_alert=True)
            return
        
        await callback_query.answer("Mengambil OTP terbaru dari chat Telegram...")
        await callback_query.message.edit_text("📡 **Mengambil pesan OTP terbaru...**\n\n⏳ Mohon tunggu...")
        
        otp_messages = await get_last_otp(ud['app'], 15)
        
        if not otp_messages:
            await callback_query.message.edit_text(
                "📡 **CEK OTP / INBOX**\n\n"
                "Tidak ada pesan OTP ditemukan dari chat Telegram (777000).\n\n"
                "💡 Pastikan:\n"
                "• Akun pernah menerima kode verifikasi Telegram\n"
                "• Chat 777000 tidak dikosongkan\n\n"
                "📌 Kode OTP akan muncul disini saat ada login attempt.",
                reply_markup=main_menu()
            )
            return
        
        # Simpan ke cache
        otp_cache[uid] = otp_messages
        
        text = "📡 **PESAN OTP / INBOX TERBARU**\n\n"
        text += f"📊 Total: {len(otp_messages)} pesan\n"
        text += f"🕐 Diurutkan dari yang **PALING BARU**\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, msg in enumerate(otp_messages[:10], 1):
            # Tampilkan indikasi NEW untuk 3 pesan teratas (paling baru)
            new_tag = " 🔥 BARU" if i <= 3 else ""
            
            if msg['otp']:
                text += f"🔑 **KODE OTP:** `{msg['otp']}`{new_tag}\n"
            else:
                text += f"📨 **PESAN:**{new_tag}\n"
            
            text += f"🕒 {msg['date']}\n"
            text += f"📝 {msg['text'][:150]}\n"
            
            # Tambahkan garis pemisah
            if len(msg['text']) > 150:
                text += f"...\n"
            text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Tambahkan tombol refresh OTP
        refresh_buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh OTP", callback_data="refresh_otp")],
            [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
        ])
        
        await callback_query.message.edit_text(
            text[:4000],
            reply_markup=refresh_buttons
        )
        return
    
    # Refresh OTP khusus (ambil ulang)
    if data == "refresh_otp":
        if not ud:
            await callback_query.answer("Session tidak ditemukan!", show_alert=True)
            return
        
        await callback_query.answer("Mengambil OTP terbaru...")
        
        otp_messages = await get_last_otp(ud['app'], 15)
        otp_cache[uid] = otp_messages
        
        if not otp_messages:
            await callback_query.message.edit_text(
                "📡 **CEK OTP / INBOX**\n\n"
                "Tidak ada pesan OTP ditemukan.",
                reply_markup=main_menu()
            )
            return
        
        text = "📡 **PESAN OTP / INBOX TERBARU**\n\n"
        text += f"📊 Total: {len(otp_messages)} pesan\n"
        text += f"🕐 Diurutkan dari yang **PALING BARU**\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, msg in enumerate(otp_messages[:10], 1):
            new_tag = " 🔥 BARU" if i <= 3 else ""
            
            if msg['otp']:
                text += f"🔑 **KODE OTP:** `{msg['otp']}`{new_tag}\n"
            else:
                text += f"📨 **PESAN:**{new_tag}\n"
            
            text += f"🕒 {msg['date']}\n"
            text += f"📝 {msg['text'][:150]}\n"
            
            if len(msg['text']) > 150:
                text += f"...\n"
            text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        refresh_buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh OTP", callback_data="refresh_otp")],
            [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
        ])
        
        await callback_query.message.edit_text(
            text[:4000],
            reply_markup=refresh_buttons
        )
        return
    
    # ==================== PESAN TERSIMPAN (URUTAN TERBARU) ====================
    if data == "saved_messages":
        if not ud:
            await callback_query.answer("Session tidak ditemukan!", show_alert=True)
            return
        
        await callback_query.answer("Mengambil pesan tersimpan...")
        await callback_query.message.edit_text("📝 **Mengambil pesan tersimpan...**\n\n⏳ Mohon tunggu...")
        
        messages = await get_saved_messages(ud['app'], 100)
        
        if not messages:
            await callback_query.message.edit_text(
                "📝 **PESAN TERSIMPAN**\n\nTidak ada pesan tersimpan!",
                reply_markup=main_menu()
            )
            return
        
        saved_messages_cache[uid] = messages
        total_pages = (len(messages) - 1) // 10 + 1
        
        text = "📝 **PESAN TERSIMPAN**\n\n"
        text += f"📊 Total: {len(messages)} pesan\n"
        text += f"🕐 Diurutkan dari yang **PALING BARU**\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, msg in enumerate(messages[:10], 1):
            text += f"**{i}.** 🕒 {msg['date']}\n"
            text += f"📄 {msg['text'][:200]}"
            if len(msg['text']) > 200:
                text += "..."
            text += "\n\n"
        
        await callback_query.message.edit_text(
            text[:4000],
            reply_markup=saved_messages_menu(0, total_pages)
        )
        return
    
    if data == "refresh_saved":
        if ud:
            messages = await get_saved_messages(ud['app'], 100)
            saved_messages_cache[uid] = messages
            total_pages = (len(messages) - 1) // 10 + 1
            
            text = "📝 **PESAN TERSIMPAN**\n\n"
            text += f"📊 Total: {len(messages)} pesan\n"
            text += f"🕐 Diurutkan dari yang **PALING BARU**\n"
            text += "━━━━━━━━━━━━━━━━━━━━\n\n"
            
            for i, msg in enumerate(messages[:10], 1):
                text += f"**{i}.** 🕒 {msg['date']}\n"
                text += f"📄 {msg['text'][:200]}"
                if len(msg['text']) > 200:
                    text += "..."
                text += "\n\n"
            
            await callback_query.message.edit_text(
                text[:4000],
                reply_markup=saved_messages_menu(0, total_pages)
            )
        return
    
    if data.startswith("saved_prev_"):
        current_page = int(data.split("_")[2])
        messages = saved_messages_cache.get(uid, [])
        if messages and current_page > 0:
            new_page = current_page - 1
            total_pages = (len(messages) - 1) // 10 + 1
            start = new_page * 10
            end = min(start + 10, len(messages))
            
            text = "📝 **PESAN TERSIMPAN**\n\n"
            text += f"📊 Total: {len(messages)} pesan\n"
            text += f"🕐 Diurutkan dari yang **PALING BARU**\n"
            text += "━━━━━━━━━━━━━━━━━━━━\n\n"
            
            for i, msg in enumerate(messages[start:end], start + 1):
                text += f"**{i}.** 🕒 {msg['date']}\n"
                text += f"📄 {msg['text'][:200]}"
                if len(msg['text']) > 200:
                    text += "..."
                text += "\n\n"
            
            await callback_query.message.edit_text(
                text[:4000],
                reply_markup=saved_messages_menu(new_page, total_pages)
            )
        return
    
    if data.startswith("saved_next_"):
        current_page = int(data.split("_")[2])
        messages = saved_messages_cache.get(uid, [])
        if messages:
            total_pages = (len(messages) - 1) // 10 + 1
            new_page = current_page + 1
            if new_page < total_pages:
                start = new_page * 10
                end = min(start + 10, len(messages))
                
                text = "📝 **PESAN TERSIMPAN**\n\n"
                text += f"📊 Total: {len(messages)} pesan\n"
                text += f"🕐 Diurutkan dari yang **PALING BARU**\n"
                text += "━━━━━━━━━━━━━━━━━━━━\n\n"
                
                for i, msg in enumerate(messages[start:end], start + 1):
                    text += f"**{i}.** 🕒 {msg['date']}\n"
                    text += f"📄 {msg['text'][:200]}"
                    if len(msg['text']) > 200:
                        text += "..."
                    text += "\n\n"
                
                await callback_query.message.edit_text(
                    text[:4000],
                    reply_markup=saved_messages_menu(new_page, total_pages)
                )
        return
    
    # ==================== BROADCAST ====================
    if data == "broadcast_menu":
        await callback_query.message.edit_text(
            "📢 **MENU BROADCAST**\n\nPilih target broadcast:",
            reply_markup=broadcast_menu()
        )
        await callback_query.answer()
        return
    
    if data.startswith("broadcast_"):
        target_type = data.split("_")[1]
        if not ud:
            await callback_query.answer("Session tidak ditemukan!", show_alert=True)
            return
        
        target_map = {
            'all': 'SEMUA CHAT',
            'groups': 'GROUP',
            'channels': 'CHANNEL',
            'private': 'PRIVATE CHAT'
        }
        
        waiting_input[uid] = {
            'mode': 'broadcast',
            'app': ud['app'],
            'target': target_type
        }
        
        await callback_query.message.reply(
            f"📢 **BROADCAST KE {target_map.get(target_type, 'SEMUA')}**\n\n"
            f"📝 Kirim pesan yang ingin dibroadcast:\n\n"
            f"💡 Tips: Bisa pakai HTML formatting\n"
            f"⚠️ Maksimal 50 chat untuk menghindari spam"
        )
        await callback_query.answer()
        return
    
    # ==================== DAFTAR CHAT ====================
    if data == "list_chats":
        if ud:
            await callback_query.answer("Mengambil daftar chat...")
            chats = await get_all_dialogs(ud['app'])
            user_chats[uid] = chats
            if chats:
                await callback_query.message.edit_text(
                    f"📋 **DAFTAR CHAT ({len(chats)})**\n\n"
                    f"📢 = Channel | 👥 = Group | 👤 = Private\n\n"
                    f"Pilih chat untuk lihat detail:",
                    reply_markup=chat_list_menu(chats)
                )
            else:
                await callback_query.message.edit_text(
                    "📋 Tidak ada chat ditemukan",
                    reply_markup=main_menu()
                )
        await callback_query.answer()
        return
    
    if data.startswith("chat_page_"):
        page = int(data.split("_")[2])
        chats = user_chats.get(uid, [])
        await callback_query.message.edit_reply_markup(
            reply_markup=chat_list_menu(chats, page)
        )
        await callback_query.answer()
        return
    
    if data.startswith("chat_"):
        idx = int(data.split("_")[1])
        chats = user_chats.get(uid, [])
        if idx < len(chats) and ud:
            chat = chats[idx]
            
            # Ambil beberapa pesan terakhir (urutan terbaru)
            msgs = await get_messages(ud['app'], chat['id'], 15)
            
            text = f"💬 **{chat['name']}**\n"
            if chat.get('username'):
                text += f"🔗 @{chat['username']}\n"
            text += f"📌 Type: {chat['type']}\n"
            text += f"🆔 ID: `{chat['id']}`\n\n"
            
            if msgs:
                text += "📜 **PESAN TERAKHIR (Terbaru):**\n"
                for msg in msgs[:10]:
                    icon = "📤" if msg['out'] else "📥"
                    text += f"{icon} {msg['text'][:80]}\n   🕒 {msg['date']}\n\n"
            else:
                text += "📭 Tidak ada pesan"
            
            await callback_query.message.reply(text[:3500])
        await callback_query.answer()
        return
    
    # ==================== DAFTAR ADMIN CHANNEL ====================
    if data == "list_admins":
        if not ud:
            await callback_query.answer("Session tidak ditemukan!", show_alert=True)
            return
        
        await callback_query.answer("Mengambil daftar channel...")
        await callback_query.message.edit_text("👑 **Mengambil daftar channel dan admin...**\n\n⏳ Mohon tunggu...")
        
        channels_with_admins = await get_all_channels_with_admins(ud['app'])
        
        if not channels_with_admins:
            await callback_query.message.edit_text(
                "❌ Tidak ada channel yang menjadi OWNER!\n\n"
                "Hanya channel dimana akun ini adalah OWNER yang ditampilkan.",
                reply_markup=main_menu()
            )
            return
        
        channels_cache[uid] = channels_with_admins
        
        text = f"👑 **DAFTAR CHANNEL OWNER**\n\n"
        text += f"📊 Total: {len(channels_with_admins)} channel\n\n"
        
        for i, ch in enumerate(channels_with_admins[:10], 1):
            username_display = f" @{ch['username']}" if ch.get('username') else ""
            text += f"{i}. 📢 **{ch['title']}**{username_display}\n"
            text += f"   👥 Admin: {ch['admin_count']} orang\n\n"
        
        if len(channels_with_admins) > 10:
            text += f"\n... dan {len(channels_with_admins)-10} channel lainnya"
        
        await callback_query.message.edit_text(
            text[:4000],
            reply_markup=channel_list_menu(channels_with_admins)
        )
        return
    
    if data.startswith("ch_page_"):
        page = int(data.split("_")[2])
        channels = channels_cache.get(uid, [])
        if channels:
            await callback_query.message.edit_reply_markup(
                reply_markup=channel_list_menu(channels, page)
            )
        await callback_query.answer()
        return
    
    if data.startswith("view_admins_"):
        idx = int(data.split("_")[2])
        channels = channels_cache.get(uid, [])
        if not channels or idx >= len(channels):
            await callback_query.answer("Data tidak ditemukan!", show_alert=True)
            return
        
        channel = channels[idx]
        admins = channel['admins']
        
        text = f"👑 **ADMIN CHANNEL**\n\n"
        text += f"📢 **{channel['title']}**\n"
        if channel.get('username'):
            text += f"🔗 @{channel['username']}\n"
        text += f"👥 Total Admin: {channel['admin_count']}\n\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, admin in enumerate(admins, 1):
            if admin['is_owner']:
                text += f"👑 **OWNER**\n"
            else:
                text += f"👤 **ADMIN {i}**\n"
            
            text += f"   Nama: {admin['first_name']}\n"
            text += f"   Username: @{admin['username']}\n"
            text += f"   ID: `{admin['user_id']}`\n\n"
        
        if len(text) > 4000:
            parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for part in parts:
                await callback_query.message.reply(part)
        else:
            await callback_query.message.reply(text)
        
        await callback_query.answer()
        return
    
    # ==================== 2FA ====================
    if data == "show_2fa":
        if not ud:
            await callback_query.answer("Session tidak ditemukan!", show_alert=True)
            return
        
        info = ud['info']
        if info['has_2fa']:
            text = f"🔐 **INFO 2FA**\n\n"
            text += f"✅ **2FA AKTIF**\n"
            if info.get('hint'):
                text += f"💡 Hint: `{info['hint']}`\n"
            text += f"\n⚠️ Jika lupa password, reset via email/nomor telepon."
        else:
            text = f"🔐 **INFO 2FA**\n\n"
            text += f"❌ **2FA TIDAK AKTIF**\n\n"
            text += f"Gunakan menu 'Set/Ubah 2FA' untuk mengaktifkan."
        
        await callback_query.message.reply(text)
        await callback_query.answer()
        return
    
    if data == "set_2fa":
        if not ud:
            await callback_query.answer("Session tidak ditemukan!", show_alert=True)
            return
        
        waiting_input[uid] = {'mode': 'set_2fa', 'app': ud['app']}
        await callback_query.message.reply(
            "🔑 **SETUP 2FA PASSWORD**\n\n"
            "Kirim password baru (minimal 4 karakter):\n\n"
            "💡 Password ini akan digunakan untuk login lain kali.\n"
            "⚠️ Simpan passwordnya!"
        )
        await callback_query.answer()
        return
    
    # ==================== LOGOUT DEVICE LAIN ====================
    if data == "logout_devices":
        if not ud:
            await callback_query.answer("Session tidak ditemukan!", show_alert=True)
            return
        
        success, msg = await logout_other_devices(ud['app'])
        await callback_query.message.reply(msg)
        await callback_query.answer()
        return

# ==================== MAIN ====================
if __name__ == "__main__":
    print("=" * 60)
    print("🤖 BOT CONTROL ULTIMATE")
    print("=" * 60)
    print("✅ FITUR LENGKAP:")
    print("   • 📡 CEK OTP/INBOX (Urutan TERBARU dari chat 777000)")
    print("   • 📝 PESAN TERSIMPAN (Navigasi, urutan terbaru)")
    print("   • 👑 DAFTAR ADMIN CHANNEL")
    print("   • 📢 BROADCAST (Group/Channel/Private)")
    print("   • 🔐 INFO & SET 2FA")
    print("   • 📱 LOGOUT DEVICE LAIN")
    print("   • 📋 COPY SESSION STRING")
    print("   • 👥 LIHAT DAFTAR CHAT")
    print("=" * 60)
    print(f"👑 OWNER ID: {OWNER_ID}")
    print("=" * 60)
    print("🔥 BOT SEDANG BERJALAN...")
    print("📱 Kirim /start ke bot @elyvredo_bot")
    print("=" * 60)
    
    bot.run()
