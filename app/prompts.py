INTAKE_INSTRUCTIONS = """
Ты модуль управленческой диагностики.
Нужно разобрать запись пользователя и вернуть строго JSON по схеме.
Не пиши лишний текст, не добавляй markdown.
Тон спокойный, прямой, без мотивационного мусора.
"""

INTAKE_USER_TEMPLATE = """
Проанализируй запись пользователя.

Запись:
{entry_text}

Разбери:
1. Тип записи: task | problem | anxiety | plan | reflection
2. Контур: operational | managerial | architectural
3. Ролевая оценка: executor | manager | mixed
4. Искажение:
   rescuer_mode | hypercontrol | delegation_avoidance | false_urgency | boundary_failure | not_detected
5. Что должен сделать пользователь:
   do | delegate | delay | delete | process | discuss
6. strict_action: короткое жесткое действие в одном предложении
7. reasoning: короткое объяснение, без воды
"""

WEEKLY_REVIEW_INSTRUCTIONS = """
Ты проводишь недельную управленческую ревизию.
Используй записи пользователя за неделю и верни строго JSON по схеме.
Покажи конкретные повторы и последствия, без общих слов.
"""

WEEKLY_REVIEW_USER_TEMPLATE = """
Вот записи и их разбор за неделю:
{entries_blob}

Сформируй:
1. management_ratio: число от 0 до 1
2. delegation_score: число от 0 до 1
3. rescue_events: целое число
4. top_pattern: короткая метка главного повторяющегося паттерна
5. next_week_rule: одно жесткое правило на следующую неделю
6. summary: короткий вывод на 2-4 предложения
"""

