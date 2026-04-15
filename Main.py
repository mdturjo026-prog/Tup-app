import sqlite3
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

TOKEN = "8607390888:AAHdvuCwsDjrjaW7tli_qFWnrm1Aq2Pkf_8"
ADMIN_ID = 7827023967 # তোমার ID
GROUP_ID = -5102848972 # তোমার গ্রুপের ID - @username_to_id_bot থেকে নাও

conn = sqlite3.connect('exchange.db', check_same_thread=False)
cur = conn.cursor()
cur.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, total_buy_usd REAL DEFAULT 0, total_sell_usd REAL DEFAULT 0)')
cur.execute('CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, type TEXT, product TEXT, usd REAL, taka REAL, trxid TEXT, number TEXT, status TEXT DEFAULT "pending")')
cur.execute('CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, name TEXT, price_usd REAL, price_taka REAL, icon TEXT, active INTEGER DEFAULT 1)')
cur.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')

defaults = {
    'buy_rate': '120', 'sell_rate': '110',
    'min_buy': '1', 'max_buy': '100',
    'min_sell': '1', 'max_sell': '100',
    'bkash_number': '01XXXXXXXXX',
    'paypal_email': 'your@email.com',
    'usdt_address': '0xYourBEP20Address'
}
for k, v in defaults.items():
    cur.execute("INSERT OR IGNORE INTO settings VALUES (?,?)", (k, v))

default_products = [
    ('TOPUP', 'WEEKLY OFFER', 1.23, 148, '📅'),
    ('TOPUP', 'MONTHLY OFFER', 6.16, 739, '📅'),
    ('FREE FIRE', 'IDCODE TOPUP', 0, 0, '🆔'),
    ('FREE FIRE', 'LEVEL UP PASS', 0, 0, '📈'),
    ('FREE FIRE', 'Weekly & Monthly', 0, 0, '🎁'),
    ('FREE FIRE', 'UniPin TOPUP', 0, 0, '💎')
]
for cat, name, usd, taka, icon in default_products:
    cur.execute("INSERT OR IGNORE INTO products (category, name, price_usd, price_taka, icon) VALUES (?,?,?,?,?)", (cat, name, usd, taka, icon))
conn.commit()

def get_setting(key):
    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    return cur.fetchone()[0]

def set_setting(key, value):
    cur.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, value))
    conn.commit()

def get_all_products():
    cur.execute("SELECT id, category, name, price_usd, price_taka, icon FROM products WHERE active=1 ORDER BY category, id")
    return cur.fetchall()

async def send_to_group(text):
    try:
        await app.bot.send_message(GROUP_ID, text, parse_mode='HTML')
    except: pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cur.execute("INSERT OR IGNORE INTO users VALUES (?, 0, 0)", (user_id,))
    conn.commit()
    s = dict(cur.execute("SELECT key, value FROM settings").fetchall())
    keyboard = [[InlineKeyboardButton("💵 Open Shop", web_app=WebAppInfo(url="https://তোমারনাম.github.io/topup-app/"))]]
    text = f"💵 USD Exchange & TopUp BD\n\n🟢 BUY: {s['buy_rate']}৳ = $1 | Limit: ${s['min_buy']}-${s['max_buy']}\n🔴 SELL: $1 = {s['sell_rate']}৳ | Limit: ${s['min_sell']}-${s['max_sell']}\n\nFast & Trusted 24/7"
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "NoUsername"
    full_name = update.effective_user.first_name
    data = json.loads(update.effective_message.web_app_data.data)
    action = data.get('action')

    if action == 'get_data':
        settings = dict(cur.execute("SELECT key, value FROM settings").fetchall())
        products = get_all_products()
        await context.bot.send_message(user_id, json.dumps({'settings': settings, 'products': products}))

    elif action == 'buy_product':
        pid = int(data.get('product_id'))
        cur.execute("SELECT name, price_usd, price_taka FROM products WHERE id=?", (pid,))
        name, usd, taka = cur.fetchone()
        trxid = data.get('trxid').strip()
        number = data.get('number', '')
        try:
            cur.execute("INSERT INTO orders (user_id, username, type, product, usd, taka, trxid, number) VALUES (?,?,?,?,?,?,?,?)",
                       (user_id, username, 'buy', name, usd, taka, trxid, number))
            order_id = cur.lastrowid
            conn.commit()

            # ইউজারকে মেসেজ
            await update.message.reply_text(f"✅ Order Placed!\n\nProduct: {name}\nPay: {taka}৳ bKash\nTrxID: {trxid}\nOrder ID: #{order_id}\nStatus: Pending")

            # অ্যাডমিনকে মেসেজ
            await context.bot.send_message(ADMIN_ID, f"🔔 NEW BUY\nUser: {user_id} @{username}\nProduct: {name}\nAmount: {taka}৳ = ${usd}\nTrxID: {trxid}\nGameID: {number}\nOrder ID: {order_id}\n/order_done {order_id}")

            # গ্রুপে মেসেজ
            await send_to_group(f"🆕 <b>New Buy Order #{order_id}</b>\n\n👤 Customer: {full_name} (@{username})\n🎁 Product: {name}\n💰 Amount: {taka}৳ = ${usd}\n📱 TrxID: <code>{trxid}</code>\n🆔 GameID: <code>{number}</code>\n\n⏳ Status: Pending Verification")

        except sqlite3.IntegrityError:
            await update.message.reply_text("❌ This TrxID is already used!")

    elif action == 'sell_usd':
        usd = float(data.get('usd_amount'))
        taka = usd * float(get_setting('sell_rate'))
        txid = data.get('txid').strip()
        number = data.get('number')
        cur.execute("INSERT INTO orders (user_id, username, type, product, usd, taka, trxid, number) VALUES (?,?,?,?,?,?,?)",
                   (user_id, username, 'sell', 'USD', usd, taka, txid, number))
        order_id = cur.lastrowid
        conn.commit()

        # ইউজারকে মেসেজ
        await update.message.reply_text(f"✅ Sell Order Placed!\n\nYou Send: ${usd} USD\nYou Get: {taka}৳ bKash\nTo: {number}\nTXID: {txid}\nOrder ID: #{order_id}")

        # অ্যাডমিনকে মেসেজ
        await context.bot.send_message(ADMIN_ID, f"🔔 NEW SELL\nUser: {user_id} @{username}\nReceive: ${usd}\nSend: {taka}৳ to {number}\nTXID: {txid}\nID: {order_id}\n/order_done {order_id}")

        # গ্রুপে মেসেজ
        await send_to_group(f"🆕 <b>New Sell Order #{order_id}</b>\n\n👤 Customer: {full_name} (@{username})\n💸 Sold: ${usd} USD\n💰 Get: {taka}৳ bKash\n📱 Number: <code>{number}</code>\n🔗 TXID: <code>{txid}</code>\n\n⏳ Status: Pending Payment")

    elif action == 'admin_panel' and user_id == ADMIN_ID:
        await admin_menu(update, context)

