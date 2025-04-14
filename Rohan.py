import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import requests
import json
import os
from datetime import datetime, timedelta
import uuid
from dotenv import load_dotenv
from collections import defaultdict
import time
import re
import random
import logging
import httpx
import asyncio

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_TOKEN = os.getenv("API_TOKEN")
API_ENDPOINT = "https://bcheck.tech/api/checks"
ADMIN_FILE = "admins.json"
KEYS_FILE = "keys.json"

# Validate TELEGRAM_TOKEN format
def validate_telegram_token(token):
    """Check if token matches Telegram's format."""
    if not token:
        return False
    # Format: number:alphanumeric (e.g., 123456789:AAF...)
    pattern = r'^\d{8,10}:[A-Za-z0-9_-]{35}$'
    return bool(re.match(pattern, token))

# Load admins
def load_admins():
    if os.path.exists(ADMIN_FILE):
        with open(ADMIN_FILE, "r") as f:
            return json.load(f)
    return [1866961136]  # Default admin ID (replace with yours)

def save_admins(admins):
    with open(ADMIN_FILE, "w") as f:
        json.dump(admins, f, indent=2)

ADMIN_IDS = load_admins()

# Rate limiting: {user_id: [(timestamp, command)]}
REQUESTS = defaultdict(list)
RATE_LIMIT = 5  # Max 5 /check or /vbv per hour
RATE_WINDOW = 3600  # 1 hour in seconds

def load_keys():
    """Load keys from keys.json."""
    if os.path.exists(KEYS_FILE):
        with open(KEYS_FILE, "r") as f:
            return json.load(f)
    return []

def save_keys(keys):
    """Save keys to keys.json."""
    with open(KEYS_FILE, "w") as f:
        json.dump(keys, f, indent=2)

def check_rate_limit(user_id, command):
    """Check if user is within rate limit."""
    now = time.time()
    REQUESTS[user_id] = [req for req in REQUESTS[user_id] if now - req[0] < RATE_WINDOW]
    if len([req for req in REQUESTS[user_id] if req[1] == command]) >= RATE_LIMIT:
        return False
    REQUESTS[user_id].append((now, command))
    return True

def escape_markdown(text):
    """Escape ALL MarkdownV2 reserved characters."""
    if text is None:
        return ""
    chars = r'_*\[\]\(\)~`>#+-=|{}\.!'
    return re.sub(r'([{}])'.format(chars), r'\\\1', str(text))

def mock_bin_lookup(card_number):
    """Simulate BIN info."""
    bin_prefix = card_number[:6]
    if bin_prefix.startswith("4"):
        card_type = "VISA - CREDIT - CLASSIC"
        bank = "JPMORGAN CHASE BANK N.A."
        country = "UNITED STATES 🇺🇸"
    elif bin_prefix.startswith("5"):
        card_type = "MASTERCARD - DEBIT - PERSONAL"
        bank = "SANTANDER BANK, NA"
        country = "UNITED STATES 🇺🇸"
    else:
        card_type = "MASTERCARD - CREDIT - PLATINUM"
        bank = "RAKUTEN CARD CO.,LTD."
        country = "JAPAN 🇯🇵"
    return card_type, bank, country

