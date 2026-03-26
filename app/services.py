from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from json import dumps
from typing import Any

from . import db
from . import llm_service
from .schemas import AnalysisResult, DailyResetResponse, WeeklyReviewResponse


OPERATIONAL_MARKERS = {
    "срочно",
    "быстро",
    "сам",
    "руками",
    "проверить",
    "исправить",
    "ответить",
    "потушить",
    "разобраться",
    "переделать",
}

MANAGERIAL_MARKERS = {
    "делег",
    "owner",
    "владелец",
    "приоритет",
    "решение",
    "команда",
    "1:1",
    "контекст",
    "критерии",
}

ARCHITECTURAL_MARKERS = {
    "процесс",
    "система",
    "узкое место",
    "регламент",
    "автоматиз",
    "шаблон",
    "метрика",
}

ANXIETY_MARKERS = {"боюсь", "трев", "перегруз", "не успеваю", "хаос", "страшно"}
PLAN_MARKERS = {"сегодня", "план", "неделя", "хочу", "надо", "сделаю"}
REFLECTION_MARKERS = {"понял", "заметил", "опять", "сорвался", "рефлексия", "вывод"}
VAGUE_TASK_MARKERS = {"сделать", "поработать", "посмотреть", "разобраться", "подумать", "заняться", "проверить"}
VAGUE_RESULT_MARKERS = {"нормально", "как-нибудь", "по возможности", "если успею", "готово", "ок"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _contains_any(text: str, markers: set[str]) -> bool:
    return any(marker in text for marker in markers)


def _parse_deadline(deadline_text: str) -> datetime:
    cleaned = deadline_text.strip()
    try:
        return datetime.strptime(cleaned, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValueError("Срок должен быть в формате YYYY-MM-DD HH:MM, например 2026-03-28 16:00") from exc


def _deadline_to_display(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def evaluate_commitment_quality(text: str, deadline_text: str, definition_of_done: str) -> dict[str, Any]:
    lowered_text = text.lower().strip()
    lowered_dod = definition_of_done.lower().strip()
    comments = []

    if len(text.strip()) < 12:
        comments.append("Формулировка задачи слишком короткая. Нужен конкретный результат, а не ярлык.")
    if any(marker in lowered_text for marker in VAGUE_TASK_MARKERS):
        comments.append("В задаче слишком размытый глагол. Лучше описать измеримый результат.")
    if "до" in lowered_text and any(word in lowered_text for word in ("пятницы", "вечера", "конца дня")):
        comments.append("Не прячь срок в тексте задачи. Срок должен жить отдельным точным полем.")
    if len(definition_of_done.strip()) < 12:
        comments.append("Definition of done слишком короткий. Нужен критерий, по которому можно сказать 'готово'.")
    if any(marker in lowered_dod for marker in VAGUE_RESULT_MARKERS):
        comments.append("Критерий готовности размыт. Укажи, что именно должно быть отправлено, согласовано или опубликовано.")

    deadline_dt = _parse_deadline(deadline_text)
    if deadline_dt <= now_dt():
        comments.append("Срок уже в прошлом. Нужен будущий дедлайн.")
    if deadline_dt - now_dt() < timedelta(minutes=30):
        comments.append("Срок слишком близко. Это больше похоже на тревожную срочность, чем на нормальное планирование.")

    if not comments:
        quality_comment = "Формулировка нормальная: есть конкретный срок и критерий готовности."
        quality_score = 3
    elif len(comments) == 1:
        quality_comment = comments[0]
        quality_score = 2
    else:
        quality_comment = " ".join(comments)
        quality_score = 1

    return {
        "deadline_dt": deadline_dt,
        "quality_score": quality_score,
        "quality_comment": quality_comment,
    }


def analyze_entry(text: str) -> AnalysisResult:
    lowered = text.lower()

    if _contains_any(lowered, ANXIETY_MARKERS):
        entry_type = "anxiety"
    elif _contains_any(lowered, REFLECTION_MARKERS):
        entry_type = "reflection"
    elif _contains_any(lowered, PLAN_MARKERS):
        entry_type = "plan"
    elif "?" in lowered or "проблем" in lowered:
        entry_type = "problem"
    else:
        entry_type = "task"

    operational_hits = sum(marker in lowered for marker in OPERATIONAL_MARKERS)
    managerial_hits = sum(marker in lowered for marker in MANAGERIAL_MARKERS)
    architectural_hits = sum(marker in lowered for marker in ARCHITECTURAL_MARKERS)

    if architectural_hits >= max(operational_hits, managerial_hits) and architectural_hits > 0:
        contour = "architectural"
    elif managerial_hits >= operational_hits and managerial_hits > 0:
        contour = "managerial"
    else:
        contour = "operational"

    if contour == "operational" and operational_hits >= 2:
        role_verdict = "executor"
    elif contour == "managerial":
        role_verdict = "manager"
    else:
        role_verdict = "mixed"

    if "сам" in lowered or "руками" in lowered:
        distortion = "rescuer_mode"
    elif "провер" in lowered or "контрол" in lowered:
        distortion = "hypercontrol"
    elif "делег" not in lowered and contour == "operational":
        distortion = "delegation_avoidance"
    elif "срочно" in lowered:
        distortion = "false_urgency"
    elif "перегруз" in lowered or "хаос" in lowered:
        distortion = "boundary_failure"
    else:
        distortion = "not_detected"

    if contour == "managerial":
        recommended_action = "do"
        strict_action = "Зафиксируй owner, критерий результата и срок."
    elif contour == "architectural":
        recommended_action = "process"
        strict_action = "Не туши симптом, опиши правило или процесс."
    elif distortion in {"rescuer_mode", "hypercontrol", "delegation_avoidance"}:
        recommended_action = "delegate"
        strict_action = "Не делай это сам. Назначь владельца и критерий приемки."
    elif distortion == "false_urgency":
        recommended_action = "delay"
        strict_action = "Остановись на 15 минут и перепроверь, что реально горит."
    else:
        recommended_action = "discuss"
        strict_action = "Сначала уточни контекст и только потом бери задачу."

    reasoning = (
        f"Контур={contour}. Роль={role_verdict}. "
        f"Сигнал искажения={distortion}. Система видит риск скатиться в операционку."
    )

    return AnalysisResult(
        entry_type=entry_type,
        contour=contour,
        role_verdict=role_verdict,
        distortion=distortion,
        recommended_action=recommended_action,
        strict_action=strict_action,
        reasoning=reasoning,
    )


def save_capture(text: str, source: str) -> dict[str, Any]:
    created_at = now_iso()
    try:
        analysis = llm_service.analyze_entry(text)
    except Exception:
        analysis = analyze_entry(text)
    entry_id = db.insert_and_return_id(
        """
        INSERT INTO entries (text, source, created_at, entry_type, contour, raw_payload)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (text, source, created_at, analysis.entry_type, analysis.contour, "{}"),
    )
    db.insert_and_return_id(
        """
        INSERT INTO analyses (
            entry_id, role_verdict, distortion, recommended_action, strict_action, reasoning, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entry_id,
            analysis.role_verdict,
            analysis.distortion,
            analysis.recommended_action,
            analysis.strict_action,
            analysis.reasoning,
            created_at,
        ),
    )
    return {"entry_id": entry_id, "analysis": analysis.model_dump()}


def create_commitment(text: str, due_date: str, definition_of_done: str) -> dict[str, Any]:
    quality = evaluate_commitment_quality(text, due_date, definition_of_done)
    created_at = now_iso()
    commitment_id = db.insert_and_return_id(
        """
        INSERT INTO commitments (
            text, status, due_date, broken_count, created_at, definition_of_done, quality_comment, updated_at
        )
        VALUES (?, 'open', ?, 0, ?, ?, ?, ?)
        """,
        (
            text.strip(),
            quality["deadline_dt"].isoformat(),
            created_at,
            definition_of_done.strip(),
            quality["quality_comment"],
            created_at,
        ),
    )
    return {
        "id": commitment_id,
        "text": text.strip(),
        "due_date": quality["deadline_dt"].isoformat(),
        "definition_of_done": definition_of_done.strip(),
        "status": "open",
        "quality_comment": quality["quality_comment"],
        "quality_score": quality["quality_score"],
    }


def list_commitments(status: str = "open", limit: int = 10) -> list[dict[str, Any]]:
    rows = db.fetch_all(
        """
        SELECT id, text, status, due_date, broken_count, created_at, definition_of_done, quality_comment, updated_at
        FROM commitments
        WHERE status = ?
        ORDER BY due_date ASC
        LIMIT ?
        """,
        (status, limit),
    )
    now = now_dt()
    for row in rows:
        due_dt = datetime.fromisoformat(row["due_date"])
        if row["status"] == "open" and due_dt < now:
            row["deadline_state"] = "overdue"
        elif row["status"] == "open" and due_dt - now <= timedelta(hours=6):
            row["deadline_state"] = "due_soon"
        else:
            row["deadline_state"] = "planned"
    return rows


def get_commitment(commitment_id: int) -> dict[str, Any] | None:
    return db.fetch_one(
        """
        SELECT id, text, status, due_date, broken_count, created_at, definition_of_done, quality_comment, updated_at
        FROM commitments
        WHERE id = ?
        """,
        (commitment_id,),
    )


def mark_commitment_done(commitment_id: int) -> dict[str, Any]:
    existing = get_commitment(commitment_id)
    if not existing:
        raise ValueError("Commitment not found")
    db.execute(
        "UPDATE commitments SET status = 'done', updated_at = ? WHERE id = ?",
        (now_iso(), commitment_id),
    )
    existing["status"] = "done"
    return existing


def move_commitment(commitment_id: int, new_due_date: str) -> dict[str, Any]:
    existing = get_commitment(commitment_id)
    if not existing:
        raise ValueError("Commitment not found")
    quality = evaluate_commitment_quality(existing["text"], new_due_date, existing.get("definition_of_done") or "")
    db.execute(
        """
        UPDATE commitments
        SET due_date = ?, broken_count = broken_count + 1, quality_comment = ?, updated_at = ?
        WHERE id = ?
        """,
        (quality["deadline_dt"].isoformat(), quality["quality_comment"], now_iso(), commitment_id),
    )
    updated = get_commitment(commitment_id)
    updated["quality_score"] = quality["quality_score"]
    return updated


def mark_commitment_broken(commitment_id: int) -> dict[str, Any]:
    existing = get_commitment(commitment_id)
    if not existing:
        raise ValueError("Commitment not found")
    db.execute(
        """
        UPDATE commitments
        SET status = 'broken', broken_count = broken_count + 1, updated_at = ?
        WHERE id = ?
        """,
        (now_iso(), commitment_id),
    )
    broken = get_commitment(commitment_id)
    return broken


def upsert_telegram_chat(chat_id: int, username: str | None, first_name: str | None) -> None:
    existing = db.fetch_one("SELECT id FROM telegram_chats WHERE chat_id = ?", (chat_id,))
    created_at = now_iso()
    if existing:
        db.execute(
            """
            UPDATE telegram_chats
            SET username = ?, first_name = ?, is_active = 1, updated_at = ?
            WHERE chat_id = ?
            """,
            (username, first_name, created_at, chat_id),
        )
        return

    db.insert_and_return_id(
        """
        INSERT INTO telegram_chats (chat_id, username, first_name, is_active, created_at, updated_at)
        VALUES (?, ?, ?, 1, ?, ?)
        """,
        (chat_id, username, first_name, created_at, created_at),
    )


def set_telegram_chat_active(chat_id: int, is_active: bool) -> None:
    db.execute(
        "UPDATE telegram_chats SET is_active = ?, updated_at = ? WHERE chat_id = ?",
        (1 if is_active else 0, now_iso(), chat_id),
    )


def list_active_telegram_chats() -> list[dict[str, Any]]:
    return db.fetch_all(
        """
        SELECT chat_id, username, first_name
        FROM telegram_chats
        WHERE is_active = 1
        ORDER BY updated_at DESC
        """
    )


def run_daily_reset(impact_focus: str, operational_risk: str, managerial_action: str) -> DailyResetResponse:
    score = 0
    lowered = " ".join([impact_focus, operational_risk, managerial_action]).lower()
    if any(word in impact_focus.lower() for word in ("результат", "приоритет", "выруч", "цель", "команда")):
        score += 1
    if any(word in operational_risk.lower() for word in ("влезть", "сам", "провер", "потуш", "руками")):
        score += 1
    if any(word in managerial_action.lower() for word in ("делег", "решение", "owner", "1:1", "приоритет")):
        score += 1

    if score <= 1:
        role_risk = "Высокий риск исполнительского дня."
    elif score == 2:
        role_risk = "День смешанный: без границ снова утянет в операционку."
    else:
        role_risk = "Каркас управленческого дня есть, но его нужно удержать."

    if "сам" in lowered or "руками" in lowered:
        distortion = "Ты снова ставишь личное участие выше системы."
    elif "срочно" in lowered:
        distortion = "Ты называешь срочным то, что требует приоритизации."
    else:
        distortion = "Главный риск дня: размытые границы роли."

    if "делег" in managerial_action.lower():
        hard_boundary = "Запрещено самому перепроверять то, что уже делегировано."
    else:
        hard_boundary = "Запрещено брать новые ручные задачи до одного управленческого действия."

    must_do_today = managerial_action.strip().rstrip(".") + "."

    payload = {
        "impact_focus": impact_focus,
        "operational_risk": operational_risk,
        "managerial_action": managerial_action,
        "score": score,
        "role_risk": role_risk,
    }
    db.insert_ritual_log("daily_reset", payload, now_iso())
    return DailyResetResponse(
        score=score,
        role_risk=role_risk,
        distortion=distortion,
        hard_boundary=hard_boundary,
        must_do_today=must_do_today,
    )


def get_patterns(limit: int = 5) -> list[dict[str, Any]]:
    rows = db.fetch_all(
        """
        SELECT a.distortion, a.role_verdict, e.text, e.created_at
        FROM analyses a
        JOIN entries e ON e.id = a.entry_id
        ORDER BY e.created_at DESC
        LIMIT 50
        """
    )
    counter = Counter(row["distortion"] for row in rows if row["distortion"] != "not_detected")
    patterns = []
    for label, frequency in counter.most_common(limit):
        latest = next((row for row in rows if row["distortion"] == label), None)
        patterns.append(
            {
                "label": label,
                "frequency": frequency,
                "last_seen": latest["created_at"] if latest else None,
                "example": latest["text"] if latest else "",
            }
        )
    return patterns


def run_weekly_review() -> dict[str, Any]:
    since_dt = datetime.now(timezone.utc) - timedelta(days=7)
    since = since_dt.isoformat()
    rows = db.fetch_all(
        """
        SELECT e.text, e.entry_type, e.contour, e.created_at,
               a.role_verdict, a.distortion, a.recommended_action
        FROM entries e
        JOIN analyses a ON a.entry_id = e.id
        WHERE e.created_at >= ?
        ORDER BY e.created_at DESC
        """,
        (since,),
    )
    total = len(rows) or 1
    managerial_count = sum(1 for row in rows if row["role_verdict"] == "manager")
    delegation_score = sum(1 for row in rows if row["recommended_action"] == "delegate") / total
    rescue_events = sum(1 for row in rows if row["distortion"] in {"rescuer_mode", "hypercontrol"})
    top_pattern = get_patterns(limit=1)
    top_pattern_label = top_pattern[0]["label"] if top_pattern else "not_detected"
    management_ratio = managerial_count / total
    week_start = since_dt.date().isoformat()

    entries_blob = "\n\n".join(
        (
            f"[{row['created_at']}] text={row['text']} | contour={row['contour']} | "
            f"role={row['role_verdict']} | distortion={row['distortion']} | "
            f"action={row['recommended_action']}"
        )
        for row in rows
    ) or "Нет записей за неделю."

    try:
        review_model = llm_service.weekly_review(
            entries_blob=entries_blob,
            week_start=week_start,
            entries_reviewed=len(rows),
        )
    except Exception:
        if top_pattern_label in {"rescuer_mode", "hypercontrol"}:
            next_week_rule = "Не исправлять руками задачи команды без явного запроса и критерия приемки."
        elif top_pattern_label == "delegation_avoidance":
            next_week_rule = "Каждую новую операционную задачу сначала пытаться делегировать."
        else:
            next_week_rule = "Каждый день начинать с одного управленческого действия до операционки."

        summary = (
            f"Управленческих записей: {managerial_count} из {total}. "
            f"Повторяющийся паттерн: {top_pattern_label}. "
            f"Событий спасательства: {rescue_events}. "
            f"Правило на неделю: {next_week_rule}"
        )
        review_model = WeeklyReviewResponse(
            week_start=week_start,
            management_ratio=round(management_ratio, 2),
            delegation_score=round(delegation_score, 2),
            rescue_events=rescue_events,
            top_pattern=top_pattern_label,
            next_week_rule=next_week_rule,
            summary=summary,
            entries_reviewed=len(rows),
        )

    db.insert_and_return_id(
        """
        INSERT INTO weekly_reviews (
            week_start, management_ratio, delegation_score, rescue_events,
            top_pattern, next_week_rule, summary, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            review_model.week_start,
            review_model.management_ratio,
            review_model.delegation_score,
            review_model.rescue_events,
            review_model.top_pattern,
            review_model.next_week_rule,
            review_model.summary,
            now_iso(),
        ),
    )
    return review_model.model_dump()


def list_recent_entries(limit: int = 10) -> list[dict[str, Any]]:
    return db.fetch_all(
        """
        SELECT e.id, e.text, e.entry_type, e.contour, e.created_at,
               a.role_verdict, a.distortion, a.recommended_action
        FROM entries e
        JOIN analyses a ON a.entry_id = e.id
        ORDER BY e.created_at DESC
        LIMIT ?
        """,
        (limit,),
    )


def format_analysis_message(saved: dict[str, Any]) -> str:
    analysis = saved["analysis"]
    return (
        f"Запись #{saved['entry_id']}\n"
        f"Тип: {analysis['entry_type']}\n"
        f"Контур: {analysis['contour']}\n"
        f"Роль: {analysis['role_verdict']}\n"
        f"Искажение: {analysis['distortion']}\n"
        f"Рекомендация: {analysis['recommended_action']}\n"
        f"Жесткое действие: {analysis['strict_action']}\n"
        f"Почему: {analysis['reasoning']}"
    )


def format_patterns_message(limit: int = 5) -> str:
    patterns = get_patterns(limit=limit)
    if not patterns:
        return "Паттерны еще не накопились."

    lines = ["Повторяющиеся паттерны:"]
    for pattern in patterns:
        lines.append(
            f"- {pattern['label']} x{pattern['frequency']} | пример: {pattern['example']}"
        )
    return "\n".join(lines)


def format_weekly_review_message() -> str:
    review = run_weekly_review()
    return (
        f"Недельная ревизия\n"
        f"Период с: {review['week_start']}\n"
        f"Management ratio: {review['management_ratio']}\n"
        f"Delegation score: {review['delegation_score']}\n"
        f"Rescue events: {review['rescue_events']}\n"
        f"Top pattern: {review['top_pattern']}\n"
        f"Rule: {review['next_week_rule']}\n"
        f"Summary: {review['summary']}"
    )


def format_commitments_message(status: str = "open") -> str:
    items = list_commitments(status=status, limit=20)
    if not items:
        return "Открытых обязательств пока нет."

    lines = ["Обязательства:"]
    for item in items:
        due_dt = datetime.fromisoformat(item["due_date"])
        lines.append(
            f"#{item['id']} [{item['deadline_state']}] до {_deadline_to_display(due_dt)}\n"
            f"{item['text']}\n"
            f"DoD: {item.get('definition_of_done') or '-'}"
        )
    return "\n\n".join(lines)


def format_single_commitment_message(item: dict[str, Any]) -> str:
    due_dt = datetime.fromisoformat(item["due_date"])
    return (
        f"#{item['id']} [{item.get('deadline_state', 'planned')}] до {_deadline_to_display(due_dt)}\n"
        f"{item['text']}\n"
        f"DoD: {item.get('definition_of_done') or '-'}\n"
        f"Качество: {item.get('quality_comment') or '-'}"
    )


def format_commitment_created_message(commitment: dict[str, Any]) -> str:
    due_dt = datetime.fromisoformat(commitment["due_date"])
    return (
        f"Обязательство #{commitment['id']} зафиксировано.\n"
        f"Срок: {_deadline_to_display(due_dt)}\n"
        f"Результат: {commitment['text']}\n"
        f"DoD: {commitment['definition_of_done']}\n"
        f"Оценка качества: {commitment['quality_comment']}"
    )


def format_commitment_done_message(commitment: dict[str, Any]) -> str:
    return f"Обязательство #{commitment['id']} отмечено как done."


def format_commitment_moved_message(commitment: dict[str, Any]) -> str:
    due_dt = datetime.fromisoformat(commitment["due_date"])
    return (
        f"Обязательство #{commitment['id']} перенесено.\n"
        f"Новый срок: {_deadline_to_display(due_dt)}\n"
        f"Комментарий: {commitment['quality_comment']}"
    )


def format_deadline_help() -> str:
    return (
        "Формат срока только такой: YYYY-MM-DD HH:MM\n"
        "Пример: 2026-03-28 16:00\n"
        "Не пиши 'к пятнице', 'до вечера' или 'как получится'."
    )


def build_repeat_intervention(distortion: str) -> str | None:
    recent = db.fetch_all(
        """
        SELECT a.distortion, e.text, e.created_at
        FROM analyses a
        JOIN entries e ON e.id = a.entry_id
        WHERE e.created_at >= datetime('now', '-7 day')
        ORDER BY e.created_at DESC
        LIMIT 10
        """
    )
    repeated_count = sum(1 for row in recent if row["distortion"] == distortion)
    if distortion == "not_detected" or repeated_count < 3:
        return None

    cause_map = {
        "rescuer_mode": "Ты снова делаешь ставку на незаменимость вместо системы.",
        "hypercontrol": "Ты снова путаешь контроль качества с личным участием.",
        "delegation_avoidance": "Ты снова обходишь делегирование и платишь за это своим фокусом.",
        "false_urgency": "Ты снова называешь срочным то, что требует приоритизации.",
        "boundary_failure": "У тебя снова текут границы, поэтому день собирается вокруг чужих задач.",
    }
    ban_map = {
        "rescuer_mode": "Запрет: не исправлять руками чужую работу сегодня.",
        "hypercontrol": "Запрет: не перепроверять вручную то, где уже есть владелец.",
        "delegation_avoidance": "Запрет: не брать новую операционную задачу без попытки делегирования.",
        "false_urgency": "Запрет: не отвечать на новую срочность без 10 минут паузы.",
        "boundary_failure": "Запрет: не открывать новые мелкие задачи до главного управленческого решения.",
    }
    return (
        f"Интервенция\n"
        f"Паттерн повторился {repeated_count} раз за 7 дней.\n"
        f"{cause_map.get(distortion, 'Ты снова повторяешь знакомый откат.')}\n"
        f"{ban_map.get(distortion, 'Нужна жесткая граница на сегодня.')}"
    )


def _reminder_already_sent(commitment_id: int, reminder_kind: str, bucket: str) -> bool:
    row = db.fetch_one(
        """
        SELECT id
        FROM ritual_logs
        WHERE ritual_type = 'commitment_reminder'
          AND payload = ?
        LIMIT 1
        """,
        (dumps({"commitment_id": commitment_id, "kind": reminder_kind, "bucket": bucket}, ensure_ascii=True),),
    )
    return row is not None


def _mark_reminder_sent(commitment_id: int, reminder_kind: str, bucket: str) -> None:
    db.insert_ritual_log(
        "commitment_reminder",
        {"commitment_id": commitment_id, "kind": reminder_kind, "bucket": bucket},
        now_iso(),
    )


def get_due_commitment_reminders() -> list[str]:
    reminders = []
    now = now_dt()
    open_items = list_commitments(status="open", limit=50)
    for item in open_items:
        due_dt = datetime.fromisoformat(item["due_date"])
        delta = due_dt - now
        if timedelta(hours=0) <= delta <= timedelta(hours=2):
            bucket = now.strftime("%Y-%m-%dT%H")
            if not _reminder_already_sent(item["id"], "due_soon", bucket):
                reminders.append(
                    f"Дедлайн рядом: обязательство #{item['id']} до {_deadline_to_display(due_dt)}.\n"
                    f"{item['text']}\n"
                    f"DoD: {item.get('definition_of_done') or '-'}"
                )
                _mark_reminder_sent(item["id"], "due_soon", bucket)
        elif delta < timedelta(0):
            bucket = now.strftime("%Y-%m-%d")
            if not _reminder_already_sent(item["id"], "overdue", bucket):
                reminders.append(
                    f"Срок сорван: обязательство #{item['id']} должно было быть готово к {_deadline_to_display(due_dt)}.\n"
                    f"{item['text']}\n"
                    "Отметь /done ID или перенеси через /move ID."
                )
                _mark_reminder_sent(item["id"], "overdue", bucket)
    return reminders


def has_daily_reset_today() -> bool:
    today = datetime.now(timezone.utc).date().isoformat()
    row = db.fetch_one(
        """
        SELECT id
        FROM ritual_logs
        WHERE ritual_type = 'daily_reset' AND substr(created_at, 1, 10) = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (today,),
    )
    return row is not None


def build_morning_reminder() -> str:
    if has_daily_reset_today():
        return (
            "Утренний check.\n"
            "Ты уже прошел daily reset сегодня. Не размывай день новыми ручными задачами раньше управленческого действия."
        )
    return (
        "Утренний reset обязателен.\n"
        "1. Что сегодня реально влияет на результат?\n"
        "2. Где ты рискуешь снова влезть в операционку?\n"
        "3. Какое одно управленческое действие обязательно сегодня?\n"
        "Ответь командой /reset."
    )


def build_evening_reminder() -> str:
    patterns = get_patterns(limit=1)
    top = patterns[0]["label"] if patterns else "not_detected"
    if has_daily_reset_today():
        return (
            "Вечерний check.\n"
            f"Главный текущий паттерн: {top}.\n"
            "Зафиксируй: где ты удержал роль, а где снова полез руками."
        )
    return (
        "Вечерний check.\n"
        "Сегодня день прошел без daily reset. Система помечает это как день без управления.\n"
        "Минимум на сейчас: зафиксируй один откат и одно управленческое решение на завтра."
    )


def get_day_management_status() -> dict[str, Any]:
    today = datetime.now(timezone.utc).date().isoformat()
    reset_done = has_daily_reset_today()
    entries = db.fetch_all(
        """
        SELECT a.role_verdict, a.distortion
        FROM analyses a
        JOIN entries e ON e.id = a.entry_id
        WHERE substr(e.created_at, 1, 10) = ?
        """,
        (today,),
    )
    managers = sum(1 for row in entries if row["role_verdict"] == "manager")
    executors = sum(1 for row in entries if row["role_verdict"] == "executor")
    rescue_events = sum(1 for row in entries if row["distortion"] in {"rescuer_mode", "hypercontrol"})

    if reset_done and managers >= executors:
        status = "with_management"
        label = "День с управлением"
        comment = "Есть daily reset и пока управленческие действия не проигрывают операционке."
    elif reset_done:
        status = "at_risk"
        label = "День под риском"
        comment = "Reset есть, но операционка пока тянет тебя сильнее управленческого слоя."
    else:
        status = "without_management"
        label = "День без управления"
        comment = "Daily reset не пройден. Система считает, что день начался без управленческого каркаса."

    return {
        "date": today,
        "status": status,
        "label": label,
        "comment": comment,
        "reset_done": reset_done,
        "manager_entries": managers,
        "executor_entries": executors,
        "rescue_events": rescue_events,
    }


def format_day_status_message() -> str:
    payload = get_day_management_status()
    return (
        f"{payload['label']}\n"
        f"Дата: {payload['date']}\n"
        f"Reset: {'done' if payload['reset_done'] else 'missed'}\n"
        f"Manager entries: {payload['manager_entries']}\n"
        f"Executor entries: {payload['executor_entries']}\n"
        f"Rescue events: {payload['rescue_events']}\n"
        f"Комментарий: {payload['comment']}"
    )