async def admin_menu(u, context):
    s = dict(cur.execute("SELECT key, value FROM settings").fetchall())
    cur.execute("SELECT COUNT(*), SUM(total_buy_usd), SUM(total_sell_usd) FROM users")
    users, total_buy, total_sell = cur.fetchone()
    cur.execute("SELECT COUNT(*) FROM orders WHERE status='pending'")
    pending = cur.fetchone()[0]
    profit = (total_buy or 0) * (float(s['buy_rate']) - float(s['sell_rate']))

    kb = [
        [InlineKeyboardButton("📦 Orders", callback_data='adm_orders'), InlineKeyboardButton("🎁 Products", callback_data='adm_products')],
        [InlineKeyboardButton("⚙️ Rates & Limits", callback_data='adm_rate'), InlineKeyboardButton("📱 Payment Info", callback_data='adm_number')]
    ]
    text = f"🔐 Admin Panel\n\n👥 Users: {users}\n📥 Total Buy: ${total_buy or 0:.2f}\n📤 Total Sell: ${total_sell or 0:.2f}\n💰 Profit: {profit:.2f}৳\n\n⚙️ Settings:\nBuy: {s['buy_rate']}৳ = $1 | Limit: ${s['min_buy']}-${s['max_buy']}\nSell: $1 = {s['sell_rate']}৳ | Limit: ${s['min_sell']}-${s['max_sell']}\n\n⏳ Pending Orders: {pending}"
    await context.bot.send_message(ADMIN_ID, text, reply_markup=InlineKeyboardMarkup(kb))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id!= ADMIN_ID: return
    await query.answer()
    d = query.data
    s = dict(cur.execute("SELECT key, value FROM settings").fetchall())

    if d == 'adm_products':
        cur.execute("SELECT id, category, name, price_taka, active FROM products")
        rows = cur.fetchall()
        text = "🎁 All Products:\n\n"
        for r in rows:
            status = "✅" if r[4] else "❌"
            text += f"{status} ID: `{r[0]}` | {r[1]}\n{r[2]} - {r[3]}৳\n/del_product {r[0]}\n\n"
        text += "\nAdd: `/add_product Category|Name|USD|TAKA|Icon`\nEx: `/add_product FREE FIRE|Diamond|5|600|💎`"
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=back_btn())

    elif d == 'adm_rate':
        context.user_data['adm_state'] = 'set_rate'
        await query.edit_message_text(f"Set Rates & Limits:\n`buy_rate|sell_rate|min_buy|max_buy|min_sell|max_sell`\n\nCurrent: {s['buy_rate']}|{s['sell_rate']}|{s['min_buy']}|{s['max_buy']}|{s['min_sell']}|{s['max_sell']}\nEx: `125|115|5|500|5|500`", parse_mode='Markdown', reply_markup=back_btn())

    elif d == 'adm_number':
        context.user_data['adm_state'] = 'set_number'
        await query.edit_message_text(f"Set Payment Details:\n`bkash|paypal|usdt_address`\n\nCurrent:\n{s['bkash_number']}\n{s['paypal_email']}\n{s['usdt_address']}", parse_mode='Markdown', reply_markup=back_btn())

    elif d == 'adm_orders':
        cur.execute("SELECT id, type, product, usd, taka, username, status FROM orders WHERE status='pending' LIMIT 10")
        rows = cur.fetchall()
        if not rows: return await query.edit_message_text("No pending orders.", reply_markup=back_btn())
        text = "⏳ Pending Orders:\n\n"
        for r in rows: text += f"ID: `{r[0]}` | {r[1].upper()} | @{r[5]}\n{r[2]} - ${r[3]} = {r[4]}৳\n/order_done {r[0]}\n\n"
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=back_btn())

    elif d == 'adm_main':
        await query.message.delete()
        await admin_menu(query, context)

