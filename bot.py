import asyncio
import aiosqlite
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

logging.basicConfig(level=logging.INFO)

# ================= НАСТРОЙКА БОТА =================
API_TOKEN = '8724651736:AAGaV6oJmh12o1PQ-NQ4Dj4A4V-I_hcj07o'
ADMIN_ID = 6597940034
MY_TG_LINK = 'https://t.me/KsGpv'  # Твоя ссылка на профиль
DB_NAME = 'minecraft_business.db'
# ==================================================

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

RANKS_DICT = {
    "1": "🟢 [Стажёр]",
    "2": "🔵 [Мл. Курьер]",
    "3": "🟡 [Курьер]",
    "4": "🟠 [Ст. Курьер]",
    "5": "🟣 [Гл. Курьер]"
}

def determine_rank(orders_count: int, custom_rank: str = None) -> str:
    if custom_rank and custom_rank != "None":
        return custom_rank
    if orders_count >= 50: return "🟣 [Гл. Курьер]"
    if orders_count >= 30: return "🟠 [Ст. Курьер]"
    if orders_count >= 15: return "🟡 [Курьер]"
    if orders_count >= 5:  return "🔵 [Мл. Курьер]"
    return "🟢 [Стажёр]"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            warehouse TEXT DEFAULT 'Не назначен',
            partner TEXT DEFAULT 'Нет напарника',
            balance REAL DEFAULT 0.0,
            completed_orders INTEGER DEFAULT 0,
            warns INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Работает',
            custom_rank TEXT DEFAULT 'None'
        )''')
        await db.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_text TEXT,
            price REAL DEFAULT 0.0,
            status TEXT DEFAULT 'Свободен',
            taken_by_id INTEGER DEFAULT NULL,
            taken_by_name TEXT DEFAULT NULL
        )''')
        await db.execute('''
        CREATE TABLE IF NOT EXISTS order_messages (
            order_id INTEGER,
            user_id INTEGER,
            message_id INTEGER,
            PRIMARY KEY (order_id, user_id)
        )''')
        await db.commit()

# Функция, которая будет каждые 15 минут отправлять тебе сообщение, чтобы бот на Render не засыпал
async def send_ping_message():
    await asyncio.sleep(10) # небольшая пауза при запуске
    while True:
        try:
            await bot.send_message(chat_id=ADMIN_ID, text="🤖 Бот работает стабильно! Проверка каждые 15 минут.")
        except Exception as e:
            logging.error(f"Ошибка пинга: {e}")
        await asyncio.sleep(900) # 900 секунд = 15 минут

def get_order_keyboard(order_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Забрать заказ 📦", callback_data=f"take_{order_id}")
    ]])

def get_courier_keyboard(order_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Написать Боссу 💬", url=MY_TG_LINK)],
        [InlineKeyboardButton(text="📦 Я доставил (В бочке)", callback_data=f"done_{order_id}")],
        [InlineKeyboardButton(text="❌ Отказаться", callback_data=f"cancel_{order_id}")]
    ])

def get_admin_keyboard(order_id: int, courier_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить и выплатить", callback_data=f"adm_confirm_{order_id}_{courier_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm_reject_{order_id}_{courier_id}")]
    ])

def get_admin_cancel_keyboard(order_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Отменить этот заказ", callback_data=f"boss_force_cancel_{order_id}")
    ]])

def get_fire_keyboard(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Уволить курьера", callback_data=f"fire_{user_id}")
    ]])

WELCOME_TEXT = (
    "🌿 *Привет! Добро пожаловать в курьерскую службу!* 📦\n\n"
    "Твоя задача — доставлять ресурсы по тайным бочкам на сервере, зарабатывать койны биржи и получать привилегии!\n\n"
    "*Как это работает:*\n"
    "1️⃣ Успей нажать кнопку *«Забрать заказ»*.\n"
    "2️⃣ Доставь товар и нажми кнопку *«Я доставил заказ»*.\n"
    "3️⃣ Босс проверит бочку, тебе зачислятся койны (1 койн = 1 рубль на бирже) и +1 выполненный заказ!\n"
    "4️⃣ Вывод заработанных средств доступен от *15 койнов* через Босса!\n\n"
    "Пропиши /profile, чтобы узнать свой ранг и баланс."
)

