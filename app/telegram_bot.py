from __future__ import annotations

import logging

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .config import settings
from .services import (
    build_evening_reminder,
    build_morning_reminder,
    build_repeat_intervention,
    create_commitment,
    format_day_status_message,
    format_commitment_created_message,
    format_commitment_done_message,
    format_commitment_moved_message,
    format_commitments_message,
    format_deadline_help,
    format_analysis_message,
    format_patterns_message,
    format_single_commitment_message,
    format_weekly_review_message,
    get_commitment,
    get_due_commitment_reminders,
    list_active_telegram_chats,
    mark_commitment_done,
    move_commitment,
    run_daily_reset,
    save_capture,
    set_telegram_chat_active,
    upsert_telegram_chat,
)


logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

RESET_KEYS = ("impact_focus", "operational_risk", "managerial_action")
COMMIT_KEYS = ("text", "due_date", "definition_of_done")
RESET_PROMPTS = {
    "impact_focus": "1/3 Что сегодня реально влияет на результат?",
    "operational_risk": "2/3 Где ты рискуешь снова влезть в операционку?",
    "managerial_action": "3/3 Какое одно управленческое действие обязательно сегодня?",
}
COMMIT_PROMPTS = {
    "text": "1/3 Какой конкретный результат ты обязуешься получить?",
    "due_date": (
        "2/3 Укажи точный срок в формате YYYY-MM-DD HH:MM.\n"
        "Пример: 2026-03-28 16:00"
    ),
    "definition_of_done": "3/3 Что будет считаться готовым результатом? Один конкретный критерий.",
}
MENU_TRIGGER = "Меню"
MENU_KEYBOARD = ReplyKeyboardMarkup(
    [[KeyboardButton(MENU_TRIGGER)]],
    resize_keyboard=True,
    is_persistent=True,
)


def _build_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Новая запись", callback_data="menu:new_entry"),
                InlineKeyboardButton("Daily Reset", callback_data="menu:reset"),
            ],
            [
                InlineKeyboardButton("Новое обязательство", callback_data="menu:commit"),
                InlineKeyboardButton("Обязательства", callback_data="menu:commitments"),
            ],
            [
                InlineKeyboardButton("Weekly Review", callback_data="menu:weekly"),
                InlineKeyboardButton("Паттерны", callback_data="menu:patterns"),
            ],
            [
                InlineKeyboardButton("Статус дня", callback_data="menu:day_status"),
                InlineKeyboardButton("Статус", callback_data="menu:status"),
            ],
        ]
    )


def _build_commitment_actions(commitment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Done", callback_data=f"commitment:done:{commitment_id}"),
                InlineKeyboardButton("Move", callback_data=f"commitment:move:{commitment_id}"),
            ]
        ]
    )


def _reset_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["daily_reset_step"] = RESET_KEYS[0]
    context.user_data["daily_reset_payload"] = {}


def _clear_reset_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("daily_reset_step", None)
    context.user_data.pop("daily_reset_payload", None)


def _start_commit_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["commit_step"] = COMMIT_KEYS[0]
    context.user_data["commit_payload"] = {}


def _clear_commit_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("commit_step", None)
    context.user_data.pop("commit_payload", None)


def _start_move_state(context: ContextTypes.DEFAULT_TYPE, commitment_id: int) -> None:
    context.user_data["move_commitment_id"] = commitment_id


async def _send_menu_message(target, text: str = "Выбери действие.") -> None:
    await target.reply_text(text, reply_markup=_build_main_menu())


async def _show_main_menu(update: Update) -> None:
    if update.message:
        await update.message.reply_text("Выбери действие.", reply_markup=_build_main_menu())
    elif update.callback_query:
        await update.callback_query.edit_message_text("Выбери действие.", reply_markup=_build_main_menu())


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat:
        user = update.effective_user
        upsert_telegram_chat(
            chat_id=update.effective_chat.id,
            username=user.username if user else None,
            first_name=user.first_name if user else None,
        )
    _clear_reset_state(context)
    _clear_commit_state(context)
    context.user_data.pop("move_commitment_id", None)
    await update.message.reply_text(
        "Manager OS bot активен.\n"
        "Команды:\n"
        "/reset - пройти daily reset\n"
        "/commit - создать обязательство с дедлайном\n"
        "/commitments - список открытых обязательств\n"
        "/done ID - отметить обязательство выполненным\n"
        "/move ID - перенести обязательство на новый срок\n"
        "/weekly - недельная ревизия\n"
        "/patterns - повторяющиеся паттерны\n"
        "/day - статус дня\n"
        "/status - статус LLM и режима\n\n"
        "/pause - отключить push-напоминания\n"
        "/resume - снова включить push-напоминания\n\n"
        "Любой обычный текст я трактую как новую запись и сразу разбираю.",
        reply_markup=MENU_KEYBOARD,
    )
    await _send_menu_message(update.message)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"LLM: {'on' if settings.llm_enabled else 'off'}\n"
        f"Model: {settings.openai_model}\n"
        f"Mode: {settings.app_mode}",
        reply_markup=MENU_KEYBOARD,
    )


