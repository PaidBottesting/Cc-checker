import telegram
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
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

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_TOKEN = os.getenv("API_TOKEN")
API_ENDPOINT = "https://bcheck.tech/api/checks"
ADMIN_FILE = "admins.json"
KEYS_FILE = "keys.json"

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
    """Escape special characters for MarkdownV2."""
    chars = r'_*[]()~`>#+-=|{}.!'
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

def start(update, context):
    """Send welcome message."""
    update.message.reply_text(
        "🌟 *Welcome to Card Check Bot!* 🌟\n\n"
        "🔍 *Commands*:\n"
        "🔑 `/gen` - Generate key (admins)\n"
        "✅ `/redeem <key>` - Redeem key\n"
        "💳 `/check <card|mm|yyyy|cvv>` - Check card\n"
        "🔒 `/vbv <card|mm|yyyy|cvv>` - 3DS/VBV check\n"
        "📍 `/fakeus` - Fake US address\n"
        "📜 `/mykeys` - List keys\n"
        "ℹ️ `/status <key>` - Key status\n"
        "🛠️ `/addadmin <user_id>` - Add admin\n"
        "🚫 `/removeadmin <user_id>` - Remove admin\n"
        "❓ `/help` - Help menu\n\n"
        "⚠️ *Test cards only* (e.g., 4242424242424242).",
        parse_mode="MarkdownV2"
    )

def help_command(update, context):
    """Send help message."""
    update.message.reply_text(
        "❓ *Help Menu* ❓\n\n"
        "🔍 *Commands*:\n"
        "🔑 `/gen` - Generate key (admins)\n"
        "✅ `/redeem <key>` - Redeem key\n"
        "💳 `/check <card|mm|yyyy|cvv>` - Card check\n"
        "🔒 `/vbv <card|mm|yyyy|cvv>` - 3DS/VBV check\n"
        "📍 `/fakeus` - Fake US address\n"
        "📜 `/mykeys` - List keys\n"
        "ℹ️ `/status <key>` - Key status\n"
        "🛠️ `/addadmin <user_id>` - Add admin\n"
        "🚫 `/removeadmin <user_id>` - Remove admin\n"
        "❓ `/help` - This menu\n\n"
        "⚠️ *Use test cards!*",
        parse_mode="MarkdownV2"
    )

def addadmin(update, context):
    """Add admin."""
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        update.message.reply_text("🚫 *Error*: Only admins can use /addadmin.", parse_mode="MarkdownV2")
        return

    if not context.args:
        update.message.reply_text("❓ *Usage*: `/addadmin <user_id>`", parse_mode="MarkdownV2")
        return

    try:
        new_admin = int(context.args[0])
        if new_admin in ADMIN_IDS:
            update.message.reply_text(f"⚠️ *Error*: User {escape_markdown(new_admin)} is already an admin.", parse_mode="MarkdownV2")
            return

        ADMIN_IDS.append(new_admin)
        save_admins(ADMIN_IDS)
        update.message.reply_text(f"✅ *Success*: User {escape_markdown(new_admin)} added as admin.", parse_mode="MarkdownV2")
    except ValueError:
        update.message.reply_text("❌ *Error*: Invalid user ID.", parse_mode="MarkdownV2")

def removeadmin(update, context):
    """Remove admin."""
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        update.message.reply_text("🚫 *Error*: Only admins can use /removeadmin.", parse_mode="MarkdownV2")
        return

    if not context.args:
        update.message.reply_text("❓ *Usage*: `/removeadmin <user_id>`", parse_mode="MarkdownV2")
        return

    try:
        admin_id = int(context.args[0])
        if admin_id == user_id:
            update.message.reply_text("⚠️ *Error*: You cannot remove yourself.", parse_mode="MarkdownV2")
            return
        if admin_id not in ADMIN_IDS:
            update.message.reply_text(f"⚠️ *Error*: User {escape_markdown(admin_id)} is not an admin.", parse_mode="MarkdownV2")
            return

        ADMIN_IDS.remove(admin_id)
        save_admins(ADMIN_IDS)
        update.message.reply_text(f"✅ *Success*: User {escape_markdown(admin_id)} removed from admins.", parse_mode="MarkdownV2")
    except ValueError:
        update.message.reply_text("❌ *Error*: Invalid user ID.", parse_mode="MarkdownV2")