@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or f"id_{user_id}"
    is_new = False
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT status FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
            if user and user[0] == 'Уволен':
                await message.answer("❌ Ты уволен из курьерской службы!")
                return
            if not user:
                await db.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
                await db.commit()
                is_new = True
                
    await message.answer(WELCOME_TEXT, parse_mode="Markdown")
    
    if is_new:
        try:
            await bot.send_message(
                chat_id=ADMIN_ID, 
                text=f"🔔 **Новый пользователь в боте!**\n👤 Ник: @{username}\n🆔 ID: `{user_id}`",
                parse_mode="Markdown"
            )
        except: pass

@dp.message(Command("profile"))
async def cmd_profile(message: Message):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT warehouse, partner, balance, completed_orders, warns, status, custom_rank FROM users WHERE user_id = ?", (message.from_user.id,)) as cursor:
            data = await cursor.fetchone()
            if data:
                wh, partner, balance, completed_orders, warns, status, custom_rank = data
                emoji = "🌴" if status == "В отпуске" else "🏃‍♂️"
                if status == "Уволен": emoji = "❌"
                rank = determine_rank(completed_orders, custom_rank)
                
                withdraw_status = "✅ Доступен Боссу!" if balance >= 15.0 else f"❌ Недоступен (нужно еще {round(15.0 - balance, 2)} 🪙)"
                
                await message.answer(f"📋 *Твой профиль курьера:*\n\n"
                                     f"🎖️ Твой ранг: *{rank}*\n"
                                     f"👤 Статус: {emoji} {status}\n"
                                     f"📦 Склад: {wh}\n"
                                     f"🤝 Напарник: @{partner}\n"
                                     f"💰 *Баланс кошелька:* {round(balance, 2)} 🪙 (койнов)\n"
                                     f"💵 Вывод средств: {withdraw_status}\n"
                                     f"📊 Выполнено заказов: *{completed_orders} шт.*\n"
                                     f"🛑 Варны: {warns}/3\n\n"
                                     f"ℹ️ _Койны можно вывести на сервере через @KsGpv!_", parse_mode="Markdown")
            else:
                await message.answer("❌ Сначала пропиши /start")

@dp.message(Command("top"))
async def cmd_top(message: Message):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT username, completed_orders, balance, custom_rank FROM users WHERE status != 'Уволен' ORDER BY completed_orders DESC LIMIT 10") as cursor:
            rows = await cursor.fetchall()
            
    if not rows:
        await message.answer("📊 Топ пока пуст.")
        return
        
    text = "🏆 *ТОП-10 ЛУЧШИХ КУРЬЕРОВ СЛУЖБЫ:* 🏆\n\n"
    for i, row in enumerate(rows, 1):
        rank_title = determine_rank(row[1], row[3])
        text += f"{i}. @{row[0]} — *{row[1]} зак.* | {rank_title} | ({round(row[2], 2)} 🪙)\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("order"))
