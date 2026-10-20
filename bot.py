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

# 2. Твой цифровой Telegram ID — сюда бот будет слать чеки!
ADMIN_ID = 1054746088

# 3. Твой юзернейм в Telegram (без @) и ссылки на закрытый канал
ADMIN_USERNAME = "maksim_dubtsov"
PRIVATE_CHANNEL_LINK = "https://t.me/+твоя_приватная_ссылка_на_канал"
PUBLIC_CHANNEL_LINK = "https://t.me/your_us_channel"

# 4. Реквизиты для перевода по СБП / номеру телефона
PAYMENT_PHONE = "+79639117097"
PAYMENT_BANKS = "Сбербанк / Т-Банк (СБП)"
PAYMENT_RECIPIENT = "Максим Сергеевич Д."

# =====================================================================
# БАЗА ТАРИФОВ И ПРОМОКОДОВ
# =====================================================================

TARIFFS = {
    "tier1": {
        "name": "📘 База и Гайды",
        "price": 3990,
        "old_price": 6500,
        "desc": (
            "• Доступ в закрытый Telegram-канал со всей базой знаний\n"
            "• Разбор реальных писем, прошедших отбор + шаблон Harvard CV\n"
            "• Гайд по структуре видеовизитки и подготовке к Duolingo (DET)\n"
            "• Пошаговая инструкция по заполнению анкеты DS-160\n"
            "• Закрытый чат участников потока"
        )
    },
    "tier2": {
        "name": "🔥 Менторство в Telegram (Хит)",
        "price": 7990,
        "old_price": 12900,
        "desc": (
            "• Всё из тарифа «База и Гайды» + закрытые материалы\n"
            "• Помощь с концепцией заявки: выбираем сильную тему и угол подачи\n"
            "• Проверка и правка твоего мотивационного письма и Harvard CV\n"
            "• Рекомендации по сценарию и подаче для видеовизитки\n"
            "• Подготовка к интервью: разбор вопросов и составление сильных ответов\n"
            "• Ответы на вопросы по анкете DS-160 и визе J-1 в личном чате"
        )
    },
    "tier3": {
        "name": "💎 Приоритет + США (VIP)",
        "price": 14900,
        "old_price": 24000,
        "desc": (
            "• Всё из тарифа «Менторство» с приоритетным разбором без очереди\n"
            "• Адаптация документов сразу под несколько обменных программ США\n"
            "• Индивидуальная проработка ответов для комиссии и консула\n"
            "• Детальная проверка визовых документов перед посольством\n"
            "• Личный гайд по прилёту: открытие карты Chase, связь и быт в США"
        )
    }
}

# Промокоды: TAMPA27 (с сайта даёт 15%), GRANT20 (секретный за подписку/личку даёт 20%)
PROMOCODES = {
    "TAMPA27": 15,
    "SPARK15": 15,
    "GRANT20": 20,
    "VIP20": 20
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
        [
            InlineKeyboardButton(text="🎁 Промокод на -20%", callback_data="get_promo_info"),
            InlineKeyboardButton(text="🇺🇸 О проекте", callback_data="about_project")
        ],
        [InlineKeyboardButton(text="💬 Задать вопрос Максиму", url=f"https://t.me/{ADMIN_USERNAME}")]
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
    
    buttons.append([InlineKeyboardButton(text="🎟 Ввести промокод", callback_data="enter_promo")])
    buttons.append([InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_tariff_detail_kb(tier_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Перейти к оплате", callback_data=f"pay_{tier_key}")],
        [InlineKeyboardButton(text="🎟 Ввести промокод на скидку", callback_data="enter_promo")],
        [InlineKeyboardButton(text="💬 Уточнить вопрос у Максима", url=f"https://t.me/{ADMIN_USERNAME}")],
        [InlineKeyboardButton(text="⬅️ Назад к тарифам", callback_data="show_tariffs")]
    ])

def get_payment_kb(tier_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатил(а) - отправить чек", callback_data=f"send_receipt_{tier_key}")],
        [InlineKeyboardButton(text="💬 Написать Максиму в личку", url=f"https://t.me/{ADMIN_USERNAME}")],
        [InlineKeyboardButton(text="⬅️ Назад к описанию тарифа", callback_data=f"select_{tier_key}")]
    ])

# =====================================================================
# ОБРАБОТЧИКИ КОМАНД И КНОПОК
# =====================================================================

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    if uid not in user_cart:
        user_cart[uid] = {"discount": 0, "promo_code": None, "tier": "tier2"}

    welcome_text = (
        f"Привет, <b>{message.from_user.first_name}</b>! 👋\n\n"
        "Добро пожаловать в <b>US.GRANT // Mentorship</b> - пошаговую систему подготовки к грантовым программам обмена в США ($20,000) от Максима Дубцова.\n\n"
        "Я сам прошёл весь путь от студента Московского Политеха и получения визы J-1 в Казахстане до 3 месяцев учёбы во Флориде (University of Tampa) и саммита в Колорадо за счёт полного гранта.\n\n"
        "Здесь ты можешь:\n"
        "• Выбрать формат подготовки (вся работа удобно в Telegram)\n"
        "• Активировать промокод на скидку 15-20%\n"
        "• Получить мгновенный доступ к закрытым гайдам, реальным письмам и личному разбору\n\n"
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
        "🇺🇸 <b>Почему формат работы в Telegram даёт максимальный результат?</b>\n\n"
        "1. <b>Без воды и часовых лекций:</b> тебе не нужно подстраиваться под расписание созвонов. Ты получаешь выжимку, шаблоны Harvard CV и примеры реальных победных эссе.\n\n"
        "2. <b>Персональная проверка:</b> на тарифах с менторством ты скидываешь свои черновики и вопросы прямо в чат, а я проверяю их и даю готовые сильные формулировки по американским стандартам.\n\n"
        "3. <b>Практический опыт 2026 года:</b> актуальная информация по Duolingo (DET), анкете DS-160, получению визы J-1 в Казахстане и открытию банковской карты Chase в США."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 Посмотреть тарифы", callback_data="show_tariffs")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_main")]
    ])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "get_promo_info")