def gen(update, context):
    """Show inline keyboard for key duration."""
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        update.message.reply_text("🚫 *Error*: Only admins can use /gen.", parse_mode="MarkdownV2")
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
    update.message.reply_text("🔑 *Select key duration*:", parse_mode="MarkdownV2", reply_markup=reply_markup)

def gen_callback(update, context):
    """Handle /gen keyboard."""
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id

    if user_id not in ADMIN_IDS:
        query.message.reply_text("🚫 *Error*: Only admins can generate keys.", parse_mode="MarkdownV2")
        return

    try:
        duration = int(query.data.split("_")[1])
        if duration not in [1, 3, 7, 30]:
            query.message.reply_text("⚠️ *Error*: Invalid duration.", parse_mode="MarkdownV2")
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

        query.message.reply_text(
            f"✅ *Key Generated* ✅\n"
            f"🔑 *Key*: `{escape_markdown(key)}`\n"
            f"⏳ *Duration*: {duration} days\n"
            f"📅 *Expires*: {escape_markdown(expires_at)}",
            parse_mode="MarkdownV2"
        )
    except Exception as e:
        query.message.reply_text(f"❌ *Error generating key*: {escape_markdown(str(e))}", parse_mode="MarkdownV2")

def redeem(update, context):
    """Redeem a key."""
    user_id = update.message.from_user.id
    if not context.args:
        update.message.reply_text("❓ *Usage*: `/redeem <key>`", parse_mode="MarkdownV2")
        return

    key = context.args[0].strip()
    keys = load_keys()
    now = datetime.utcnow()

    for k in keys:
        if k["key"] == key:
            expires_at = datetime.fromisoformat(k["expires_at"])
            if k["status"] == "used":
                update.message.reply_text("🚫 *Error*: Key already used.", parse_mode="MarkdownV2")
                return
            if now > expires_at:
                update.message.reply_text("⏰ *Error*: Key has expired.", parse_mode="MarkdownV2")
                return

            k["status"] = "used"
            k["user_id"] = user_id
            save_keys(keys)
            update.message.reply_text(
                f"✅ *Key Redeemed* ✅\n"
                f"🔑 *Key*: `{escape_markdown(key)}`\n"
                f"📅 *Valid until*: {escape_markdown(expires_at)}",
                parse_mode="MarkdownV2"
            )
            return

    update.message.reply_text("❌ *Error*: Invalid key.", parse_mode="MarkdownV2")