async def cmd_send_order(message: Message):
    if message.from_user.id != ADMIN_ID: return
    raw_text = message.text.replace("/order", "").strip()
    if not raw_text or "|" not in raw_text:
        await message.answer("❌ Пиши строго через черточку `|` чтобы указать цену в койнах!\nПример: `/order 16 грибов | 0.25`")
        return
        
    order_text, price_str = raw_text.split("|", 1)
    order_text = order_text.strip()
    try:
        price = float(price_str.strip().replace("🪙", "").replace(",", "."))
    except ValueError:
        await message.answer("❌ Ошибка в цене! Укажи цену числом (можно дробным). Пример: 0.25 или 1.5")
        return
        
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("INSERT INTO orders (order_text, price) VALUES (?, ?)", (order_text, price))
        order_id = cursor.lastrowid
        await db.commit()
        
        async with db.execute("SELECT user_id FROM users WHERE status = 'Работает'") as u_cursor:
            users = await u_cursor.fetchall()
            
        for u in users:
            uid = u[0]
            try:
                msg = await bot.send_message(
                    chat_id=uid, 
                    text=f"🔔 *НОВЫЙ ЗАКАЗ №{order_id}:*\n📦 Что доставить: *{order_text}*\n💰 Награда: *{price} 🪙 (койнов)*", 
                    reply_markup=get_order_keyboard(order_id), 
                    parse_mode="Markdown"
                )
                await db.execute("INSERT INTO order_messages (order_id, user_id, message_id) VALUES (?, ?, ?)", (order_id, uid, msg.message_id))
            except: pass
        await db.commit()
    await message.answer(f"🚀 Заказ №{order_id} отправлен! Цена: {price} 🪙")

