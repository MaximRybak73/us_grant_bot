import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# =====================================================================
# ⚙️ НАСТРОЙКИ БОТА (ТВОИ ДАННЫЕ УЖЕ ПРОПИСАНЫ)
# =====================================================================

# 1. Токен бота от @BotFather
BOT_TOKEN = "8945401067:AAHgN4KxT0RPX-LSddmUT86rAErwvkxG5G0"

# 2. Твой цифровой Telegram ID - сюда бот будет слать чеки!
ADMIN_ID = 1054746088

# 3. Твой юзернейм в Telegram (без @) и ссылки на канал
ADMIN_USERNAME = "MaxxximSergeevich"
PRIVATE_CHANNEL_LINK = "https://t.me/+твоя_приватная_ссылка_на_канал"
PUBLIC_CHANNEL_LINK = "https://t.me/your_us_channel"

# 4. Реквизиты для перевода по СБП / номеру телефона
PAYMENT_PHONE = "+79639117097"
PAYMENT_BANKS = "Сбербанк"
PAYMENT_RECIPIENT = "Максим Сергеевич Д."

# =====================================================================
# БАЗА ТАРИФОВ, ЛИЧНОЙ КОНСУЛЬТАЦИИ И ПРОМОКОДОВ
# =====================================================================

TARIFFS = {
    "tier1": {
        "name": "🔥 Подача заявки + Обратная связь",
        "price": 6490,
        "old_price": 10900,
        "desc": (
            "• Реальные победные письма SPARK и готовый шаблон резюме Harvard CV\n"
            "• Помощь с идеей заявки: выбираем сильную тему под твой опыт\n"
            "• Личная проверка и правка твоего мотивационного эссе и резюме в чате\n"
            "• Рекомендации по сценарию 2-минутной видеовизитки и тесту Duolingo\n"
            "• Разбор вопросов отборочного интервью и составление сильных ответов\n"
            "• Пошаговый гайд и ответы на вопросы по визовой анкете DS-160"
        )
    },
    "tier2": {
        "name": "💎 VIP: Полное сопровождение + США",
        "price": 12900,
        "old_price": 19900,
        "desc": (
            "• Всё из первого тарифа с приоритетным разбором без очереди\n"
            "• Возможность лично звонить мне в Telegram для разбора любых затыков и вопросов\n"
            "• Индивидуальная подготовка к финальному интервью и разговору с консулом США\n"
            "• Полная проверка визовой анкеты DS-160 и документов перед поездкой в Казахстан\n"
            "• Сопровождение по приезде в США: открытие банковской карты Chase, сим-карта, выбор дисциплин в вузе и бытовые вопросы на месте"
        )
    },
    "consult": {
        "name": "💬 Личная консультация (40 минут)",
        "price": 1490,
        "old_price": 2500,
        "desc": (
            "• Индивидуальный созвон со мной в Telegram (длительность — 40 минут)\n"
            "• Разбор твоего профиля, опыта и оценка реальных шансов на грант SPARK\n"
            "• Помощь с выбором сильной темы для мотивационного письма и структуры Harvard CV\n"
            "• Ответы на любые вопросы по отбору, тесту Duolingo, визе J-1 в Казахстане и жизни в США\n"
            "• 🗓 <b>Как выбираем время:</b> после оплаты просто напиши мне в личку, и мы с тобой текстом договоримся об удобном дне и времени для звонка!"
        )
    }
}

# Промокод с сайта (-15% ДО 7 НОЯБРЯ)
PROMOCODES = {
    "TAMPA27": 15
}

# Состояния пользователя
class OrderState(StatesGroup):
    waiting_for_promo = State()
    waiting_for_receipt = State()

# Память для хранения текущего выбора пользователя
user_cart = {}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# =====================================================================
# КЛАВИАТУРЫ
# =====================================================================

def get_main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 Тарифы и участие", callback_data="show_tariffs")],
        [InlineKeyboardButton(text="💬 Личная консультация (1 990 ₽)", callback_data="select_consult")],
        [
            InlineKeyboardButton(text="🎁 СКИДКА -15% ДО 7 НОЯБРЯ", callback_data="get_promo_info"),
            InlineKeyboardButton(text="🇺🇸 О подготовке", callback_data="about_project")
        ],
        [InlineKeyboardButton(text="✍️ Задать вопрос Максиму", url=f"https://t.me/{ADMIN_USERNAME}")]
    ])

