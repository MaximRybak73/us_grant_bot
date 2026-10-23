import asyncio
import logging
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# =====================================================================
# НАСТРОЙКИ
# =====================================================================

BOT_TOKEN = "8950848059:AAHAodC_g4ZqvWEXXxUq8KR383-vSlmslc0"

ADMIN_ID = 1054746088
ADMIN_USERNAME = "MaxxximSergeevich"

PAYMENT_PHONE = "+79639117097"
PAYMENT_BANK = "Сбербанк"
PAYMENT_RECIPIENT = "Максим Сергеевич Д."

# Ключи здесь совпадают с ключами на сайте (data-book="base" / "vip" / "consult"),
# поэтому кнопка на сайте вида t.me/<бот>?start=base открывает сразу нужную карточку.
TARIFFS = {
    "base": {
        "title": "Подача и разбор",
        "price": 6490,
        "old_price": 10900,
        "points": [
            "Разбор твоей истории и выбор темы эссе",
            "Личная правка мотивационного письма и резюме",
            "Разбор сценария видеовизитки",
            "Подготовка к отборочному интервью",
            "Сопровождение по анкете DS-160",
        ],
    },
    "vip": {
        "title": "VIP · Полное ведение",
        "price": 12900,
        "old_price": 19900,
        "points": [
            "Всё из тарифа «Подача и разбор», без очереди",
            "Личная связь со мной в Telegram на протяжении подготовки",
            "Отдельная подготовка к интервью с консулом",
            "Полная проверка документов перед поездкой",
            "Сопровождение по прилёту: банк, сим-карта, дисциплины в вузе",
        ],
    },
    "consult": {
        "title": "Личная консультация",
        "price": 1990,
        "old_price": None,
        "points": [
            "Один созвон со мной один на один",
            "Честная оценка твоих шансов на грант",
            "Разбор темы эссе и структуры резюме",
            "Ответы на вопросы по отбору и визе",
        ],
    },
}

PROMO_CODE = "TAMPA27"
PROMO_PERCENT = 15
PROMO_UNTIL = datetime(2026, 11, 7, 23, 59, 59, tzinfo=timezone.utc)


class Order(StatesGroup):
    promo = State()
    receipt = State()


# uid -> {"tariff": str, "discount": int, "promo": str | None}
sessions: dict[int, dict] = {}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


def get_session(uid: int) -> dict:
    if uid not in sessions:
        sessions[uid] = {"tariff": "base", "discount": 0, "promo": None}
    return sessions[uid]


def fmt(amount: int) -> str:
    return f"{amount:,} ₽".replace(",", " ")


def price_now(key: str, discount: int) -> int:
    base = TARIFFS[key]["price"]
    return round(base * (100 - discount) / 100)


def promo_active() -> bool:
    return datetime.now(timezone.utc) < PROMO_UNTIL


# =====================================================================
# ЭКРАНЫ
# =====================================================================

def screen_home() -> tuple[str, InlineKeyboardMarkup]:
    text = (
        "Это бот личного сопровождения к программе SPARK (грант $20 000).\n\n"
        "Я Максим — финалист SPARK 2026, прошёл весь путь от заявки до учёбы "
        "в США. Здесь можно выбрать формат работы со мной, посмотреть условия "
        "и оплатить без лишних шагов."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Форматы и цены", callback_data="list:tariffs")],
        [InlineKeyboardButton(text="Личная консультация", callback_data="open:consult")],
        [InlineKeyboardButton(text="У меня есть промокод", callback_data="promo:ask")],
        [InlineKeyboardButton(text="Написать мне напрямую", url=f"https://t.me/{ADMIN_USERNAME}")],
    ])
    return text, kb


def screen_tariffs(uid: int) -> tuple[str, InlineKeyboardMarkup]:
    s = get_session(uid)
    discount = s["discount"]
    lines = ["Выбери формат — ниже видно, что входит в каждый.\n"]
    if discount:
        lines.append(f"Промокод {s['promo']} применён, скидка −{discount}%.\n")
    elif promo_active():
        lines.append(f"Есть промокод с сайта «{PROMO_CODE}» — можно применить перед оплатой.\n")

    rows = []
    for key in ("base", "vip"):
        t = TARIFFS[key]
        price = price_now(key, discount)
        label = f"{t['title']} — {fmt(price)}"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"open:{key}")])
    rows.append([InlineKeyboardButton(text="Личная консультация", callback_data="open:consult")])
    if not discount and promo_active():
        rows.append([InlineKeyboardButton(text="Ввести промокод", callback_data="promo:ask")])
    rows.append([InlineKeyboardButton(text="Назад", callback_data="nav:home")])

    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