async def patterns(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(format_patterns_message(), reply_markup=MENU_KEYBOARD)


async def weekly(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(format_weekly_review_message(), reply_markup=MENU_KEYBOARD)


async def day_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(format_day_status_message(), reply_markup=MENU_KEYBOARD)


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _reset_state(context)
    await update.message.reply_text(RESET_PROMPTS[RESET_KEYS[0]], reply_markup=MENU_KEYBOARD)


async def commit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _clear_reset_state(context)
    _clear_commit_state(context)
    context.user_data.pop("move_commitment_id", None)
    _start_commit_state(context)
    await update.message.reply_text(
        "Фиксируем обязательство.\n"
        "Никаких размытых сроков и формулировок.\n"
        f"{COMMIT_PROMPTS[COMMIT_KEYS[0]]}",
        reply_markup=MENU_KEYBOARD,
    )


async def commitments(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    items_text = format_commitments_message()
    await update.message.reply_text(items_text, reply_markup=MENU_KEYBOARD)
    for item in list_active_commitments_for_ui():
        await update.message.reply_text(
            format_single_commitment_message(item),
            reply_markup=_build_commitment_actions(item["id"]),
        )


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Используй так: /done 3", reply_markup=MENU_KEYBOARD)
        return
    try:
        commitment = mark_commitment_done(int(context.args[0]))
    except Exception:
        await update.message.reply_text(
            "Не смог найти обязательство. Проверь ID через /commitments.",
            reply_markup=MENU_KEYBOARD,
        )
        return
    await update.message.reply_text(format_commitment_done_message(commitment), reply_markup=MENU_KEYBOARD)


async def move(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Используй так: /move 3", reply_markup=MENU_KEYBOARD)
        return
    try:
        commitment_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом. Пример: /move 3", reply_markup=MENU_KEYBOARD)
        return
    _clear_reset_state(context)
    _clear_commit_state(context)
    _start_move_state(context, commitment_id)
    await update.message.reply_text(
        f"Новый срок для обязательства #{commitment_id}.\n{format_deadline_help()}",
        reply_markup=MENU_KEYBOARD,
    )


async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat:
        set_telegram_chat_active(update.effective_chat.id, False)
    await update.message.reply_text(
        "Push-напоминания отключены. Анализ входящих сообщений продолжит работать.",
        reply_markup=MENU_KEYBOARD,
    )


async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat:
        user = update.effective_user
        upsert_telegram_chat(
            chat_id=update.effective_chat.id,
            username=user.username if user else None,
            first_name=user.first_name if user else None,
        )
    await update.message.reply_text("Push-напоминания снова включены.", reply_markup=MENU_KEYBOARD)


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _show_main_menu(update)


def list_active_commitments_for_ui() -> list[dict]:
    from .services import list_commitments

    return list_commitments(status="open", limit=10)


async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    action = query.data or ""

    if action == "menu:new_entry":
        await query.message.reply_text(
            "Напиши обычным сообщением любую задачу, тревогу или входящий запрос. Я сразу разберу запись.",
            reply_markup=MENU_KEYBOARD,
        )
        return
    if action == "menu:reset":
        _reset_state(context)
        await query.message.reply_text(RESET_PROMPTS[RESET_KEYS[0]], reply_markup=MENU_KEYBOARD)
        return
    if action == "menu:commit":
        _clear_reset_state(context)
        _clear_commit_state(context)
        context.user_data.pop("move_commitment_id", None)
        _start_commit_state(context)
        await query.message.reply_text(
            "Фиксируем обязательство.\n"
            "Никаких размытых сроков и формулировок.\n"
            f"{COMMIT_PROMPTS[COMMIT_KEYS[0]]}",
            reply_markup=MENU_KEYBOARD,
        )
        return
    if action == "menu:commitments":
        await query.message.reply_text(format_commitments_message(), reply_markup=MENU_KEYBOARD)
        for item in list_active_commitments_for_ui():
            await query.message.reply_text(
                format_single_commitment_message(item),
                reply_markup=_build_commitment_actions(item["id"]),
            )
        return
    if action == "menu:weekly":
        await query.message.reply_text(format_weekly_review_message(), reply_markup=MENU_KEYBOARD)
        return
    if action == "menu:patterns":
        await query.message.reply_text(format_patterns_message(), reply_markup=MENU_KEYBOARD)
        return
    if action == "menu:day_status":
        await query.message.reply_text(format_day_status_message(), reply_markup=MENU_KEYBOARD)
        return
    if action == "menu:status":
        await query.message.reply_text(
            f"LLM: {'on' if settings.llm_enabled else 'off'}\n"
            f"Model: {settings.openai_model}\n"
            f"Mode: {settings.app_mode}",
            reply_markup=MENU_KEYBOARD,
        )
        return

    await _show_main_menu(update)


async def handle_commitment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    payload = (query.data or "").split(":")
    if len(payload) != 3:
        return

    _, action, raw_id = payload
    try:
        commitment_id = int(raw_id)
    except ValueError:
        return

    if action == "done":
        try:
            commitment = mark_commitment_done(commitment_id)
        except Exception:
            await query.message.reply_text("Не смог отметить обязательство как done.", reply_markup=MENU_KEYBOARD)
            return
        await query.message.reply_text(format_commitment_done_message(commitment), reply_markup=MENU_KEYBOARD)
        return

    if action == "move":
        item = get_commitment(commitment_id)
        if not item:
            await query.message.reply_text("Не смог найти обязательство.", reply_markup=MENU_KEYBOARD)
            return
        _clear_reset_state(context)
        _clear_commit_state(context)
        _start_move_state(context, commitment_id)
        await query.message.reply_text(
            f"Новый срок для обязательства #{commitment_id}.\n{format_deadline_help()}",
            reply_markup=MENU_KEYBOARD,
        )
        return


async def push_morning_reset(context: ContextTypes.DEFAULT_TYPE) -> None:
    for chat in list_active_telegram_chats():
        await context.bot.send_message(chat_id=chat["chat_id"], text=build_morning_reminder())


async def push_evening_review(context: ContextTypes.DEFAULT_TYPE) -> None:
    for chat in list_active_telegram_chats():
        await context.bot.send_message(chat_id=chat["chat_id"], text=build_evening_reminder())


async def push_weekly_review(context: ContextTypes.DEFAULT_TYPE) -> None:
    message = format_weekly_review_message()
    for chat in list_active_telegram_chats():
        await context.bot.send_message(chat_id=chat["chat_id"], text=message)


async def push_commitment_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    reminders = get_due_commitment_reminders()
    if not reminders:
        return
    for chat in list_active_telegram_chats():
        for reminder in reminders:
            await context.bot.send_message(chat_id=chat["chat_id"], text=reminder)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if message is None or not message.text:
        return
    if update.effective_chat:
        user = update.effective_user
        upsert_telegram_chat(
            chat_id=update.effective_chat.id,
            username=user.username if user else None,
            first_name=user.first_name if user else None,
        )

    if message.text.strip() == MENU_TRIGGER:
        await _send_menu_message(message)
        return

    step = context.user_data.get("daily_reset_step")
    if step:
        payload = context.user_data.setdefault("daily_reset_payload", {})
        payload[step] = message.text

        current_index = RESET_KEYS.index(step)
        if current_index < len(RESET_KEYS) - 1:
            next_step = RESET_KEYS[current_index + 1]
            context.user_data["daily_reset_step"] = next_step
            await message.reply_text(RESET_PROMPTS[next_step])
            return

        _clear_reset_state(context)
        result = run_daily_reset(
            impact_focus=payload["impact_focus"],
            operational_risk=payload["operational_risk"],
            managerial_action=payload["managerial_action"],
        )
        await message.reply_text(
            "Daily reset\n"
            f"Score: {result.score}\n"
            f"Risk: {result.role_risk}\n"
            f"Distortion: {result.distortion}\n"
            f"Boundary: {result.hard_boundary}\n"
            f"Must do: {result.must_do_today}"
        )
        return

    commit_step = context.user_data.get("commit_step")
    if commit_step:
        payload = context.user_data.setdefault("commit_payload", {})
        payload[commit_step] = message.text.strip()

        current_index = COMMIT_KEYS.index(commit_step)
        if current_index < len(COMMIT_KEYS) - 1:
            next_step = COMMIT_KEYS[current_index + 1]
            context.user_data["commit_step"] = next_step
            if next_step == "due_date":
                await message.reply_text(format_deadline_help(), reply_markup=MENU_KEYBOARD)
            await message.reply_text(COMMIT_PROMPTS[next_step], reply_markup=MENU_KEYBOARD)
            return

        try:
            commitment = create_commitment(
                text=payload["text"],
                due_date=payload["due_date"],
                definition_of_done=payload["definition_of_done"],
            )
        except ValueError as exc:
            _clear_commit_state(context)
            await message.reply_text(str(exc), reply_markup=MENU_KEYBOARD)
            await message.reply_text("Попробуй снова через /commit.", reply_markup=MENU_KEYBOARD)
            return

        _clear_commit_state(context)
        await message.reply_text(format_commitment_created_message(commitment), reply_markup=MENU_KEYBOARD)
        return

    move_commitment_id = context.user_data.get("move_commitment_id")
    if move_commitment_id:
        try:
            commitment = move_commitment(move_commitment_id, message.text.strip())
        except ValueError as exc:
            await message.reply_text(str(exc), reply_markup=MENU_KEYBOARD)
            await message.reply_text(format_deadline_help(), reply_markup=MENU_KEYBOARD)
            return
        context.user_data.pop("move_commitment_id", None)
        await message.reply_text(format_commitment_moved_message(commitment), reply_markup=MENU_KEYBOARD)
        return

    saved = save_capture(message.text, source="telegram")
    await message.reply_text(format_analysis_message(saved), reply_markup=MENU_KEYBOARD)
    intervention = build_repeat_intervention(saved["analysis"]["distortion"])
    if intervention:
        await message.reply_text(intervention, reply_markup=MENU_KEYBOARD)


def schedule_jobs(application: Application) -> None:
    queue = application.job_queue
    if queue is None:
        return

    queue.run_daily(
        push_morning_reset,
        time=settings.parse_clock(settings.morning_reset_time),
        name="morning_reset",
    )
    queue.run_daily(
        push_evening_review,
        time=settings.parse_clock(settings.evening_review_time),
        name="evening_review",
    )
    queue.run_daily(
        push_weekly_review,
        time=settings.parse_clock(settings.weekly_review_time),
        days=(settings.weekly_review_day,),
        name="weekly_review",
    )
    queue.run_repeating(
        push_commitment_reminders,
        interval=3600,
        first=60,
        name="commitment_reminders",
    )


def build_application() -> Application:
    if not settings.telegram_enabled:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")

    application = Application.builder().token(settings.telegram_bot_token).post_init(post_init).build()
    schedule_jobs(application)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("menu", menu))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("patterns", patterns))
    application.add_handler(CommandHandler("weekly", weekly))
    application.add_handler(CommandHandler("day", day_status))
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(CommandHandler("commit", commit))
    application.add_handler(CommandHandler("commitments", commitments))
    application.add_handler(CommandHandler("done", done))
    application.add_handler(CommandHandler("move", move))
    application.add_handler(CommandHandler("pause", pause))
    application.add_handler(CommandHandler("resume", resume))
    application.add_handler(CallbackQueryHandler(handle_menu_callback, pattern=r"^menu:"))
    application.add_handler(CallbackQueryHandler(handle_commitment_callback, pattern=r"^commitment:"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return application


async def post_init(application: Application) -> None:
    await application.bot.set_my_commands(
        [
            BotCommand("menu", "Показать меню"),
            BotCommand("reset", "Daily reset"),
            BotCommand("commit", "Новое обязательство"),
            BotCommand("commitments", "Открытые обязательства"),
            BotCommand("day", "Статус дня"),
            BotCommand("weekly", "Недельная ревизия"),
            BotCommand("patterns", "Повторяющиеся паттерны"),
            BotCommand("status", "Статус бота"),
        ]
    )


def main() -> None:
    application = build_application()
    logger.info("Starting Telegram bot in polling mode")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
