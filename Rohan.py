import logging
import os
import requests
import time
import string
import random
import yaml
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, executor, types
from aiogram.utils.exceptions import Throttled
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# Configure vars get from env or config.yml
CONFIG = yaml.load(open('config.yml', 'r'), Loader=yaml.SafeLoader)
TOKEN = os.getenv('TOKEN', CONFIG['token'])
BLACKLISTED = os.getenv('BLACKLISTED', CONFIG['blacklisted']).split()
PREFIX = os.getenv('PREFIX', CONFIG['prefix'])
OWNER = int(os.getenv('OWNER', CONFIG['owner']))
ANTISPAM = int(os.getenv('ANTISPAM', CONFIG['antispam']))
BINCODES_API_KEY = "d7fd1f14c7570cf1803497a7cd8521af"
BINCODES_API_ENDPOINT = "https://api.bincodes.com/cc/"

# Initialize bot and dispatcher
storage = MemoryStorage()
bot = Bot(token=TOKEN, parse_mode=types.ParseMode.HTML)
dp = Dispatcher(bot, storage=storage)

# Configure logging
logging.basicConfig(level=logging.INFO, filename="bot.log")

# BOT INFO
loop = asyncio.get_event_loop()
bot_info = loop.run_until_complete(bot.get_me())
BOT_USERNAME = bot_info.username
BOT_NAME = bot_info.first_name
BOT_ID = bot_info.id

# Random DATA
letters = string.ascii_lowercase
First = ''.join(random.choice(letters) for _ in range(6))
Last = ''.join(random.choice(letters) for _ in range(6))
Name = f'{First}+{Last}'
Email = f'{First}.{Last}@gmail.com'
UA = 'Mozilla/5.0 (X11; Linux i686; rv:102.0) Gecko/20100101 Firefox/102.0'

async def is_owner(user_id):
    return user_id == OWNER

async def is_card_valid(card_number: str) -> bool:
    return (sum(map(lambda n: n[1] + (n[0] % 2 == 0) * (n[1] - 9 * (n[1] > 4)), enumerate(map(int, card_number[:-1])))) + int(card_number[-1])) % 10 == 0

@dp.message_handler(commands=['start', 'help'], commands_prefix=PREFIX)
async def helpstr(message: types.Message):
    keyboard_markup = types.InlineKeyboardMarkup(row_width=3)
    btns = types.InlineKeyboardButton("Bot Channel", url="https://t.me/Rohan_Stock69")
    keyboard_markup.row(btns)
    FIRST = message.from_user.first_name
    MSG = f'''
Hello {FIRST}, Im {BOT_NAME}
U can find my Boss  <a href="tg://user?id={OWNER}">HERE</a>
Cmds /chk /info /bin /gen /fakeus'''
    await message.answer(MSG, reply_markup=keyboard_markup, disable_web_page_preview=True)

@dp.message_handler(commands=['info', 'id'], commands_prefix=PREFIX)
async def info(message: types.Message):
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        is_bot = message.reply_to_message.from_user.is_bot
        username = message.reply_to_message.from_user.username
        first = message.reply_to_message.from_user.first_name
    else:
        user_id = message.from_user.id
        is_bot = message.from_user.is_bot
        username = message.from_user.username
        first = message.from_user.first_name
    await message.reply(f'''
═════════╕
<b>USER INFO</b>
<b>USER ID:</b> <code>{user_id}</code>
<b>USERNAME:</b> @{username}
<b>FIRSTNAME:</b> {first}
<b>BOT:</b> {is_bot}
<b>BOT-OWNER:</b> {await is_owner(user_id)}
╘═════════''')