def check(update, context):
    """Card check via bcheck.tech."""
    user_id = update.message.from_user.id

    if not check_rate_limit(user_id, "check"):
        update.message.reply_text("⏳ *Error*: Too many /check requests. Wait and try again.", parse_mode="MarkdownV2")
        return

    keys = load_keys()
    now = datetime.utcnow()
    active_key = None
    for k in keys:
        if k["user_id"] == user_id and k["status"] == "used" and datetime.fromisoformat(k["expires_at"]) > now:
            active_key = k["key"]
            break

    if not active_key:
        update.message.reply_text(
            "🔐 *Error*: You need an active key. Use `/redeem <key>`.",
            parse_mode="MarkdownV2"
        )
        return

    if not context.args:
        update.message.reply_text(
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
            update.message.reply_text("❌ *Error*: Invalid card number.", parse_mode="MarkdownV2")
            return
        if not (exp_month.isdigit() and 1 <= int(exp_month) <= 12):
            update.message.reply_text("❌ *Error*: Invalid month.", parse_mode="MarkdownV2")
            return
        if not (exp_year.isdigit() and 2025 <= int(exp_year) <= 2035):
            update.message.reply_text("❌ *Error*: Invalid year.", parse_mode="MarkdownV2")
            return
        if not (cvc.isdigit() and len(cvc) in [3, 4]):
            update.message.reply_text("❌ *Error*: Invalid CVC.", parse_mode="MarkdownV2")
            return

        start_time = time.time()
        if card_number != "4242424242424242":
            update.message.reply_text(
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
            if response.status_code == 200 and response_data.get("valid", False):
                update.message.reply_text(
                    f"✅ *Approved* ✅\n\n"
                    f"💳 *CC* ⇾ `{escape_markdown(card_number)}|{exp_month}|{exp_year}|{cvc}`\n"
                    f"🌐 *Gateway* ⇾ Braintree Auth 1\n"
                    f"📋 *Response* ⇾ Approved\n\n"
                    f"🔍 *BIN Info*: {escape_markdown(card_type)}\n"
                    f"🏦 *Bank*: {escape_markdown(bank)}\n"
                    f"🌍 *Country*: {escape_markdown(country)}\n\n"
                    f"⏱️ *Took* {elapsed_time:.2f} seconds [ FREE ]",
                    parse_mode="MarkdownV2"
                )
            else:
                error = response_data.get("error", "Processor Declined - Fraud Suspected")
                update.message.reply_text(
                    f"❌ *Declined* ❌\n\n"
                    f"💳 *CC* ⇾ `{escape_markdown(card_number)}|{exp_month}|{exp_year}|{cvc}`\n"
                    f"🌐 *Gateway* ⇾ Braintree Auth 1\n"
                    f"📋 *Response* ⇾ {escape_markdown(error)}\n\n"
                    f"🔍 *BIN Info*: {escape_markdown(card_type)}\n"
                    f"🏦 *Bank*: {escape_markdown(bank)}\n"
                    f"🌍 *Country*: {escape_markdown(country)}\n\n"
                    f"⏱️ *Took* {elapsed_time:.2f} seconds [ FREE ]",
                    parse_mode="MarkdownV2"
                )
        except requests.exceptions.RequestException as e:
            update.message.reply_text(
                f"🚨 *Connection Error* 🚨\n"
                f"💬 *Details*: {escape_markdown(str(e))}",
                parse_mode="MarkdownV2"
            )
        except ValueError:
            update.message.reply_text("❌ *Error*: Invalid API response.", parse_mode="MarkdownV2")
    except ValueError:
        update.message.reply_text(
            "❓ *Usage*: `/check <card|mm|yyyy|cvv>`\n"
            "📌 *Example*: `/check 4242424242424242|12|2026|123`",
            parse_mode="MarkdownV2"
        )

def vbv(update, context):
    """3DS/VBV check via bcheck.tech."""
    user_id = update.message.from_user.id

    if not check_rate_limit(user_id, "vbv"):
        update.message.reply_text("⏳ *Error*: Too many /vbv requests. Wait and try again.", parse_mode="MarkdownV2")
        return

    keys = load_keys()
    now = datetime.utcnow()
    active_key = None
    for k in keys:
        if k["user_id"] == user_id and k["status"] == "used" and datetime.fromisoformat(k["expires_at"]) > now:
            active_key = k["key"]
            break

    if not active_key:
        update.message.reply_text(
            "🔐 *Error*: You need an active key. Use `/redeem <key>`.",
            parse_mode="MarkdownV2"
        )
        return

    if not context.args:
        update.message.reply_text(
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
            update.message.reply_text("❌ *Error*: Invalid card number.", parse_mode="MarkdownV2")
            return
        if not (exp_month.isdigit() and 1 <= int(exp_month) <= 12):
            update.message.reply_text("❌ *Error*: Invalid month.", parse_mode="MarkdownV2")
            return
        if not (exp_year.isdigit() and 2025 <= int(exp_year) <= 2035):
            update.message.reply_text("❌ *Error*: Invalid year.", parse_mode="MarkdownV2")
            return
        if not (cvc.isdigit() and len(cvc) in [3, 4]):
            update.message.reply_text("❌ *Error*: Invalid CVC.", parse_mode="MarkdownV2")
            return

        start_time = time.time()
        if card_number != "4242424242424242":
            update.message.reply_text(
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
            if response.status_code == 200 and response_data.get("valid", False):
                update.message.reply_text(
                    f"✅ *Approved* ✅\n\n"
                    f"💳 *CC* ⇾ `{escape_markdown(card_number)}|{exp_month}|{exp_year}|{cvc}`\n"
                    f"🌐 *Gateway* ⇾ 3DS Lookup\n"
                    f"📋 *Response* ⇾ Approved\n\n"
                    f"🔍 *Info*: {escape_markdown(card_type)}\n"
                    f"🏦 *Issuer*: {escape_markdown(bank)}\n"
                    f"🌍 *Country*: {escape_markdown(country)}\n\n"
                    f"⏱️ *Time*: {elapsed_time:.2f} seconds",
                    parse_mode="MarkdownV2"
                )
            else:
                error = response_data.get("error", "3DS Authentication Rejected")
                update.message.reply_text(
                    f"❌ *Rejected* ❌\n\n"
                    f"💳 *Card*: `{escape_markdown(card_number)}|{exp_month}|{exp_year}|{cvc}`\n"
                    f"🌐 *Gateway*: 3DS Lookup\n"
                    f"📋 *Response*: {escape_markdown(error)}\n\n"
                    f"🔍 *Info*: {escape_markdown(card_type)}\n"
                    f"🏦 *Issuer*: {escape_markdown(bank)}\n"
                    f"🌍 *Country*: {escape_markdown(country)}\n\n"
                    f"⏱️ *Time*: {elapsed_time:.2f} seconds",
                    parse_mode="MarkdownV2"
                )
        except requests.exceptions.RequestException as e:
            update.message.reply_text(
                f"🚨 *Connection Error* 🚨\n"
                f"💬 *Details*: {escape_markdown(str(e))}",
                parse_mode="MarkdownV2"
            )
        except ValueError:
            update.message.reply_text("❌ *Error*: Invalid API response.", parse_mode="MarkdownV2")
    except ValueError:
        update.message.reply_text(
            "❓ *Usage*: `/vbv <card|mm|yyyy|cvv>`\n"
            "📌 *Example*: `/vbv 4242424242424242|12|2026|123`",
            parse_mode="MarkdownV2"
        )

def fakeus(update, context):
    """Generate fake US address."""
    address = generate_fake_us_address()
    update.message.reply_text(
        f"📍 *United States Address Generator* 📍\n\n"
        f"👤 *Full Name*: {escape_markdown(address['full_name'])}\n"
        f"🏠 *Street Address*: {escape_markdown(address['street_address'])}\n"
        f"🏙️ *City/Town/Village*: {escape_markdown(address['city'])}\n"
        f"🌎 *State/Province/Region*: {escape_markdown(address['state'])}\n"
        f"📮 *Postal Code*: {escape_markdown(address['zip_code'])}\n"
        f"📞 *Phone Number*: {escape_markdown(address['phone'])}\n"
        f"🇺🇸 *Country*: {escape_markdown(address['country'])}\n"
        f"📧 *Temporary Email*: `{escape_markdown(address['email'])}` (Open link)",
        parse_mode="MarkdownV2"
    )

def mykeys(update, context):
    """List active keys."""
    user_id = update.message.from_user.id
    keys = load_keys()
    now = datetime.utcnow()
    active_keys = [
        k for k in keys
        if k["user_id"] == user_id and k["status"] == "used" and datetime.fromisoformat(k["expires_at"]) > now
    ]

    if not active_keys:
        update.message.reply_text(
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
            f"⏳ *Expires*: {escape_markdown(expires_at)}\n\n"
        )
    update.message.reply_text(response, parse_mode="MarkdownV2")

def status(update, context):
    """Check key status."""
    if not context.args:
        update.message.reply_text("❓ *Usage*: `/status <key>`", parse_mode="MarkdownV2")
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
                f"📋 *Status*: {status}\n"
                f"⏳ *Duration*: {k['duration_days']} days\n"
                f"📅 *Expires*: {escape_markdown(expires_at)}"
            )
            if k["user_id"]:
                response += f"\n👤 *User ID*: {escape_markdown(k['user_id'])}"
            update.message.reply_text(response, parse_mode="MarkdownV2")
            return

    update.message.reply_text("❌ *Error*: Key not found.", parse_mode="MarkdownV2")

def main():
    """Run the bot."""
    if not TELEGRAM_TOKEN or not API_TOKEN:
        print("Error: TELEGRAM_TOKEN or API_TOKEN missing in .env")
        return

    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("addadmin", addadmin))
    dp.add_handler(CommandHandler("removeadmin", removeadmin))
    dp.add_handler(CommandHandler("gen", gen))
    dp.add_handler(CallbackQueryHandler(gen_callback, pattern="^gen_"))
    dp.add_handler(CommandHandler("redeem", redeem))
    dp.add_handler(CommandHandler("check", check))
    dp.add_handler(CommandHandler("vbv", vbv))
    dp.add_handler(CommandHandler("fakeus", fakeus))
    dp.add_handler(CommandHandler("mykeys", mykeys))
    dp.add_handler(CommandHandler("status", status))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()