def get_tariffs_kb(user_id: int) -> InlineKeyboardMarkup:
    discount = user_cart.get(user_id, {}).get("discount", 0)
    buttons = []
    for key, t in TARIFFS.items():
        final_price = int(t["price"] * (100 - discount) / 100)
        price_str = f"{final_price:,} ₽".replace(",", " ")
        if discount > 0:
            btn_text = f"{t['name']} - {price_str} (-{discount}%)"
        else:
            btn_text = f"{t['name']} - {price_str}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"select_{key}")])
    
    buttons.append([InlineKeyboardButton(text="🎟 Ввести промокод (TAMPA27)", callback_data="enter_promo")])
    buttons.append([InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_tariff_detail_kb(tier_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Перейти к оплате", callback_data=f"pay_{tier_key}")],
        [InlineKeyboardButton(text="🎟 Ввести промокод на скидку -15%", callback_data="enter_promo")],
        [InlineKeyboardButton(text="💬 Уточнить вопрос у Максима", url=f"https://t.me/{ADMIN_USERNAME}")],
        [InlineKeyboardButton(text="⬅️ Назад к выбору форматов", callback_data="show_tariffs")]
    ])

def get_payment_kb(tier_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатил(а) - отправить чек", callback_data=f"send_receipt_{tier_key}")],
        [InlineKeyboardButton(text="💬 Написать Максиму в личку", url=f"https://t.me/{ADMIN_USERNAME}")],
        [InlineKeyboardButton(text="⬅️ Назад к описанию", callback_data=f"select_{tier_key}")]
    ])

# =====================================================================
# ОБРАБОТЧИКИ КОМАНД И КНОПОК
# =====================================================================

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    if uid not in user_cart:
        user_cart[uid] = {"discount": 0, "promo_code": None, "tier": "tier1"}

    welcome_text = (
        f"Привет, <b>{message.from_user.first_name}</b>! 👋\n\n"
        "Добро пожаловать в <b>US.GRANT // SPARK Mentorship</b> - систему подготовки к грантовой программе SPARK в США ($20,000) от финалиста 2026 года Максима Дубцова.\n\n"
        "Я сам прошёл весь отбор с первого раза: от подачи заявки и получения визы J-1 в Казахстане до 3 месяцев учёбы во Флориде (University of Tampa) и саммита в Колорадо за счёт полного гранта.\n\n"
        "Здесь ты можешь:\n"
        "• Выбрать тариф полного менторства со мной в Telegram\n"
        "• Записаться на <b>разовую личную консультацию (1 990 ₽)</b>\n"
        "• Активировать промокод с сайта <code>TAMPA27</code> на <b>СКИДКУ -15% (ДЕЙСТВУЕТ ДО 7 НОЯБРЯ!)</b>\n\n"
        "👇 <i>Выбирай нужный пункт в меню ниже:</i>"
    )
    await message.answer(welcome_text, parse_mode="HTML", reply_markup=get_main_menu_kb())

@dp.callback_query(F.data == "back_main")
async def cb_back_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text = (
        "<b>Главное меню // US.GRANT Mentorship</b>\n\n"
        "Выбери интересующий раздел ниже:"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=get_main_menu_kb())

@dp.callback_query(F.data == "about_project")
async def cb_about_project(call: CallbackQuery):
    text = (
        "🇺🇸 <b>Как проходит наша работа по подготовке к SPARK?</b>\n\n"
        "1. <b>Никакой сухой теории:</b> на менторстве ты сразу получаешь мои реальные победные письма SPARK, шаблон Harvard CV и чёткие гайды.\n\n"
        "2. <b>Личная проверка в Telegram:</b> ты присылаешь свои черновики эссе, резюме и вопросы в личный чат со мной, а я проверяю их и помогаю докрутить формулировки до стандартов комиссии США.\n\n"
        "3. <b>Поддержка до США (на VIP):</b> возможность созваниваться со мной в Telegram по любым вопросам + помощь уже по прилёту в Америку (открытие карты Chase, сим-карта, выбор предметов в вузе).\n\n"
        "4. <b>Личная консультация (40 минут):</b> если пока не готов брать полное менторство, можешь записаться на разовый созвон со мной за 1 990 ₽ — разберём твой кейс и все вопросы!"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 Посмотреть тарифы и консультацию", callback_data="show_tariffs")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_main")]
    ])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "get_promo_info")