def screen_tariff_card(uid: int, key: str) -> tuple[str, InlineKeyboardMarkup]:
    s = get_session(uid)
    s["tariff"] = key
    t = TARIFFS[key]
    discount = s["discount"]
    price = price_now(key, discount)

    bullets = "\n".join(f"· {p}" for p in t["points"])
    price_block = f"<b>{fmt(price)}</b>"
    if t["old_price"] and not discount:
        price_block = f"<s>{fmt(t['old_price'])}</s>  <b>{fmt(price)}</b>"
    elif t["old_price"] and discount:
        price_block = f"<s>{fmt(t['old_price'])}</s>  <b>{fmt(price)}</b> (−{discount}%)"

    text = f"<b>{t['title']}</b>\n\n{bullets}\n\n{price_block}"

    rows = [[InlineKeyboardButton(text="Перейти к оплате", callback_data=f"pay:{key}")]]
    if not discount and promo_active():
        rows.append([InlineKeyboardButton(text="Ввести промокод", callback_data="promo:ask")])
    rows.append([InlineKeyboardButton(text="Вопрос по формату", url=f"https://t.me/{ADMIN_USERNAME}")])
    back_to = "list:tariffs" if key != "consult" else "nav:home"
    rows.append([InlineKeyboardButton(text="Назад", callback_data=back_to)])

    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def screen_payment(uid: int, key: str) -> tuple[str, InlineKeyboardMarkup]:
    s = get_session(uid)
    price = price_now(key, s["discount"])
    text = (
        f"К оплате: <b>{fmt(price)}</b>\n\n"
        "Перевод по СБП, по номеру телефона:\n"
        f"<code>{PAYMENT_PHONE}</code>\n"
        f"Банк: {PAYMENT_BANK}\n"
        f"Получатель: {PAYMENT_RECIPIENT}\n\n"
        "После перевода пришли сюда скриншот или файл чека — я проверю его лично "
        "и бот сразу откроет доступ к следующему шагу."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Я перевёл(а) — отправить чек", callback_data=f"receipt:{key}")],
        [InlineKeyboardButton(text="Назад", callback_data=f"open:{key}")],
    ])
    return text, kb


# =====================================================================
# СТАРТ / НАВИГАЦИЯ
# =====================================================================

@dp.message(CommandStart(deep_link=True))
async def cmd_start_deeplink(message: Message, command: CommandObject, state: FSMContext):
    await state.clear()
    get_session(message.from_user.id)
    payload = (command.args or "").strip().lower()
    if payload in TARIFFS:
        text, kb = screen_tariff_card(message.from_user.id, payload)
        intro = "Привет! Ты перешёл(а) по ссылке с сайта — вот этот формат подробнее.\n\n"
        await message.answer(intro + text, parse_mode="HTML", reply_markup=kb)
    else:
        text, kb = screen_home()
        await message.answer(text, reply_markup=kb)


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    get_session(message.from_user.id)
    text, kb = screen_home()
    await message.answer(text, reply_markup=kb)


@dp.callback_query(F.data == "nav:home")
async def cb_home(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text, kb = screen_home()
    await call.message.edit_text(text, reply_markup=kb)


@dp.callback_query(F.data == "list:tariffs")
async def cb_list_tariffs(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text, kb = screen_tariffs(call.from_user.id)
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


@dp.callback_query(F.data.startswith("open:"))
async def cb_open_tariff(call: CallbackQuery):
    key = call.data.split(":", 1)[1]
    text, kb = screen_tariff_card(call.from_user.id, key)
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


# =====================================================================
# ПРОМОКОД
# =====================================================================

@dp.callback_query(F.data == "promo:ask")
async def cb_promo_ask(call: CallbackQuery, state: FSMContext):
    if not promo_active():
        await call.answer("Срок действия промокода уже истёк.", show_alert=True)
        return
    await state.set_state(Order.promo)
    text = "Пришли промокод одним сообщением."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="list:tariffs")]
    ])
    await call.message.edit_text(text, reply_markup=kb)


@dp.message(Order.promo)
async def process_promo(message: Message, state: FSMContext):
    uid = message.from_user.id
    code = (message.text or "").strip().upper()
    s = get_session(uid)

    if code == PROMO_CODE and promo_active():
        s["discount"] = PROMO_PERCENT
        s["promo"] = code
        await state.clear()
        text, kb = screen_tariffs(uid)
        await message.answer(f"Промокод применён, скидка −{PROMO_PERCENT}%.\n\n" + text,
                              parse_mode="HTML", reply_markup=kb)
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Попробовать ещё раз", callback_data="promo:ask")],
            [InlineKeyboardButton(text="К форматам", callback_data="list:tariffs")],
        ])
        await message.answer("Такой промокод не найден или его срок истёк.", reply_markup=kb)


