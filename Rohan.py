import asyncio
import sqlite3
import time
import random
import logging
import pytz
import requests

from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

# --- Logging ---
logging.basicConfig(level=logging.INFO)

# --- Config ---
API_TOKEN = '7655173404:AAF3FadHz2zQbXGmrWwGUgaBN35LFnXiVoo'
OWNER_ID = 1866961136
STRIPE_API_KEY = 'pk_live_Ng5VkKcI3Ur3KZ92goEDVRBq'
BIN_API_URL = 'https://lookup.binlist.net/'

bot = Bot(token=API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())

# --- SQLite Setup ---
conn = sqlite3.connect("users.db", check_same_thread=False)
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, expires_at INTEGER, is_admin INTEGER DEFAULT 0)")
conn.commit()

cooldown = {}

# --- Utility Functions ---
def is_admin(user_id: int):
    c.execute("SELECT 1 FROM users WHERE user_id = ? AND is_admin = 1", (user_id,))
    return c.fetchone() is not None

def has_access(user_id: int):
    c.execute("SELECT expires_at FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    return row and row[0] > time.time()

def check_stripe(card_number: str):
    url = "https://api.stripe.com/v1/tokens"
    headers = {"Authorization": f"Bearer {STRIPE_API_KEY}"}
    payload = {
        "card[number]": card_number,
        "card[exp_month]": "12",
        "card[exp_year]": "2026",
        "card[cvc]": "123"
    }
    response = requests.post(url, headers=headers, data=payload)
    if response.status_code == 200:
        return "✅ Approved - 3D Secure Passed"
    return "❌ Declined - Stripe API Failed"

def get_bin_info(bin_number: str):
    response = requests.get(f"{BIN_API_URL}{bin_number}")
    if response.status_code == 200:
        data = response.json()
        bank = data.get('bank', {}).get('name', 'Unknown')
        country = data.get('country', {}).get('name', 'Unknown')
        card_type = data.get('type', 'Unknown')
        return f"Bank: {bank}\nCountry: {country}\nType: {card_type}"
    return "❌ BIN not found"

# --- APScheduler Job ---
def remove_expired_users():
    now = int(time.time())
    c.execute("DELETE FROM users WHERE expires_at <= ?", (now,))
    conn.commit()
    print("⏰ Expired access removed.")

scheduler = AsyncIOScheduler(timezone=pytz.timezone('Asia/Kolkata'))
scheduler.add_job(remove_expired_users, "cron", hour=0, minute=0)
scheduler.start()

# --- Handlers ---
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("👋 Welcome to CC Checker Bot!\nUse /redeem to get access.\nFree tools: /bin /fakeus")

@dp.message(Command("fakeus"))
async def cmd_fakeus(message: Message):
    await message.answer("🇺🇸 Fake US Info:\nName: John Doe\nCard: 4111 1111 1111 1111\nExp: 12/27\nCVV: 123")

@dp.message(Command("bin"))
async def cmd_bin(message: Message):
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Please provide a BIN. Example: /bin 411111")
    bin_info = get_bin_info(args[1])
    await message.answer(f"🔍 BIN Info:\n{bin_info}")

@dp.message(Command("vbv"))
async def cmd_vbv(message: Message):
    if not has_access(message.from_user.id):
        return await message.answer("❌ You don’t have access.\nDM to buy - @Rohan2349")
    result = random.choice(["✅ Approved - 3D Secure Passed", "❌ Declined - VBV Failed"])
    await message.answer(f"🔐 VBV Check Result:\n{result}")

@dp.message(Command("redeem"))
async def cmd_redeem(message: Message):
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Please provide a code. Example: /redeem Rohan-XXXX")
    code = args[1]
    if not code.startswith("Rohan-"):
        return await message.answer("Invalid code format.")

    duration = 86400  # 1 day default
    if "1" in code: duration = 3600
    elif "3" in code: duration = 86400 * 3
    elif "5" in code: duration = 86400 * 5
    elif "7" in code: duration = 86400 * 7
    elif "30" in code: duration = 86400 * 30

    expires_at = int(time.time()) + duration
    c.execute("REPLACE INTO users (user_id, expires_at, is_admin) VALUES (?, ?, ?)", (message.from_user.id, expires_at, 0))
    conn.commit()
    await message.answer(f"✅ Access granted for {duration // 86400} day(s)!")

@dp.message(Command("info"))
async def cmd_info(message: Message):
    c.execute("SELECT expires_at, is_admin FROM users WHERE user_id = ?", (message.from_user.id,))
    row = c.fetchone()
    if not row:
        return await message.answer("❌ You have no access.")
    remaining = int(row[0] - time.time())
    admin = "✅" if row[1] else "❌"
    await message.answer(f"🧾 Access Info:\n⏳ Expires in: {remaining // 3600}h\n👮 Admin: {admin}")

@dp.message(Command("add_admin"))
async def cmd_add_admin(message: Message):
    if message.from_user.id != OWNER_ID:
        return await message.answer("❌ Only owner can add admins.")
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Usage: /add_admin <user_id>")
    user_id = int(args[1])
    c.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    await message.answer("✅ Admin added.")

@dp.message(Command("remove_admin"))
async def cmd_remove_admin(message: Message):
    if message.from_user.id != OWNER_ID:
        return await message.answer("❌ Only owner can remove admins.")
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Usage: /remove_admin <user_id>")
    user_id = int(args[1])
    c.execute("UPDATE users SET is_admin = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    await message.answer("✅ Admin removed.")

@dp.message(Command("check"))
async def cmd_check(message: Message):
    user_id = message.from_user.id
    if not has_access(user_id):
        return await message.answer("❌ You don’t have access.\nDM to buy - @Rohan2349")

    if user_id in cooldown and time.time() - cooldown[user_id] < 5:
        return await message.answer("⌛ Please wait a few seconds before using this again.")
    cooldown[user_id] = time.time()

    card = "4111 1111 1111 1111"
    status = check_stripe(card)
    await message.answer(f"💳 Checking: {card}\nResult: {status}")

# --- Run Bot ---
async def main():
    print("Bot Starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