@dp.message_handler(commands=['bin'], commands_prefix=PREFIX)
async def binio(message: types.Message):
    await message.answer_chat_action('typing')
    ID = message.from_user.id
    FIRST = message.from_user.first_name
    BIN = message.text[len('/bin '):]
    if len(BIN) < 6:
        return await message.reply('Send bin not ass')
    try:
        response = requests.get(
            f"{BINCODES_API_ENDPOINT}?format=json&api_key={BINCODES_API_KEY}&cc={BIN[:8]}",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("valid"):
                INFO = f'''
<b>BIN:</b> <code>{BIN[:6]}</code>
<b>Card:</b> {data.get('card', 'UNKNOWN')}
<b>Type:</b> {data.get('type', 'UNKNOWN')}
<b>Level:</b> {data.get('level', 'UNKNOWN')}
<b>Bank:</b> {data.get('bank', 'UNKNOWN')}
<b>Country:</b> {data.get('country', 'UNKNOWN')} ({data.get('countrycode', '')})
SENDER: <a href="tg://user?id={ID}">{FIRST}</a>
BOT⇢ @{BOT_USERNAME}
OWNER⇢ <a href="tg://user?id={OWNER}">LINK</a>
'''
            else:
                INFO = f'''
<b>BIN:</b> <code>{BIN[:6]}</code>
<b>Response:</b> Invalid BIN
SENDER: <a href="tg://user?id={ID}">{FIRST}</a>
BOT⇢ @{BOT_USERNAME}
OWNER⇢ <a href="tg://user?id={OWNER}">LINK</a>
'''
            await message.reply(INFO)
        else:
            await message.reply(f'<b>Error:</b> API returned status {response.status_code}')
    except Exception as e:
        await message.reply(f'<b>Error:</b> Failed to fetch BIN info - {str(e)}')

@dp.message_handler(commands=['chk'], commands_prefix=PREFIX)
async def chk(message: types.Message):
    await message.answer_chat_action('typing')
    tic = time.perf_counter()
    ID = message.from_user.id
    FIRST = message.from_user.first_name
    try:
        await dp.throttle('chk', rate=ANTISPAM)
    except Throttled:
        await message.reply(f'<b>Too many requests!</b>\nBlocked For {ANTISPAM} seconds')
        return
    if message.reply_to_message:
        cc = message.reply_to_message.text
    else:
        cc = message.text[len('/chk '):]
    if len(cc) == 0:
        return await message.reply("<b>Type your cc</b>")
    try:
        parts = cc.split('|')
        if len(parts) != 4:
            return await message.reply('<b>Failed to parse Card</b>\n<b>Reason: Invalid Format!</b>\n<b>Example:</b> <code>4242424242424242|12|2026|123</code>')
        ccn, mm, yy, cvv = [p.strip() for p in parts]
        if not (ccn.isdigit() and 15 <= len(ccn) <= 16):
            return await message.reply('<b>Failed to parse Card</b>\n<b>Reason: Invalid Card Number!</b>')
        if not (mm.isdigit() and 1 <= int(mm) <= 12):
            return await message.reply('<b>Failed to parse Card</b>\n<b>Reason: Invalid Month!</b>')
        if not (yy.isdigit() and 2025 <= int(yy) <= 2035):
            return await message.reply('<b>Failed to parse Card</b>\n<b>Reason: Invalid Year!</b>')
        if not (cvv.isdigit() and len(cvv) in [3, 4]):
            return await message.reply('<b>Failed to parse Card</b>\n<b>Reason: Invalid CVV!</b>')
        BIN = ccn[:6]
        if BIN in BLACKLISTED:
            return await message.reply('<b>BLACKLISTED BIN</b>')
        if not await is_card_valid(ccn):
            return await message.reply('<b>Invalid luhn algorithm</b>')
        # Demo mode
        input_ccn = ccn
        if ccn != "4242424242424242":
            await message.reply(f'''
<b>⚠️ Demo Mode ⚠️</b>
<b>💳 Card:</b> <code>{ccn}</code>
<b>🔐 Using test card for API call.</b>
''')
            ccn = "4242424242424242"
            mm = "12"
            yy = "2026"
            cvv = "123"
        # Stripe API
        STRIPE_KEY = "pk_live_Ng5VkKcI3Ur3KZ92goEDVRBq"  # REPLACE WITH YOUR TEST KEY (pk_test_...)
        headers = {
            "user-agent": UA,
            "accept": "application/json",
            "content-type": "application/x-www-form-urlencoded"
        }
        try:
            # Get muid, guid, sid
            m = requests.post('https://m.stripe.com/6', headers=headers, timeout=10)
            r = m.json()
            Guid = r['guid']
            Muid = r['muid']
            Sid = r['sid']
            postdata = {
                "guid": Guid,
                "muid": Muid,
                "sid": Sid,
                "key": pk_live_Ng5VkKcI3Ur3KZ92goEDVRBq,
                "card[name]": Name,
                "card[number]": ccn,
                "card[exp_month]": mm,
                "card[exp_year]": yy[-2:],
                "card[cvc]": cvv
            }
            pr = requests.post('https://api.stripe.com/v1/tokens', data=postdata, headers=headers, timeout=10)
            toc = time.perf_counter()
            logging.info(f"Stripe API response: status={pr.status_code}, text={pr.text}")
            if pr.status_code == 200:
                result = pr.json()
                if 'id' in result:
                    await message.reply(f'''
✅<b>Approved</b>✅
<b>CC:</b> <code>{ccn}|{mm}|{yy}|{cvv}</code>
<b>Gateway:</b> Stripe
<b>Response:</b> Token created
<b>Took:</b> <code>{toc - tic:0.2f}</code>(s)
<b>ChkBy:</b> <a href="tg://user?id={ID}">{FIRST}</a>
<b>Owner:</b> {await is_owner(ID)}
<b>Bot:</b> @{BOT_USERNAME}
''')
                else:
                    error = result.get('error', {}).get('message', 'Unknown error')
                    await message.reply(f'''
❌<b>Declined</b>❌
<b>CC:</b> <code>{ccn}|{mm}|{yy}|{cvv}</code>
<b>Gateway:</b> Stripe
<b>Response:</b> {error}
<b>Took:</b> <code>{toc - tic:0.2f}</code>(s)
<b>ChkBy:</b> <a href="tg://user?id={ID}">{FIRST}</a>
<b>Owner:</b> {await is_owner(ID)}
<b>Bot:</b> @{BOT_USERNAME}
''')
            else:
                await message.reply(f'''
❌<b>Error</b>❌
<b>CC:</b> <code>{ccn}|{mm}|{yy}|{cvv}</code>
<b>Gateway:</b> Stripe
<b>Response:</b> API returned status {pr.status_code}
<b>Took:</b> <code>{toc - tic:0.2f}</code>(s)
<b>ChkBy:</b> <a href="tg://user?id={ID}">{FIRST}</a>
<b>Owner:</b> {await is_owner(ID)}
<b>Bot:</b> @{BOT_USERNAME}
''')
        except requests.exceptions.Timeout:
            toc = time.perf_counter()
            await message.reply(f'''
❌<b>Error</b>❌
<b>CC:</b> <code>{ccn}|{mm}|{yy}|{cvv}</code>
<b>Gateway:</b> Stripe
<b>Response:</b> API request timed out
<b>Took:</b> <code>{toc - tic:0.2f}</code>(s)
<b>ChkBy:</b> <a href="tg://user?id={ID}">{FIRST}</a>
<b>Owner:</b> {await is_owner(ID)}
<b>Bot:</b> @{BOT_USERNAME}
''')
        except requests.exceptions.RequestException as e:
            toc = time.perf_counter()
            await message.reply(f'''
❌<b>Error</b>❌
<b>CC:</b> <code>{ccn}|{mm}|{yy}|{cvv}</code>
<b>Gateway:</b> Stripe
<b>Response:</b> Connection error - {str(e)}
<b>Took:</b> <code>{toc - tic:0.2f}</code>(s)
<b>ChkBy:</b> <a href="tg://user?id={ID}">{FIRST}</a>
<b>Owner:</b> {await is_owner(ID)}
<b>Bot:</b> @{BOT_USERNAME}
''')
    except Exception as e:
        toc = time.perf_counter()
        await message.reply(f'''
❌<b>Error</b>❌
<b>CC:</b> <code>{cc}</code>
<b>Gateway:</b> Stripe
<b>Response:</b> Failed to parse card - {str(e)}
<b>Took:</b> <code>{toc - tic:0.2f}</code>(s)
<b>ChkBy:</b> <a href="tg://user?id={ID}">{FIRST}</a>
<b>Owner:</b> {await is_owner(ID)}
<b>Bot:</b> @{BOT_USERNAME}
''')

@dp.message_handler(commands=['gen'], commands_prefix=PREFIX)
async def gen_key(message: types.Message):
    await message.answer_chat_action('typing')
    ID = message.from_user.id
    FIRST = message.from_user.first_name
    if not await is_owner(ID):
        return await message.reply('<b>Error:</b> Only the owner can generate keys!')
    args = message.text[len('/gen '):].strip().lower()
    durations = {
        '1day': 1,
        '3day': 3,
        '5day': 5,
        '7day': 7,
        '30day': 30
    }
    if args not in durations:
        return await message.reply(
            '<b>Usage:</b> /gen [1day|3day|5day|7day|30day]\n'
            '<b>Example:</b> <code>/gen 1day</code>'
        )
    duration = durations[args]
    key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    expiry = (datetime.now() + timedelta(days=duration)).strftime('%Y-%m-%d %H:%M:%S')
    await message.reply(f'''
<b>Generated Key</b>
<b>Key:</b> <code>{key}</code>
<b>Duration:</b> {args} ({duration} days)
<b>Expires:</b> {expiry}
<b>Generated by:</b> <a href="tg://user?id={ID}">{FIRST}</a>
<b>Bot:</b> @{BOT_USERNAME}
''')

@dp.message_handler(commands=['fakeus'], commands_prefix=PREFIX)
async def fakeus(message: types.Message):
    await message.answer_chat_action('typing')
    ID = message.from_user.id
    FIRST = message.from_user.first_name
    first_name = ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase, k=6)).capitalize()
    last_name = ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase, k=6)).capitalize()
    street = f"{random.randint(100, 9999)} Main St"
    city = random.choice(['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix'])
    state = random.choice(['NY', 'CA', 'IL', 'TX', 'AZ'])
    zip_code = f"{random.randint(10000, 99999)}"
    phone = f"{random.randint(200, 999)}-{random.randint(100, 999)}-{random.randint(1000, 9999)}"
    email = f"{first_name.lower()}.{last_name.lower()}@fakeus.com"
    await message.reply(f'''
<b>Fake US User</b>
<b>Name:</b> {first_name} {last_name}
<b>Address:</b> {street}, {city}, {state} {zip_code}
<b>Phone:</b> {phone}
<b>Email:</b> {email}
<b>Generated by:</b> <a href="tg://user?id={ID}">{FIRST}</a>
<b>Bot:</b> @{BOT_USERNAME}
''')

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, loop=loop)