async def cb_get_promo_info(call: CallbackQuery):
    text = (
        "🎁 <b>Как получить скидку до 20% на любой тариф?</b>\n\n"
        "У тебя есть 2 варианта:\n\n"
        "1️⃣ <b>Базовый промокод с сайта (-15%):</b>\n"
        "Нажми кнопку «Ввести промокод» и напиши код <code>TAMPA27</code> - цены сразу пересчитаются со скидкой 15%.\n\n"
        "2️⃣ <b>Повышенный промокод от Максима (-20%):</b>\n"
        "Напиши мне в личные сообщения слово <b>«ГРАНТ»</b>, коротко расскажи, на каком ты курсе, и я выдам тебе персональный промокод на <b>20% скидки</b>!"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написать Максиму «ГРАНТ»", url=f"https://t.me/{ADMIN_USERNAME}")],
        [InlineKeyboardButton(text="🎟 Ввести промокод сейчас", callback_data="enter_promo")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_main")]
    ])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "show_tariffs")
async def cb_show_tariffs(call: CallbackQuery, state: FSMContext):
    await state.clear()
    uid = call.from_user.id
    if uid not in user_cart:
        user_cart[uid] = {"discount": 0, "promo_code": None, "tier": "tier2"}

    discount = user_cart[uid].get("discount", 0)
    promo = user_cart[uid].get("promo_code")

    promo_status = (
        f"✅ <b>Активен промокод {promo} (скидка -{discount}%)</b>\n\n"
        if discount > 0 else
        "💡 <i>У тебя есть промокод? Нажми «Ввести промокод» ниже для пересчёта цен.</i>\n\n"
    )

    text = (
        "🔥 <b>Выбери свой формат подготовки к гранту $20,000:</b>\n\n"
        f"{promo_status}"
        "Нажми на любой тариф, чтобы посмотреть полное описание и перейти к оплате:"
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

    t = TARIFFS[tier_key]
    discount = user_cart[uid].get("discount", 0)
    final_price = int(t["price"] * (100 - discount) / 100)
    price_str = f"{final_price:,} ₽".replace(",", " ")
    old_str = f"{t['old_price']:,} ₽".replace(",", " ")

    discount_line = f" (с учётом твоей скидки -{discount}%!)" if discount > 0 else ""

    text = (
        f"<b>{t['name']}</b>\n\n"
        f"<b>Что входит в этот формат:</b>\n{t['desc']}\n\n"
        f"〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️\n"
        f"Старая цена: <s>{old_str}</s>\n"
        f"💰 <b>К оплате сейчас: {price_str}</b>{discount_line}\n\n"
        "После оплаты ты сразу получаешь доступ к материалам в Telegram."
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=get_tariff_detail_kb(tier_key))

# =====================================================================
# ВВОД ПРОМОКОДА
# =====================================================================

@dp.callback_query(F.data == "enter_promo")
async def cb_enter_promo(call: CallbackQuery, state: FSMContext):
    await state.set_state(OrderState.waiting_for_promo)
    text = (
        "🎟 <b>Введи свой промокод ответным сообщением в чат:</b>\n\n"
        "<i>Например: TAMPA27 (или персональный код на -20%, если ты получил его у Максима в личке).</i>"
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
        user_cart[uid] = {"discount": 0, "promo_code": None, "tier": "tier2"}

    if code in PROMOCODES:
        disc = PROMOCODES[code]
        user_cart[uid]["discount"] = disc
        user_cart[uid]["promo_code"] = code
        await state.clear()

        await message.answer(
            f"🎉 <b>Супер! Промокод {code} активирован!</b>\n"
            f"Твоя скидка <b>-{disc}%</b> применена ко всем тарифам. Выбирай формат ниже:",
            parse_mode="HTML",
            reply_markup=get_tariffs_kb(uid)
        )
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔥 Перейти к тарифам", callback_data="show_tariffs")],
            [InlineKeyboardButton(text="💬 Попросить промокод у Максима", url=f"https://t.me/{ADMIN_USERNAME}")]
        ])
        await message.answer(
            "❌ <b>Такого промокода не найдено.</b>\n"
            "Проверь правильность написания (например, <code>TAMPA27</code>) или напиши Максиму в личку!",
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
    t = TARIFFS[tier_key]
    discount = user_cart.get(uid, {}).get("discount", 0)
    final_price = int(t["price"] * (100 - discount) / 100)
    price_str = f"{final_price:,} ₽".replace(",", " ")

    text = (
        f"💳 <b>Оформление доступа: {t['name']}</b>\n"
        f"Сумма к оплате: <b>{price_str}</b>\n\n"
        "<b>Реквизиты для перевода по СБП (с любого банка):</b>\n"
        f"📱 Номер телефона: <code>{PAYMENT_PHONE}</code> <i>(нажми на номер, он скопируется)</i>\n"
        f"🏦 Банк: <b>{PAYMENT_BANKS}</b>\n"
        f"👤 Получатель: <b>{PAYMENT_RECIPIENT}</b>\n\n"
        "<b>Как получить доступ за 1 минуту:</b>\n"
        f"1. Скопируй номер <code>{PAYMENT_PHONE}</code> и переведи <b>{price_str}</b> по СБП.\n"
        "2. Нажми кнопку <b>«✅ Я оплатил(а) - отправить чек»</b> ниже.\n"
        "3. Пришли скриншот или PDF квитанции сюда в чат!"
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
        "<i>Как только ты отправишь фото или документ, я сразу передам его Максиму для открытия доступа!</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад к реквизитам", callback_data=f"pay_{tier_key}")]
    ])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