def back_btn(): return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='adm_main')]])

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID: await admin_menu(update, context)

async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!= ADMIN_ID: return
    try:
        cat, name, usd, taka, icon = " ".join(context.args).split('|')
        cur.execute("INSERT INTO products (category, name, price_usd, price_taka, icon) VALUES (?,?,?,?,?)",
                   (cat.strip(), name.strip(), float(usd), float(taka), icon.strip()))
        conn.commit()
        await update.message.reply_text(f"✅ Product Added: {name}")
    except: await update.message.reply_text("Use: /add_product Category|Name|USD|TAKA|Icon")

async def del_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!= ADMIN_ID: return
    try:
        pid = int(context.args[0])
        cur.execute("UPDATE products SET active=0 WHERE id=?", (pid,))
        conn.commit()
        await update.message.reply_text(f"✅ Product ID {pid} Disabled")
    except: await update.message.reply_text("Use: /del_product product_id")

async def order_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!= ADMIN_ID: return
    try:
        oid = int(context.args[0])
        cur.execute("SELECT user_id, username, type, product, usd, taka FROM orders WHERE id=? AND status='pending'", (oid,))
        row = cur.fetchone()
        if not row: return await update.message.reply_text("Invalid ID or already processed.")
        user_id, username, otype, product, usd, taka = row

        cur.execute("UPDATE orders SET status='completed' WHERE id=?", (oid,))
        if otype == 'buy':
            cur.execute("UPDATE users SET total_buy_usd = total_buy_usd +? WHERE user_id=?", (usd, user_id))
        else:
            cur.execute("UPDATE users SET total_sell_usd = total_sell_usd +? WHERE user_id=?", (usd, user_id))
        conn.commit()

        # অ্যাডমিনকে কনফার্ম
        await update.message.reply_text(f"✅ Order {oid} Completed")

        # ইউজারকে মেসেজ
        await context.bot.send_message(user_id, f"✅ Order Completed!\n{product} delivered.\nThank you!")

        # গ্রুপে কনফার্ম মেসেজ
        if otype == 'buy':
            await send_to_group(f"✅ <b>Order #{oid} Completed</b>\n\n👤 Customer: @{username}\n🎁 Product: {product}\n💰 Amount: ${usd} = {taka}৳\n\n🚀 Delivered Successfully!")
        else:
            await send_to_group(f"✅ <b>Order #{oid} Completed</b>\n\n👤 Customer: @{username}\n💸 Sold: ${usd} USD\n💰 Paid: {taka}৳ bKash\n\n🚀 Payment Sent Successfully!")

    except: await update.message.reply_text("Use: /order_done order_id")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!= ADMIN_ID: return
    state = context.user_data.get('adm_state')
    if not state: return
    text = update.message.text

    try:
        if state == 'set_rate':
            buy, sell, min_b, max_b, min_s, max_s = text.split('|')
            for k, v in zip(['buy_rate','sell_rate','min_buy','max_buy','min_sell','max_sell'], [buy,sell,min_b,max_b,min_s,max_s]):
                set_setting(k, v.strip())
            await update.message.reply_text(f"✅ Rates & Limits Updated!")
        elif state == 'set_number':
            bkash, paypal, usdt = text.split('|')
            set_setting('bkash_number', bkash.strip())
            set_setting('paypal_email', paypal.strip())
            set_setting('usdt_address', usdt.strip())
            await update.message.reply_text("✅ Payment Details Updated!")
    except:
        await update.message.reply_text("❌ Wrong Format! Try again.")

    context.user_data['adm_state'] = None
    await admin_menu(update, context)

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("admin", admin_cmd))
app.add_handler(CommandHandler("add_product", add_product))
app.add_handler(CommandHandler("del_product", del_product))
app.add_handler(CommandHandler("order_done", order_done))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data))
print("Bot Running...")
app.run_polling()