async def cb_get_promo_info(call: CallbackQuery):
    text = (
        "🔥 <b>СКИДКА -15% С САЙТА ДЕЙСТВУЕТ ТОЛЬКО ДО 7 НОЯБРЯ!</b>\n\n"
        "Используй промокод с сайта, чтобы зафиксировать сниженную цену:\n"
        "🎟 Промокод: <code>TAMPA27</code>\n\n"
        "<b>Как применить скидку:</b>\n"
        "1. Нажми кнопку <b>«🎟 Ввести промокод сейчас»</b> ниже.\n"
        "2. Отправь в чат код <code>TAMPA27</code>.\n"
        "3. Цены автоматически пересчитаются со скидкой <b>-15%</b>!\n\n"
        "⚡️ <i>Успей активировать промокод ДО 7 НОЯБРЯ!</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎟 Ввести промокод сейчас", callback_data="enter_promo")],
        [InlineKeyboardButton(text="🔥 Перейти к тарифам", callback_data="show_tariffs")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_main")]
    ])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "show_tariffs")
async def cb_show_tariffs(call: CallbackQuery, state: FSMContext):
    await state.clear()
    uid = call.from_user.id
    if uid not in user_cart:
        user_cart[uid] = {"discount": 0, "promo_code": None, "tier": "tier1"}

    discount = user_cart[uid].get("discount", 0)
    promo = user_cart[uid].get("promo_code")

    promo_status = (
        f"✅ <b>Активен промокод {promo} (скидка -{discount}%)</b>\n\n"
        if discount > 0 else
        "🔥 <i>ПРОМОКОД С САЙТА <code>TAMPA27</code> НА СКИДКУ -15% ДЕЙСТВУЕТ ДО 7 НОЯБРЯ! Нажми «Ввести промокод» ниже для пересчёта цен.</i>\n\n"
    )

    text = (
        "🔥 <b>Выбери свой формат подготовки к гранту SPARK ($20,000) или разовую консультацию:</b>\n\n"
        f"{promo_status}"
        "Нажми на нужный вариант ниже, чтобы посмотреть подробности и перейти к оплате:"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=get_tariffs_kb(uid))

@dp.callback_query(F.data.startswith("select_"))
async def cb_select_tariff(call: CallbackQuery):
    uid = call.from_user.id
    tier_key = call.data.split("_")[1]
    if uid not in user_cart:
        user_cart[uid] = {"discount": 0, "promo_code": None, "tier": tier_key}
    else:
        user_cart[uid]["tier"] = tier_key

    t = TARIFFS.get(tier_key, TARIFFS["tier1"])
    discount = user_cart[uid].get("discount", 0)
    final_price = int(t["price"] * (100 - discount) / 100)
    price_str = f"{final_price:,} ₽".replace(",", " ")
    old_str = f"{t['old_price']:,} ₽".replace(",", " ")

    discount_line = f" (с учётом твоей скидки -{discount}%!)" if discount > 0 else ""

    if tier_key == "consult":
        bottom_note = (
            "После оплаты и отправки чека в бот просто напиши мне в личные сообщения, "
            "и мы с тобой текстом выберем удобное время для 40-минутного звонка!"
        )
    else:
        bottom_note = (
            "После оплаты ты сразу получаешь доступ к материалам и личной работе со мной в Telegram."
        )

    text = (
        f"<b>{t['name']}</b>\n\n"
        f"<b>Что входит в этот формат:</b>\n{t['desc']}\n\n"
        f"〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️\n"
        f"Старая цена: <s>{old_str}</s>\n"
        f"💰 <b>К оплате сейчас: {price_str}</b>{discount_line}\n\n"
        f"{bottom_note}"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=get_tariff_detail_kb(tier_key))

# =====================================================================
# ВВОД ПРОМОКОДА
# =====================================================================

@dp.callback_query(F.data == "enter_promo")
async def cb_enter_promo(call: CallbackQuery, state: FSMContext):
    await state.set_state(OrderState.waiting_for_promo)
    text = (
        "🎟 <b>Введи промокод с сайта ответным сообщением в чат:</b>\n\n"
        "<i>Подсказка: промокод <code>TAMPA27</code> даёт скидку -15% ДО 7 НОЯБРЯ!</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Отмена", callback_data="show_tariffs")]
    ])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