def generate_fake_us_address():
    """Generate fake US address."""
    first_names = ["Dee", "Alex", "Jordan", "Taylor", "Morgan"]
    last_names = ["Fahey", "Smith", "Johnson", "Brown", "Davis"]
    cities = ["Grand Terrace", "Springfield", "Riverside", "Colton", "Albany"]
    states = ["California", "New York", "Texas", "Florida", "Illinois"]
    zip_codes = ["92313", "10001", "73301", "33101", "60601"]
    domains = ["teleworm.us", "tempmail.com", "fakemail.net"]

    full_name = f"{random.choice(first_names)} {random.choice(last_names)}"
    city = random.choice(cities)
    state = random.choice(states)
    zip_code = random.choice(zip_codes)
    street = f"{random.randint(100, 9999)} Main St"
    address = f"{street}, {city}, {state} {zip_code}"
    phone = ""  # Empty per example
    email = f"{''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=8))}@{random.choice(domains)}"
    return {
        "full_name": full_name,
        "street_address": address,
        "city": city,
        "state": state,
        "zip_code": zip_code,
        "phone": phone,
        "country": "United States 🇺🇸",
        "email": email
    }

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors globally."""
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.message:
        try:
            await update.message.reply_text(
                "🚨 *Error*: Something went wrong. Please try again later.",
                parse_mode="MarkdownV2"
            )
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message."""
    text = (
        "🌟 *Welcome to Card Check Bot!* 🌟\n\n"
        "🔍 *Commands*:\n"
        "🔑 `/gen` \\- Generate key \\(admins\\)\n"
        "✅ `/redeem <key>` \\- Redeem key\n"
        "💳 `/check <card|mm|yyyy|cvv>` \\- Check card\n"
        "🔒 `/vbv <card|mm|yyyy|cvv>` \\- 3DS/VBV check\n"
        "📍 `/fakeus` \\- Fake US address\n"
        "📜 `/mykeys` \\- List keys\n"
        "ℹ️ `/status <key>` \\- Key status\n"
        "🛠️ `/addadmin <user_id>` \\- Add admin\n"
        "🚫 `/removeadmin <user_id>` \\- Remove admin\n"
        "❓ `/help` \\- Help menu\n\n"
        "⚠️ *Test cards only* \\(e.g., 4242424242424242\\)."
    )
    await update.message.reply_text(text, parse_mode="MarkdownV2")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send help message."""
    text = (
        "❓ *Help Menu* ❓\n\n"
        "🔍 *Commands*:\n"
        "🔑 `/gen` \\- Generate key \\(admins\\)\n"
        "✅ `/redeem <key>` \\- Redeem key\n"
        "💳 `/check <card|mm|yyyy|cvv>` \\- Card check\n"
        "🔒 `/vbv <card|mm|yyyy|cvv>` \\- 3DS/VBV check\n"
        "📍 `/fakeus` \\- Fake US address\n"
        "📜 `/mykeys` \\- List keys\n"
        "ℹ️ `/status <key>` \\- Key status\n"
        "🛠️ `/addadmin <user_id>` \\- Add admin\n"
        "🚫 `/removeadmin <user_id>` \\- Remove admin\n"
        "❓ `/help` \\- This menu\n\n"
        "⚠️ *Use test cards!*"
    )
    await update.message.reply_text(text, parse_mode="MarkdownV2")

async def addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add admin."""
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("🚫 *Error*: Only admins can use /addadmin.", parse_mode="MarkdownV2")
        return

    if not context.args:
        await update.message.reply_text("❓ *Usage*: `/addadmin <user_id>`", parse_mode="MarkdownV2")
        return

    try:
        new_admin = int(context.args[0])
        if new_admin in ADMIN_IDS:
            await update.message.reply_text(f"⚠️ *Error*: User {escape_markdown(str(new_admin))} is already an admin.", parse_mode="MarkdownV2")
            return

        ADMIN_IDS.append(new_admin)
        save_admins(ADMIN_IDS)
        await update.message.reply_text(f"✅ *Success*: User {escape_markdown(str(new_admin))} added as admin.", parse_mode="MarkdownV2")
    except ValueError:
        await update.message.reply_text("❌ *Error*: Invalid user ID.", parse_mode="MarkdownV2")