@dp.callback_query(F.data.startswith("take_"))
async def process_take_order(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    username = callback.from_user.username or f"id_{user_id}"
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT order_id FROM orders WHERE taken_by_id = ? AND status = 'В работе'", (user_id,)) as active_cursor:
            has_active = await active_cursor.fetchone()
            if has_active:
                await callback.answer("❌ Ты не можешь брать несколько заказов одновременно! Сначала сдай или отмени текущий.", show_alert=True)
                return

        async with db.execute("SELECT status, order_text, price, taken_by_name FROM orders WHERE order_id = ?", (order_id,)) as cursor:
            res = await cursor.fetchone()
            if not res: return
            status, order_text, price, taken_by_name = res
            
        if status != "Свободен":
            await callback.answer("❌ Вы не успели!", show_alert=True)
            await callback.message.edit_text(f"❌ Заказ №{order_id} уже забрал @{taken_by_name}")
            return
            
        await db.execute("UPDATE orders SET status = 'В работе', taken_by_id = ?, taken_by_name = ? WHERE order_id = ?", (user_id, username, order_id))
        await db.commit()
        await callback.answer("✅ Ты успешно забрал заказ!", show_alert=True)
        
        try:
            await bot.send_message(
                chat_id=ADMIN_ID, 
                text=f"📦 Курьер @{username} забрал заказ №{order_id} («{order_text}») за {price} 🪙",
                reply_markup=get_admin_cancel_keyboard(order_id)
            )
        except: pass

        async with db.execute("SELECT user_id, message_id FROM order_messages WHERE order_id = ?", (order_id,)) as m_cursor:
            messages = await m_cursor.fetchall()
        for uid, msg_id in messages:
            if uid != user_id:
                try: await bot.edit_message_text(chat_id=uid, message_id=msg_id, text=f"❌ Заказ №{order_id} забрал курьер @{username}")
                except: pass
                
        await callback.message.edit_text(
            text=f"🎉 *Ты забрал заказ №{order_id}:*\n«{order_text}»\n💰 Цена: *{price} 🪙 (койнов)*\n\nКак оставишь ресурсы в бочке — жми кнопку 👇",
            reply_markup=get_courier_keyboard(order_id), parse_mode="Markdown"
        )

@dp.callback_query(F.data.startswith("boss_force_cancel_"))
async def process_boss_force_cancel(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    order_id = int(callback.data.split("_")[3])
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT taken_by_id, order_text, price FROM orders WHERE order_id = ?", (order_id,)) as cursor:
            res = await cursor.fetchone()
            if not res: return
            courier_id, order_text, price = res
            
        await db.execute("UPDATE orders SET status = 'Свободен', taken_by_id = NULL, taken_by_name = NULL WHERE order_id = ?", (order_id,))
        await db.commit()
        
    await callback.message.edit_text(f"⚠️ Вы принудительно отменили заказ №{order_id} и вернули его в список!")
    
    if courier_id:
        try: await bot.send_message(chat_id=courier_id, text=f"⚠️ Босс отменил твой заказ №{order_id} («{order_text}»), так как он долго не выполнялся. Заказ возвращен в общую ленту.")
        except: pass

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id, message_id FROM order_messages WHERE order_id = ?", (order_id,)) as m_cursor:
            messages = await m_cursor.fetchall()
        for uid, msg_id in messages:
            try: await bot.edit_message_text(chat_id=uid, message_id=msg_id, text=f"🔄 *ЗАКАЗ №{order_id} СНОВА ДОСТУПЕН:*\n📦 {order_text}\n💰 Награда: {price} 🪙", reply_markup=get_order_keyboard(order_id), parse_mode="Markdown")
            except: pass

@dp.callback_query(F.data.startswith("cancel_"))
async def process_courier_cancel(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    username = callback.from_user.username or f"id_{user_id}"
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT taken_by_id, order_text, price FROM orders WHERE order_id = ?", (order_id,)) as cursor:
            res = await cursor.fetchone()
            if not res or res[0] != user_id: return
            order_text, price = res[1], res[2]

        await db.execute("UPDATE orders SET status = 'Свободен', taken_by_id = NULL, taken_by_name = NULL WHERE order_id = ?", (order_id,))
        await db.commit()
        await callback.answer("❌ Ты отказался от заказа.", show_alert=True)
        await callback.message.edit_text(f"❌ Ты отказался от заказа №{order_id}.")
        
        try: await bot.send_message(chat_id=ADMIN_ID, text=f"⚠️ Курьер @{username} отказался от заказа №{order_id} ({order_text}).")
        except: pass
            
        async with db.execute("SELECT user_id, message_id FROM order_messages WHERE order_id = ?", (order_id,)) as m_cursor:
            messages = await m_cursor.fetchall()
        for uid, msg_id in messages:
            try: await bot.edit_message_text(chat_id=uid, message_id=msg_id, text=f"🔄 *ЗАКАЗ №{order_id} СНОВА ДОСТУПЕН:*\n📦 {order_text}\n💰 Награда: {price} 🪙", reply_markup=get_order_keyboard(order_id), parse_mode="Markdown")
            except: pass

@dp.callback_query(F.data.startswith("done_"))
async def process_courier_done(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    username = callback.from_user.username or f"id_{user_id}"
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT order_text, price FROM orders WHERE order_id = ?", (order_id,)) as cursor:
            res = await cursor.fetchone()
            if not res: return
            order_text, price = res
            
    await callback.message.edit_text(f"⏳ Запрос по заказу №{order_id} отправлен боссу. Ожидай проверки!")
    await bot.send_message(
        chat_id=ADMIN_ID,
        text=f"🕵️‍♂️ Курьер @{username} доставил заказ №{order_id} («{order_text}»).\n💰 Сумма к выплате: *{price} 🪙*\n\nПроверь бочку в игре:",
        reply_markup=get_admin_keyboard(order_id, user_id),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("adm_"))
async def process_admin_decision(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    data = callback.data.split("_")
    action, order_id, courier_id = data[1], int(data[2]), int(data[3])
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT price FROM orders WHERE order_id = ?", (order_id,)) as cursor:
            price_res = await cursor.fetchone()
            price = price_res[0] if price_res else 0.0

        if action == "confirm":
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (price, courier_id))
            await db.execute("UPDATE users SET completed_orders = completed_orders + 1 WHERE user_id = ?", (courier_id,))
            await db.execute("UPDATE orders SET status = 'Выполнен' WHERE order_id = ?", (order_id,))
            await db.commit()
            
            async with db.execute("SELECT completed_orders, custom_rank FROM users WHERE user_id = ?", (courier_id,)) as o_curr:
                ord_c, c_rank = await o_curr.fetchone()
                
            final_rank = determine_rank(ord_c, c_rank)
            await callback.message.edit_text(f"✅ Вы подтвердили заказ №{order_id}. Начислено {price} 🪙!")
            try: await bot.send_message(chat_id=courier_id, text=f"💰 Босс подтвердил доставку!\nНа баланс зачислено: *{price} 🪙*\nВыполнено заказов: *{ord_c} шт.*\nРанг: *{final_rank}*\nПроверь /profile")
            except: pass
        else:
            await db.execute("UPDATE orders SET status = 'Отклонен' WHERE order_id = ?", (order_id,))
            await db.commit()
            await callback.message.edit_text(f"❌ Вы отклонили выполнение заказа №{order_id}.")
            try: await bot.send_message(chat_id=courier_id, text=f"❌ Босс отклонил выполнение заказа №{order_id}. Что-то не так с ресурсами в бочке.")
            except: pass

@dp.message(Command("pay"))
async def cmd_pay(message: Message):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split()
    if len(args) < 3:
        await message.answer("❌ Пиши правильно:\n`/pay @ник сумма` (можно с минусом для списания при выводе средств, например `-15.0`)")
        return
        
    target = args[1].replace("@", "").lower()
    try:
        amount = float(args[2].replace(",", "."))
    except ValueError:
        await message.answer("❌ Сумма должна быть числом!")
        return
        
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id, username, balance FROM users WHERE status != 'Уволен'") as cursor:
            rows = await cursor.fetchall()
            
        for row in rows:
            if row[1] and row[1].lower() == target:
                uid, name, current_bal = row
                if amount == 0:
                    new_bal = 0.0
                    msg_text = f"🧹 Баланс курьера @{name} полностью обнулён."
                    user_msg = "💸 Твой баланс кошелька был обнулён Боссом."
                else:
                    new_bal = current_bal + amount
                    msg_text = f"✅ Изменено для @{name}. Старый баланс: {round(current_bal, 2)} 🪙, Новый баланс: {round(new_bal, 2)} 🪙"
                    user_msg = f"💳 Босс изменил твой баланс кошелька на *{amount} 🪙*! Текущий баланс: *{round(new_bal, 2)} 🪙*"
                    
                await db.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_bal, uid))
                await db.commit()
                await message.answer(msg_text)
                try: await bot.send_message(chat_id=uid, text=user_msg, parse_mode="Markdown")
                except: pass
                return
        await message.answer(f"❌ Курьер {args[1]} не найден.")

@dp.message(Command("setrank"))
async def cmd_set_rank(message: Message):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("❌ Пиши правильно:\n`/setrank @ник номер_или_название`")
        return
        
    target = args[1].replace("@", "").lower().strip()
    rank_input = args[2].strip()
    
    if rank_input == "0":
        rank_val = "None"
        rank_display = "Авто-расчет по заказам"
    elif rank_input in RANKS_DICT:
        rank_val = RANKS_DICT[rank_input]
        rank_display = rank_val
    else:
        rank_val = rank_input
        rank_display = rank_val
        
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id, username FROM users WHERE status != 'Уволен'") as cursor:
            rows = await cursor.fetchall()
            
        for row in rows:
            if row[1] and row[1].lower().strip() == target:
                uid, name = row
                await db.execute("UPDATE users SET custom_rank = ? WHERE user_id = ?", (rank_val, uid))
                await db.commit()
                await message.answer(f"🎖️ Для курьера @{name} установлен ранг: *{rank_display}*", parse_mode="Markdown")
                try:
                    user_msg = f"🎖️ Босс изменил твой ранг на: *{rank_display}*" if rank_input != "0" else "🔄 Авто-расчет ранга возвращен!"
                    await bot.send_message(chat_id=uid, text=user_msg, parse_mode="Markdown")
                except: pass
                return
        await message.answer(f"❌ Курьер {args[1]} не найден.")

@dp.message(Command("couriers"))
async def cmd_couriers(message: Message):
    if message.from_user.id != ADMIN_ID: return
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id, username, balance, completed_orders, status, custom_rank FROM users WHERE status != 'Уволен'") as cursor:
            rows = await cursor.fetchall()
            if not rows:
                await message.answer("👥 Рабочих курьеров пока нет.")
                return
            
            await message.answer("👥 *Список курьеров в сети:*")
            for row in rows:
                uid, name, bal, ord_c, status, c_rank = row
                rank_title = determine_rank(ord_c, c_rank)
                text = f"• @{name} | Ранг: {rank_title} ({ord_c} зак.) | Кошелек: *{round(bal, 2)} 🪙* | {status}"
                await message.answer(text, reply_markup=get_fire_keyboard(uid), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("fire_"))
async def process_fire_courier(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    target_id = int(callback.data.split("_")[1])
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET status = 'Уволен' WHERE user_id = ?", (target_id,))
        await db.commit()
    await callback.message.edit_text("❌ Курьер успешно уволен!")

@dp.message(Command("warn"))
async def cmd_warn(message: Message):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split()
    if len(args) < 2: return
    target = args[1].replace("@", "").lower()
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id, warns, username FROM users") as cursor:
            rows = await cursor.fetchall()
        for row in rows:
            if row[2] and row[2].lower() == target:
                new_warns = row[1] + 1
                await db.execute("UPDATE users SET warns = ? WHERE user_id = ?", (new_warns, row[0]))
                await db.commit()
                await message.answer(f"🛑 Вы выдали варн @{row[2]}. Варны: {new_warns}/3")
                try: await bot.send_message(chat_id=row[0], text=f"⚠️ Босс выдал тебе варн! ({new_warns}/3)")
                except: pass
                break

@dp.message(Command("unwarn"))
async def cmd_unwarn(message: Message):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split()
    if len(args) < 2: return
    target = args[1].replace("@", "").lower()
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id, warns, username FROM users WHERE status != 'Уволен'") as cursor:
            rows = await cursor.fetchall()
        for row in rows:
            if row[2] and row[2].lower() == target:
                new_warns = max(0, row[1] - 1)
                await db.execute("UPDATE users SET warns = ? WHERE user_id = ?", (new_warns, row[0]))
                await db.commit()
                await message.answer(f"✅ Снят варн с @{row[2]}. Варны: {new_warns}/3")
                break

@dp.message(Command("rest"))
async def cmd_rest(message: Message):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split()
    if len(args) < 2: return
    target = args[1].replace("@", "").lower()
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id, status, username FROM users WHERE status != 'Уволен'") as cursor:
            rows = await cursor.fetchall()
        for row in rows:
            if row[2] and row[2].lower() == target:
                uid, current_status, name = row
                new_status = "В отпуске" if current_status == "Работает" else "Работает"
                await db.execute("UPDATE users SET status = ? WHERE user_id = ?", (new_status, uid))
                await db.commit()
                await message.answer(f"🌴 Статус курьера @{name} изменен на: {new_status}")
                break

@dp.message(Command("setwh"))
async def cmd_set_warehouse(message: Message):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split()
    if len(args) < 4: return
    target, wh_name, partner_name = args[1].replace("@", "").lower(), args[2], args[3].replace("@", "")
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id, username FROM users") as cursor:
            rows = await cursor.fetchall()
        for row in rows:
            if row[1] and row[1].lower() == target:
                await db.execute("UPDATE users SET warehouse = ?, partner = ? WHERE user_id = ?", (wh_name, partner_name, row[0]))
                await db.commit()
                await message.answer(f"✅ Для @{row[1]} настроен склад {wh_name}")
                break

async def main():
    await init_db()
    # Запуск таймера пинга
    asyncio.create_task(send_ping_message())
    
    from aiogram.client.telegram import TelegramAPIServer
    from aiogram.client.session.aiohttp import AiohttpSession
    custom_server = TelegramAPIServer.from_base("https://api.telegram-proxy.org")
    session = AiohttpSession()
    global bot
    bot = Bot(token=API_TOKEN, session=session, api_server=custom_server)
    print("Бот успешно обновлен!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