@dp.message(OrderState.waiting_for_promo)
async def process_promo_code(message: Message, state: FSMContext):
    uid = message.from_user.id
    code = message.text.strip().upper()

    if uid not in user_cart:
        user_cart[uid] = {"discount": 0, "promo_code": None, "tier": "tier1"}

    if code in PROMOCODES:
        disc = PROMOCODES[code]
        user_cart[uid]["discount"] = disc
        user_cart[uid]["promo_code"] = code
        await state.clear()

        await message.answer(
            f"🎉 <b>Супер! Промокод {code} активирован!</b>\n"
            f"Твоя скидка <b>-{disc}% (действует ДО 7 НОЯБРЯ)</b> применена. Выбирай нужный формат ниже:",
            parse_mode="HTML",
            reply_markup=get_tariffs_kb(uid)
        )
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎟 Попробовать ещё раз", callback_data="enter_promo")],
            [InlineKeyboardButton(text="🔥 Перейти к тарифам", callback_data="show_tariffs")]
        ])
        await message.answer(
            "❌ <b>Такого промокода не найдено.</b>\n"
            "Проверь правильность написания: действующий промокод с сайта на скидку -15% (ДО 7 НОЯБРЯ) — <code>TAMPA27</code>",
            parse_mode="HTML",
            reply_markup=kb
        )

# =====================================================================
# ОПЛАТА ПО РЕКВИЗИТАМ И ОТПРАВКА ЧЕКА
# =====================================================================

@dp.callback_query(F.data.startswith("pay_"))
async def cb_pay_tariff(call: CallbackQuery):
    uid = call.from_user.id
    tier_key = call.data.split("_")[1]
    t = TARIFFS.get(tier_key, TARIFFS["tier1"])
    discount = user_cart.get(uid, {}).get("discount", 0)
    final_price = int(t["price"] * (100 - discount) / 100)
    price_str = f"{final_price:,} ₽".replace(",", " ")

    if tier_key == "consult":
        step3_text = (
            "3. Пришли скриншот или PDF квитанции сюда в чат, после чего напиши Максиму в личку, "
            "чтобы договориться о точном времени звонка!"
        )
    else:
        step3_text = "3. Пришли скриншот или PDF квитанции сюда в чат!"

    text = (
        f"💳 <b>Оформление: {t['name']}</b>\n"
        f"Сумма к оплате: <b>{price_str}</b>\n\n"
        "<b>Реквизиты для перевода по СБП (с любого банка):</b>\n"
        f"📱 Номер телефона: <code>{PAYMENT_PHONE}</code>\n"
        f"🏦 Банк: <b>{PAYMENT_BANKS}</b>\n"
        f"👤 Получатель: <b>{PAYMENT_RECIPIENT}</b>\n\n"
        "<b>Как подтвердить оплату за 1 минуту:</b>\n"
        f"1. Скопируй номер <code>{PAYMENT_PHONE}</code> и переведи <b>{price_str}</b> по СБП.\n"
        "2. Нажми кнопку <b>«✅ Я оплатил(а) - отправить чек»</b> ниже.\n"
        f"{step3_text}"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=get_payment_kb(tier_key))

@dp.callback_query(F.data.startswith("send_receipt_"))
async def cb_send_receipt(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    tier_key = call.data.split("_")[2]
    if uid not in user_cart:
        user_cart[uid] = {"discount": 0, "promo_code": None, "tier": tier_key}
    else:
        user_cart[uid]["tier"] = tier_key

    await state.set_state(OrderState.waiting_for_receipt)
    text = (
        "📸 <b>Отправь скриншот или файл (PDF) чека об оплате прямо в этот чат:</b>\n\n"
        "<i>Как только ты отправишь фото или документ, я сразу передам его Максиму для подтверждения!</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад к реквизитам", callback_data=f"pay_{tier_key}")]
    ])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