async def removeadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove admin."""
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("🚫 *Error*: Only admins can use /removeadmin.", parse_mode="MarkdownV2")
        return

    if not context.args:
        await update.message.reply_text("❓ *Usage*: `/removeadmin <user_id>`", parse_mode="MarkdownV2")
        return

    try:
        admin_id = int(context.args[0])
        if admin_id == user_id:
            await update.message.reply_text("⚠️ *Error*: You cannot remove yourself.", parse_mode="MarkdownV2")
            return
        if admin_id not in ADMIN_IDS:
            await update.message.reply_text(f"⚠️ *Error*: User {escape_markdown(str(admin_id))} is not an admin.", parse_mode="MarkdownV2")
            return

        ADMIN_IDS.remove(admin_id)
        save_admins(ADMIN_IDS)
        await update.message.reply_text(f"✅ *Success*: User {escape_markdown(str(admin_id))} removed from admins.", parse_mode="MarkdownV2")
    except ValueError:
        await update.message.reply_text("❌ *Error*: Invalid user ID.", parse_mode="MarkdownV2")

async def gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show inline keyboard for key duration."""
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("🚫 *Error*: Only admins can use /gen.", parse_mode="MarkdownV2")
        return

    keyboard = [
        [
            InlineKeyboardButton("1 Day 🕐", callback_data="gen_1"),
            InlineKeyboardButton("3 Days 🕒", callback_data="gen_3"),
        ],
        [
            InlineKeyboardButton("7 Days 🕖", callback_data="gen_7"),
            InlineKeyboardButton("30 Days 🕛", callback_data="gen_30"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🔑 *Select key duration*:", parse_mode="MarkdownV2", reply_markup=reply_markup)

async def gen_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /gen keyboard."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in ADMIN_IDS:
        await query.message.reply_text("🚫 *Error*: Only admins can generate keys.", parse_mode="MarkdownV2")
        return

    try:
        duration = int(query.data.split("_")[1])
        if duration not in [1, 3, 7, 30]:
            await query.message.reply_text("⚠️ *Error*: Invalid duration.", parse_mode="MarkdownV2")
            return

        key = f"{uuid.uuid4().hex[:6].upper()}-{uuid.uuid4().hex[:6].upper()}"
        created_at = datetime.utcnow()
        expires_at = created_at + timedelta(days=duration)

        keys = load_keys()
        keys.append({
            "key": key,
            "duration_days": duration,
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "status": "unused",
            "user_id": None
        })
        save_keys(keys)

        await query.message.reply_text(
            f"✅ *Key Generated* ✅\n"
            f"🔑 *Key*: `{escape_markdown(key)}`\n"
            f"⏳ *Duration*: {escape_markdown(str(duration))} days\n"
            f"📅 *Expires*: {escape_markdown(str(expires_at))}",
            parse_mode="MarkdownV2"
        )
    except Exception as e:
        await query.message.reply_text(f"❌ *Error generating key*: {escape_markdown(str(e))}", parse_mode="MarkdownV2")

async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Redeem a key."""
    user_id = update.message.from_user.id
    if not context.args:
        await update.message.reply_text("❓ *Usage*: `/redeem <key>`", parse_mode="MarkdownV2")
        return

    key = context.args[0].strip()
    keys = load_keys()
    now = datetime.utcnow()

    for k in keys:
        if k["key"] == key:
            expires_at = datetime.fromisoformat(k["expires_at"])
            if k["status"] == "used":
                await update.message.reply_text("🚫 *Error*: Key already used.", parse_mode="MarkdownV2")
                return
            if now > expires_at:
                await update.message.reply_text("⏰ *Error*: Key has expired.", parse_mode="MarkdownV2")
                return

            k["status"] = "used"
            k["user_id"] = user_id
            save_keys(keys)
            await update.message.reply_text(
                f"✅ *Key Redeemed* ✅\n"
                f"🔑 *Key*: `{escape_markdown(key)}`\n"
                f"📅 *Valid until*: {escape_markdown(str(expires_at))}",
                parse_mode="MarkdownV2"
            )
            return

    await update.message.reply_text("❌ *Error*: Invalid key.", parse_mode="MarkdownV2")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Card check via bcheck.tech."""
    user_id = update.message.from_user.id

    if not check_rate_limit(user_id, "check"):
        await update.message.reply_text("⏳ *Error*: Too many /check requests. Wait and try again.", parse_mode="MarkdownV2")
        return

    keys = load_keys()
    now = datetime.utcnow()
    active_key = None
    for k in keys:
        if k["user_id"] == user_id and k["status"] == "used" and datetime.fromisoformat(k["expires_at"]) > now:
            active_key = k["key"]
            break

    if not active_key:
        await update.message.reply_text(
            "🔐 *Error*: You need an active key. Use `/redeem <key>`.",
            parse_mode="MarkdownV2"
        )
        return

    if not context.args:
        await update.message.reply_text(
            "❓ *Usage*: `/check <card|mm|yyyy|cvv>`\n"
            "📌 *Example*: `/check 4242424242424242|12|2026|123`",
            parse_mode="MarkdownV2"
        )
        return

    card_input = " ".join(context.args)
    try:
        card_number, exp_month, exp_year, cvc = card_input.split("|")
        card_number = card_number.strip()
        exp_month = exp_month.strip()
        exp_year = exp_year.strip()
        cvc = cvc.strip()

        if not (card_number.isdigit() and len(card_number) >= 15 and len(card_number) <= 16):
            await update.message.reply_text("❌ *Error*: Invalid card number.", parse_mode="MarkdownV2")
            return
        if not (exp_month.isdigit() and 1 <= int(exp_month) <= 12):
            await update.message.reply_text("❌ *Error*: Invalid month.", parse_mode="MarkdownV2")
            return
        if not (exp_year.isdigit() and 2025 <= int(exp_year) <= 2035):
            await update.message.reply_text("❌ *Error*: Invalid year.", parse_mode="MarkdownV2")
            return
        if not (cvc.isdigit() and len(cvc) in [3, 4]):
            await update.message.reply_text("❌ *Error*: Invalid CVC.", parse_mode="MarkdownV2")
            return

        start_time = time.time()
        if card_number != "4242424242424242":
            await update.message.reply_text(
                f"⚠️ *Demo Mode* ⚠️\n"
                f"💳 *Card*: `{escape_markdown(card_number)}`\n"
                f"🔐 Using test card for API call.",
                parse_mode="MarkdownV2"
            )
            card_number = "4242424242424242"
            exp_month = "12"
            exp_year = "2026"
            cvc = "123"

        try:
            payload = {
                "card_number": card_number,
                "exp_month": exp_month,
                "exp_year": exp_year,
                "cvc": cvc
            }
            headers = {
                "Authorization": f"Bearer {API_TOKEN}",
                "Content-Type": "application/json"
            }
            response = requests.post(API_ENDPOINT, json=payload, headers=headers)
            elapsed_time = time.time() - start_time
            response_data = response.json()

            card_type, bank, country = mock_bin_lookup(card_number)
            card_details = f"{card_number}|{exp_month}|{exp_year}|{cvc}"
            if response.status_code == 200 and response_data.get("valid", False):
                await update.message.reply_text(
                    f"✅ *Approved* ✅\n\n"
                    f"💳 *CC* ⇾ `{escape_markdown(card_details)}`\n"
                    f"🌐 *Gateway* ⇾ Braintree Auth 1\n"
                    f"📋 *Response* ⇾ Approved\n\n"
                    f"🔍 *BIN Info*: {escape_markdown(card_type)}\n"
                    f"🏦 *Bank*: {escape_markdown(bank)}\n"
                    f"🌍 *Country*: {escape_markdown(country)}\n\n"
                    f"⏱️ *Took* {escape_markdown(str(elapsed_time)):.2f} seconds [ FREE ]",
                    parse_mode="MarkdownV2"
                )
            else:
                error = response_data.get("error", "Processor Declined - Fraud Suspected")
                await update.message.reply_text(
                    f"❌ *Declined* ❌\n\n"
                    f"💳 *CC* ⇾ `{escape_markdown(card_details)}`\n"
                    f"🌐 *Gateway* ⇾ Braintree Auth 1\n"
                    f"📋 *Response* ⇾ {escape_markdown(error)}\n\n"
                    f"🔍 *BIN Info*: {escape_markdown(card_type)}\n"
                    f"🏦 *Bank*: {escape_markdown(bank)}\n"
                    f"🌍 *Country*: {escape_markdown(country)}\n\n"
                    f"⏱️ *Took* {escape_markdown(str(elapsed_time)):.2f} seconds [ FREE ]",
                    parse_mode="MarkdownV2"
                )
        except requests.exceptions.RequestException as e:
            await update.message.reply_text(
                f"🚨 *Connection Error* 🚨\n"
                f"💬 *Details*: {escape_markdown(str(e))}",
                parse_mode="MarkdownV2"
            )
        except ValueError:
            await update.message.reply_text("❌ *Error*: Invalid API response.", parse_mode="MarkdownV2")
    except ValueError:
        await update.message.reply_text(
            "❓ *Usage*: `/check <card|mm|yyyy|cvv>`\n"
            "📌 *Example*: `/check 4242424242424242|12|2026|123`",
            parse_mode="MarkdownV2"
        )

async def vbv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """3DS/VBV check via bcheck.tech."""
    user_id = update.message.from_user.id

    if not check_rate_limit(user_id, "vbv"):
        await update.message.reply_text("⏳ *Error*: Too many /vbv requests. Wait and try again.", parse_mode="MarkdownV2")
        return

    keys = load_keys()
    now = datetime.utcnow()
    active_key = None
    for k in keys:
        if k["user_id"] == user_id and k["status"] == "used" and datetime.fromisoformat(k["expires_at"]) > now:
            active_key = k["key"]
            break

    if not active_key:
        await update.message.reply_text(
            "🔐 *Error*: You need an active key. Use `/redeem <key>`.",
            parse_mode="MarkdownV2"
        )
        return

    if not context.args:
        await update.message.reply_text(
            "❓ *Usage*: `/vbv <card|mm|yyyy|cvv>`\n"
            "📌 *Example*: `/vbv 4242424242424242|12|2026|123`",
            parse_mode="MarkdownV2"
        )
        return

    card_input = " ".join(context.args)
    try:
        card_number, exp_month, exp_year, cvc = card_input.split("|")
        card_number = card_number.strip()
        exp_month = exp_month.strip()
        exp_year = exp_year.strip()
        cvc = cvc.strip()

        if not (card_number.isdigit() and len(card_number) >= 15 and len(card_number) <= 16):
            await update.message.reply_text("❌ *Error*: Invalid card number.", parse_mode="MarkdownV2")
            return
        if not (exp_month.isdigit() and 1 <= int(exp_month) <= 12):
            await update.message.reply_text("❌ *Error*: Invalid month.", parse_mode="MarkdownV2")
            return
        if not (exp_year.isdigit() and 2025 <= int(exp_year) <= 2035):
            await update.message.reply_text("❌ *Error*: Invalid year.", parse_mode="MarkdownV2")
            return
        if not (cvc.isdigit() and len(cvc) in [3, 4]):
            await update.message.reply_text("❌ *Error*: Invalid CVC.", parse_mode="MarkdownV2")
            return

        start_time = time.time()
        if card_number != "4242424242424242":
            await update.message.reply_text(
                f"⚠️ *Demo Mode* ⚠️\n"
                f"💳 *Card*: `{escape_markdown(card_number)}`\n"
                f"🔐 Using test card for API call.",
                parse_mode="MarkdownV2"
            )
            card_number = "4242424242424242"
            exp_month = "12"
            exp_year = "2026"
            cvc = "123"

        try:
            payload = {
                "card_number": card_number,
                "exp_month": exp_month,
                "exp_year": exp_year,
                "cvc": cvc,
                "3ds_check": True
            }
            headers = {
                "Authorization": f"Bearer {API_TOKEN}",
                "Content-Type": "application/json"
            }
            response = requests.post(API_ENDPOINT, json=payload, headers=headers)
            elapsed_time = time.time() - start_time
            response_data = response.json()

            card_type, bank, country = mock_bin_lookup(card_number)
            card_details = f"{card_number}|{exp_month}|{exp_year}|{cvc}"
            if response.status_code == 200 and response_data.get("valid", False):
                await update.message.reply_text(
                    f"✅ *Approved* ✅\n\n"
                    f"💳 *CC* ⇾ `{escape_markdown(card_details)}`\n"
                    f"🌐 *Gateway* ⇾ 3DS Lookup\n"
                    f"📋 *Response* ⇾ Approved\n\n"
                    f"🔍 *Info*: {escape_markdown(card_type)}\n"
                    f"🏦 *Issuer*: {escape_markdown(bank)}\n"
                    f"🌍 *Country*: {escape_markdown(country)}\n\n"
                    f"⏱️ *Time*: {escape_markdown(str(elapsed_time)):.2f} seconds",
                    parse_mode="MarkdownV2"
                )
            else:
                error = response_data.get("error", "3DS Authentication Rejected")
                await update.message.reply_text(
                    f"❌ *Rejected* ❌\n\n"
                    f"💳 *Card*: `{escape_markdown(card_details)}`\n"
                    f"🌐 *Gateway*: 3DS Lookup\n"
                    f"📋 *Response*: {escape_markdown(error)}\n\n"
                    f"🔍 *Info*: {escape_markdown(card_type)}\n"
                    f"🏦 *Issuer*: {escape_markdown(bank)}\n"
                    f"🌍 *Country*: {escape_markdown(country)}\n\n"
                    f"⏱️ *Time*: {escape_markdown(str(elapsed_time)):.2f} seconds",
                    parse_mode="MarkdownV2"
                )
        except requests.exceptions.RequestException as e:
            await update.message.reply_text(
                f"🚨 *Connection Error* 🚨\n"
                f"💬 *Details*: {escape_markdown(str(e))}",
                parse_mode="MarkdownV2"
            )
        except ValueError:
            await update.message.reply_text("❌ *Error*: Invalid API response.", parse_mode="MarkdownV2")
    except ValueError:
        await update.message.reply_text(
            "❓ *Usage*: `/vbv <card|mm|yyyy|cvv>`\n"
            "📌 *Example*: `/vbv 4242424242424242|12|2026|123`",
            parse_mode="MarkdownV2"
        )

async def fakeus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate fake US address."""
    address = generate_fake_us_address()
    await update.message.reply_text(
        f"📍 *United States Address Generator* 📍\n\n"
        f"👤 *Full Name*: {escape_markdown(address['full_name'])}\n"
        f"🏠 *Street Address*: {escape_markdown(address['street_address'])}\n"
        f"🏙️ *City/Town/Village*: {escape_markdown(address['city'])}\n"
        f"🌎 *State/Province/Region*: {escape_markdown(address['state'])}\n"
        f"📮 *Postal Code*: {escape_markdown(address['zip_code'])}\n"
        f"📞 *Phone Number*: {escape_markdown(address['phone'])}\n"
        f"🇺🇸 *Country*: {escape_markdown(address['country'])}\n"
        f"📧 *Temporary Email*: `{escape_markdown(address['email'])}` \\(Open link\\)",
        parse_mode="MarkdownV2"
    )

async def mykeys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List active keys."""
    user_id = update.message.from_user.id
    keys = load_keys()
    now = datetime.utcnow()
    active_keys = [
        k for k in keys
        if k["user_id"] == user_id and k["status"] == "used" and datetime.fromisoformat(k["expires_at"]) > now
    ]

    if not active_keys:
        await update.message.reply_text(
            "📭 *No Active Keys* 📭\n"
            "🔐 Use `/redeem <key>`.",
            parse_mode="MarkdownV2"
        )
        return

    response = "🔑 *Your Active Keys* 🔑\n\n"
    for k in active_keys:
        expires_at = datetime.fromisoformat(k["expires_at"])
        response += (
            f"🔐 *Key*: `{escape_markdown(k['key'])}`\n"
            f"⏳ *Expires*: {escape_markdown(str(expires_at))}\n\n"
        )
    await update.message.reply_text(response, parse_mode="MarkdownV2")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check key status."""
    if not context.args:
        await update.message.reply_text("❓ *Usage*: `/status <key>`", parse_mode="MarkdownV2")
        return

    key = context.args[0].strip()
    keys = load_keys()
    now = datetime.utcnow()

    for k in keys:
        if k["key"] == key:
            expires_at = datetime.fromisoformat(k["expires_at"])
            status = "✅ Used" if k["status"] == "used" and now <= expires_at else "🔓 Unused" if now <= expires_at else "⏰ Expired"
            response = (
                f"🔑 *Key Status* 🔑\n\n"
                f"🔐 *Key*: `{escape_markdown(key)}`\n"
                f"📋 *Status*: {escape_markdown(status)}\n"
                f"⏳ *Duration*: {escape_markdown(str(k['duration_days']))} days\n"
                f"📅 *Expires*: {escape_markdown(str(expires_at))}"
            )
            if k["user_id"]:
                response += f"\n👤 *User ID*: {escape_markdown(str(k['user_id']))}"
            await update.message.reply_text(response, parse_mode="MarkdownV2")
            return

    await update.message.reply_text("❌ *Error*: Key not found.", parse_mode="MarkdownV2")

async def initialize_with_retries(application, max_attempts=3, delay=5):
    """Initialize bot with retries."""
    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(f"Attempt {attempt}/{max_attempts} to initialize bot")
            await application.initialize()
            logger.info("Bot initialized successfully")
            return True
        except telegram.error.TimedOut as e:
            logger.warning(f"Timeout on attempt {attempt}: {e}")
            if attempt == max_attempts:
                logger.error("Max retries reached. Failed to initialize bot.")
                return False
            await asyncio.sleep(delay)
        except telegram.error.InvalidToken as e:
            logger.error(f"Invalid token: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error on attempt {attempt}: {e}")
            return False
    return False

def main():
    """Run the bot."""
    if not TELEGRAM_TOKEN or not API_TOKEN:
        logger.error("TELEGRAM_TOKEN or API_TOKEN missing in .env")
        return

    if not validate_telegram_token(TELEGRAM_TOKEN):
        logger.error("Invalid TELEGRAM_TOKEN format")
        return

    # Create Application with custom HTTPX client
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=10.0, read=10.0, write=10.0)
    )
    application = Application.builder().token(TELEGRAM_TOKEN).http_client(http_client).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("addadmin", addadmin))
    application.add_handler(CommandHandler("removeadmin", removeadmin))
    application.add_handler(CommandHandler("gen", gen))
    application.add_handler(CallbackQueryHandler(gen_callback, pattern="^gen_"))
    application.add_handler(CommandHandler("redeem", redeem))
    application.add_handler(CommandHandler("check", check))
    application.add_handler(CommandHandler("vbv", vbv))
    application.add_handler(CommandHandler("fakeus", fakeus))
    application.add_handler(CommandHandler("mykeys", mykeys))
    application.add_handler(CommandHandler("status", status))
    application.add_error_handler(error_handler)

    # Run with retries
    loop = asyncio.get_event_loop()
    success = loop.run_until_complete(initialize_with_retries(application))
    if not success:
        logger.error("Failed to start bot after retries")
        return

    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    finally:
        loop.run_until_complete(application.http_client.aclose())
        logger.info("HTTP client closed")

if __name__ == "__main__":
    main()