@dp.message(OrderState.waiting_for_receipt, F.photo | F.document)
async def process_receipt_file(message: Message, state: FSMContext):
    uid = message.from_user.id
    user_info = user_cart.get(uid, {"discount": 0, "promo_code": "Нет", "tier": "tier2"})
    tier_key = user_info.get("tier", "tier2")
    t = TARIFFS[tier_key]
    discount = user_info.get("discount", 0)
    final_price = int(t["price"] * (100 - discount) / 100)

    await state.clear()

    # Ответ клиенту
    await message.answer(
        "✅ <b>Чек успешно получен и отправлен на проверку!</b>\n\n"
        "Обычно подтверждение занимает от 2 до 15 минут. Как только Максим проверит перевод, бот автоматически пришлёт тебе закрытую ссылку и инструкции прямо сюда!",
        parse_mode="HTML",
        reply_markup=get_main_menu_kb()
    )

    # Уведомление тебе (Админу) с кнопками подтверждения в 1 клик
    username_str = f"@{message.from_user.username}" if message.from_user.username else "Без юзернейма"
    admin_caption = (
        "🚨 <b>НОВАЯ ОПЛАТА В БОТЕ!</b>\n\n"
        f"👤 <b>Клиент:</b> {message.from_user.full_name} ({username_str})\n"
        f"🆔 <b>ID:</b> <code>{uid}</code>\n"
        f"📦 <b>Тариф:</b> {t['name']}\n"
        f"🎟 <b>Промокод:</b> {user_info.get('promo_code') or 'Без промокода'} (-{discount}%)\n"
        f"💰 <b>Ожидаемая сумма:</b> {final_price} ₽\n\n"
        "Проверь поступление на карту и нажми кнопку ниже:"
    )

    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить и выдать доступ", callback_data=f"approve_{uid}_{tier_key}")],
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
    t = TARIFFS.get(tier_key, TARIFFS["tier2"])

    access_text = (
        f"🎉 <b>Твоя оплата подтверждена! Добро пожаловать на борт!</b>\n\n"
        f"Твой тариф: <b>{t['name']}</b>\n\n"
        f"1️⃣ <b>Твоя ссылка в закрытый канал с базой и шаблонами:</b>\n"
        f"👉 {PRIVATE_CHANNEL_LINK}\n\n"
        f"2️⃣ <b>Личный контакт Максима для разбора и вопросов:</b>\n"
        f"👉 Напиши мне @{ADMIN_USERNAME} слово <b>«СТАРТ»</b> (если у тебя тариф с менторством или приоритетом), и мы сразу начнём работу над твоей заявкой!"
    )

    try:
        await bot.send_message(chat_id=client_id, text=access_text, parse_mode="HTML")
        await call.message.edit_caption(
            caption=call.message.caption + "\n\n✅ <b>СТАТУС: ОДОБРЕНО (Доступ выдан клиенту)</b>",
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