@dp.message(OrderState.waiting_for_receipt, F.photo | F.document)
async def process_receipt_file(message: Message, state: FSMContext):
    uid = message.from_user.id
    user_info = user_cart.get(uid, {"discount": 0, "promo_code": "Нет", "tier": "tier1"})
    tier_key = user_info.get("tier", "tier1")
    t = TARIFFS.get(tier_key, TARIFFS["tier1"])
    discount = user_info.get("discount", 0)
    final_price = int(t["price"] * (100 - discount) / 100)

    await state.clear()

    if tier_key == "consult":
        client_reply = (
            "✅ <b>Чек за личную консультацию (40 минут) получен и отправлен Максиму!</b>\n\n"
            f"Напиши сейчас Максиму в личные сообщения @{ADMIN_USERNAME}, в какой день и время тебе удобно созвониться — после проверки чека вы сразу согласуете время звонка!"
        )
    else:
        client_reply = (
            "✅ <b>Чек успешно получен и отправлен на проверку!</b>\n\n"
            "Обычно подтверждение занимает от 2 до 15 минут. Как только Максим проверит перевод, бот автоматически пришлёт тебе инструкции и доступ прямо сюда!"
        )

    # Ответ клиенту
    await message.answer(
        client_reply,
        parse_mode="HTML",
        reply_markup=get_main_menu_kb()
    )

    # Уведомление тебе (Админу) с кнопками подтверждения в 1 клик
    username_str = f"@{message.from_user.username}" if message.from_user.username else "Без юзернейма"
    admin_caption = (
        "🚨 <b>НОВАЯ ОПЛАТА В БОТЕ!</b>\n\n"
        f"👤 <b>Клиент:</b> {message.from_user.full_name} ({username_str})\n"
        f"🆔 <b>ID:</b> <code>{uid}</code>\n"
        f"📦 <b>Формат:</b> {t['name']}\n"
        f"🎟 <b>Промокод:</b> {user_info.get('promo_code') or 'Без промокода'} (-{discount}%)\n"
        f"💰 <b>Ожидаемая сумма:</b> {final_price} ₽\n\n"
        "Проверь поступление на карту и нажми кнопку ниже:"
    )

    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"approve_{uid}_{tier_key}")],
        [InlineKeyboardButton(text="❌ Отклонить (чек неверный)", callback_data=f"reject_{uid}")]
    ])

    try:
        if message.photo:
            await bot.send_photo(
                chat_id=ADMIN_ID,
                photo=message.photo[-1].file_id,
                caption=admin_caption,
                parse_mode="HTML",
                reply_markup=admin_kb
            )
        elif message.document:
            await bot.send_document(
                chat_id=ADMIN_ID,
                document=message.document.file_id,
                caption=admin_caption,
                parse_mode="HTML",
                reply_markup=admin_kb
            )
    except Exception as e:
        logging.error(f"Ошибка отправки чека админу (проверь ADMIN_ID): {e}")

@dp.message(OrderState.waiting_for_receipt)
async def process_receipt_invalid(message: Message):
    await message.answer(
        "⚠️ Пожалуйста, отправь именно <b>картинку (скриншот)</b> или <b>PDF-файл</b> чека об оплате!",
        parse_mode="HTML"
    )

# =====================================================================
# АДМИН-КНОПКИ (ПОДТВЕРЖДЕНИЕ ОПЛАТЫ В 1 КЛИК С ТЕЛЕФОНА)
# =====================================================================

@dp.callback_query(F.data.startswith("approve_"))
async def cb_admin_approve(call: CallbackQuery):
    parts = call.data.split("_")
    client_id = int(parts[1])
    tier_key = parts[2]
    t = TARIFFS.get(tier_key, TARIFFS["tier1"])

    if tier_key == "consult":
        access_text = (
            f"🎉 <b>Твоя оплата подтверждена! Запись на личную консультацию (40 минут) активна!</b>\n\n"
            f"👉 <b>Напиши мне в личные сообщения @{ADMIN_USERNAME} слово «КОНСУЛЬТАЦИЯ»</b> и укажи, когда тебе удобно созвониться — мы текстом договоримся о точном времени звонка!"
        )
    else:
        access_text = (
            f"🎉 <b>Твоя оплата подтверждена! Добро пожаловать в US.GRANT!</b>\n\n"
            f"Твой тариф: <b>{t['name']}</b>\n\n"
            f"👉 <b>Напиши мне в личные сообщения @{ADMIN_USERNAME} слово «СТАРТ»</b>, и я сразу скину тебе победные письма SPARK, шаблон Harvard CV и мы начнём личную работу над твоей заявкой!"
        )

    try:
        await bot.send_message(chat_id=client_id, text=access_text, parse_mode="HTML")
        await call.message.edit_caption(
            caption=call.message.caption + "\n\n✅ <b>СТАТУС: ОДОБРЕНО (Уведомление отправлено клиенту)</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        await call.answer(f"Ошибка отправки клиенту: {e}", show_alert=True)

@dp.callback_query(F.data.startswith("reject_"))
async def cb_admin_reject(call: CallbackQuery):
    client_id = int(call.data.split("_")[1])
    reject_text = (
        "⚠️ <b>Не удалось подтвердить твой платёж по отправленному чеку.</b>\n\n"
        f"Пожалуйста, проверь статус перевода в банке или напиши напрямую Максиму: @{ADMIN_USERNAME}"
    )
    try:
        await bot.send_message(chat_id=client_id, text=reject_text, parse_mode="HTML")
        await call.message.edit_caption(
            caption=call.message.caption + "\n\n❌ <b>СТАТУС: ОТКЛОНЕНО</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)

async def main():
    print("🚀 Бот US.GRANT успешно запущен и готов принимать оплаты!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
