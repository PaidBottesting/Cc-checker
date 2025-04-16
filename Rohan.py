import sqlite3
import time
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import logging
import random
import requests

logging.basicConfig(level=logging.INFO)

API_TOKEN = '7655173404:AAF3FadHz2zQbXGmrWwGUgaBN35LFnXiVoo'
OWNER_ID = 1866961136
STRIPE_API_KEY = 'pk_live_Ng5VkKcI3Ur3KZ92goEDVRBq'  # Add your Stripe API Key here
BIN_API_URL = 'https://lookup.binlist.net/'  # Example BIN API URL

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

conn = sqlite3.connect("users.db", check_same_thread=False)
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER, expires_at INTEGER, is_admin INTEGER DEFAULT 0)")
conn.commit()

cooldown = {}

# Auto remove expired access daily at 12:00AM IST
def remove_expired_users():
    now = int(time.time())
    c.execute("DELETE FROM users WHERE expires_at <= ?", (now,))
    conn.commit()
    print("⏰ Expired access removed.")

scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Kolkata'))
scheduler.add_job(remove_expired_users, 'cron', hour=0, minute=0)
scheduler.start()

# Utils
def is_admin(user_id):
    c.execute("SELECT 1 FROM users WHERE user_id = ? AND is_admin = 1", (user_id,))
    return c.fetchone() is not None

def has_access(user_id):
    c.execute("SELECT expires_at FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if row:
        return row[0] > time.time()
    return False

# Stripe API function for /check
def check_stripe(card_number):
    # Example request to Stripe to simulate card check
    stripe_url = "https://api.stripe.com/v1/tokens"
    headers = {"Authorization": f"Bearer {STRIPE_API_KEY}"}
    payload = {
        "card": {
            "number": card_number,
            "exp_month": "12",
            "exp_year": "2023",
            "cvc": "123"
        }
    }
    response = requests.post(stripe_url, headers=headers, data=payload)
    if response.status_code == 200:
        data = response.json()
        return "✅ Approved - 3D Secure Passed"
    else:
        return "❌ Declined - Stripe API Failed"

# BIN Code API function for /bin
def get_bin_info(bin_number):
    # Example request to BIN lookup API
    response = requests.get(f"{BIN_API_URL}{bin_number}")
    if response.status_code == 200:
        data = response.json()
        bank = data.get('bank', {}).get('name', 'Unknown')
        country = data.get('country', {}).get('name', 'Unknown')
        card_type = data.get('type', 'Unknown')
        return f"Bank: {bank}\nCountry: {country}\nType: {card_type}"
    else:
        return "❌ BIN not found"

# Commands
@dp.message_handler(commands=['start'])
async def start_cmd(msg: types.Message):
    await msg.reply("👋 Welcome to CC Checker Bot!\nUse /redeem to get access.\nFree tools: /bin /fakeus")

@dp.message_handler(commands=['fakeus'])
async def fakeus_cmd(msg: types.Message):
    await msg.reply("🇺🇸 Fake US Info:\nName: John Doe\nCard: 4111 1111 1111 1111\nExp: 12/27\nCVV: 123")

@dp.message_handler(commands=['bin'])
async def bin_cmd(msg: types.Message):
    bin_number = msg.text.split(" ")[1] if len(msg.text.split()) > 1 else None
    if not bin_number:
        return await msg.reply("Please provide a BIN. Example: /bin 411111")
    
    bin_info = get_bin_info(bin_number)
    await msg.reply(f"🔍 BIN Info:\n{bin_info}")

@dp.message_handler(commands=['vbv'])
async def vbv_cmd(msg: types.Message):
    if not has_access(msg.from_user.id):
        return await msg.reply("❌ You don’t have access.\nDM to buy - @Rohan2349")
    result = random.choice(["✅ Approved - 3D Secure Passed", "❌ Declined - VBV Failed"])
    await msg.reply(f"🔐 VBV Check Result:\n{result}")

@dp.message_handler(commands=['redeem'])
async def redeem_cmd(msg: types.Message):
    code = msg.text.split(" ")[-1] if len(msg.text.split()) > 1 else None
    if not code:
        return await msg.reply("Please provide a code. Example: /redeem Rohan-XXXX")
    if not code.startswith("Rohan-"):
        return await msg.reply("Invalid code format.")
    duration = 86400  # 1 day default
    if "1" in code: duration = 3600
    elif "3" in code: duration = 86400 * 3
    elif "5" in code: duration = 86400 * 5
    elif "7" in code: duration = 86400 * 7
    elif "30" in code: duration = 86400 * 30
    expires_at = int(time.time()) + duration
    c.execute("REPLACE INTO users (user_id, expires_at, is_admin) VALUES (?, ?, ?)", (msg.from_user.id, expires_at, 0))
    conn.commit()
    await msg.reply(f"✅ Access granted for {duration//86400} day(s)!")

@dp.message_handler(commands=['info'])
async def info_cmd(msg: types.Message):
    c.execute("SELECT expires_at, is_admin FROM users WHERE user_id = ?", (msg.from_user.id,))
    row = c.fetchone()
    if not row:
        return await msg.reply("❌ You have no access.")
    remaining = int(row[0] - time.time())
    admin = "✅" if row[1] else "❌"
    await msg.reply(f"🧾 Access Info:\n⏳ Expires in: {remaining//3600}h\n👮 Admin: {admin}")

@dp.message_handler(commands=['add_admin'])
async def add_admin_cmd(msg: types.Message):
    if msg.from_user.id != OWNER_ID:
        return await msg.reply("❌ Only owner can add admins.")
    if len(msg.text.split()) < 2:
        return await msg.reply("Usage: /add_admin <user_id>")
    user_id = int(msg.text.split()[1])
    c.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    await msg.reply("✅ Admin added.")

@dp.message_handler(commands=['remove_admin'])
async def remove_admin_cmd(msg: types.Message):
    if msg.from_user.id != OWNER_ID:
        return await msg.reply("❌ Only owner can remove admins.")
    if len(msg.text.split()) < 2:
        return await msg.reply("Usage: /remove_admin <user_id>")
    user_id = int(msg.text.split()[1])
    c.execute("UPDATE users SET is_admin = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    await msg.reply("✅ Admin removed.")

@dp.message_handler(commands=['check'])
async def check_cmd(msg: types.Message):
    user_id = msg.from_user.id
    if not has_access(user_id):
        return await msg.reply("❌ You don’t have access.\nDM to buy - @Rohan2349")

    if user_id in cooldown and time.time() - cooldown[user_id] < 5:
        return await msg.reply("⌛ Please wait a few seconds before using this again.")
    cooldown[user_id] = time.time()

    # Simulate real CC check using Stripe API
    card = "4111 1111 1111 1111"
    status = check_stripe(card)
    await msg.reply(f"💳 Checking: {card}\nResult: {status}")

if __name__ == '__main__':
    print("Bot Starting...")
    asyncio.run(dp.start_polling())