# =====================================================================
# ОПЛАТА И ЧЕК
# =====================================================================

@dp.callback_query(F.data.startswith("pay:"))
async def cb_pay(call: CallbackQuery):
    key = call.data.split(":", 1)[1]
    text, kb = screen_payment(call.from_user.id, key)
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


@dp.callback_query(F.data.startswith("receipt:"))
async def cb_ask_receipt(call: CallbackQuery, state: FSMContext):
    key = call.data.split(":", 1)[1]
    get_session(call.from_user.id)["tariff"] = key
    await state.set_state(Order.receipt)
    text = "Пришли сюда фото или PDF чека об оплате."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data=f"pay:{key}")]
    ])
    await call.message.edit_text(text, reply_markup=kb)


@dp.message(Order.receipt, F.photo | F.document)
async def process_receipt(message: Message, state: FSMContext):
    uid = message.from_user.id
    s = get_session(uid)
    key = s["tariff"]
    t = TARIFFS[key]
    price = price_now(key, s["discount"])

    await state.clear()

    if key == "consult":
        reply = (
            "Чек получен, я его проверю.\n\n"
            f"Пока жди подтверждения — напиши мне в личные сообщения @{ADMIN_USERNAME}, "
            "когда тебе удобно созвониться, и мы согласуем время."
        )
    else:
        reply = (
            "Чек получен и уже у меня на проверке. Обычно это занимает до 15 минут — "
            "как только подтвержу перевод, бот пришлёт дальнейшие шаги сюда же."
        )

    home_text, home_kb = screen_home()
    await message.answer(reply, reply_markup=home_kb)

    username = f"@{message.from_user.username}" if message.from_user.username else "без юзернейма"
    caption = (
        "Новая оплата\n\n"
        f"Клиент: {message.from_user.full_name} ({username})\n"
        f"ID: <code>{uid}</code>\n"
        f"Формат: {t['title']}\n"
        f"Промокод: {s['promo'] or '—'} (−{s['discount']}%)\n"
        f"Сумма: {fmt(price)}"
    )
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подтвердить", callback_data=f"approve:{uid}:{key}")],
        [InlineKeyboardButton(text="Отклонить", callback_data=f"reject:{uid}")],
    ])

    try:
        if message.photo:
            await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=caption,
                                  parse_mode="HTML", reply_markup=admin_kb)
        elif message.document:
            await bot.send_document(ADMIN_ID, message.document.file_id, caption=caption,
                                     parse_mode="HTML", reply_markup=admin_kb)
    except Exception as e:
        logging.error(f"Не удалось отправить чек админу: {e}")


@dp.message(Order.receipt)
async def process_receipt_invalid(message: Message):
    await message.answer("Нужен файл — пришли фото или PDF чека.")


# =====================================================================
# АДМИН: ПОДТВЕРЖДЕНИЕ / ОТКЛОНЕНИЕ
# =====================================================================

@dp.callback_query(F.data.startswith("approve:"))
async def cb_approve(call: CallbackQuery):
    _, client_id, key = call.data.split(":")
    client_id = int(client_id)
    t = TARIFFS[key]

    if key == "consult":
        text = (
            "Оплата подтверждена, запись на консультацию активна.\n\n"
            f"Напиши мне в личные сообщения @{ADMIN_USERNAME} и укажи удобное время звонка."
        )
    else:
        text = (
            "Оплата подтверждена, добро пожаловать.\n\n"
            f"Формат: {t['title']}\n\n"
            f"Напиши мне в личные сообщения @{ADMIN_USERNAME} — начнём работу над твоей заявкой."
        )

    try:
        await bot.send_message(client_id, text, parse_mode="HTML")
        await call.message.edit_caption(
            caption=(call.message.caption or "") + "\n\nСтатус: подтверждено",
            parse_mode="HTML",
        )
    except Exception as e:
        await call.answer(f"Не удалось отправить клиенту: {e}", show_alert=True)


@dp.callback_query(F.data.startswith("reject:"))
async def cb_reject(call: CallbackQuery):
    client_id = int(call.data.split(":")[1])
    text = (
        "Не вижу подтверждения перевода по этому чеку.\n\n"
        f"Проверь, пожалуйста, статус в банке или напиши напрямую: @{ADMIN_USERNAME}"
    )
    try:
        await bot.send_message(client_id, text)
        await call.message.edit_caption(
            caption=(call.message.caption or "") + "\n\nСтатус: отклонено",
            parse_mode="HTML",
        )
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)


async def main():
    print("Бот запущен.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
