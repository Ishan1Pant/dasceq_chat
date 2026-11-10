import re
from datetime import date, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from backend.app.core.config import GROQ_API_KEY
from backend.app.models.conversation import Appointment, ConversationState
from backend.app.services import groq_service

FIELD_ORDER = ["purpose", "follow_up", "name", "phone", "email", "date", "time"]
CONVERSATIONS: dict[str, ConversationState] = {}


def new_conversation(customer_timezone: str) -> ConversationState:
    welcome = (
        "Hi! I'm your appointment assistant. I can help with customer enquiries "
        "and appointment bookings."
    )
    return ConversationState(
        timezone=customer_timezone,
        last_message=welcome,
        history=[{"role": "assistant", "content": welcome}],
    )


def next_question(step: str, follow_up_question: str | None) -> str:
    questions = {
        "purpose": "What can I help you with today? If you'd like an appointment, what would it be about?",
        "follow_up": follow_up_question
        or "Is there anything specific you'd like us to know before your appointment?",
        "name": "To get started, what's your full name?",
        "phone": "What's the best contact number to reach you?",
        "email": "What email address should we use for your confirmation?",
        "date": "What date would you prefer? Please use YYYY-MM-DD.",
        "time": "What time works best? For example, 2:30 PM or 14:30.",
    }
    return questions[step]


def validate_answer(
    step: str, message: str, customer_timezone: str
) -> tuple[str | None, str | None]:
    value = message.strip()
    if not value:
        return None, "I didn't catch that. Please try again."

    if step == "name":
        if len(value) < 2 or not any(character.isalpha() for character in value):
            return None, "Please enter your name using at least two characters."
    elif step == "phone":
        digits = re.sub(r"\D", "", value)
        if not 7 <= len(digits) <= 15:
            return None, "That number doesn't look right. Please enter 7–15 digits, including your country code if needed."
    elif step == "email":
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            return None, "That email address looks incomplete. Please enter it again (for example, name@example.com)."
    elif step == "purpose":
        if len(value) < 3:
            return None, "Could you add a little more detail about what you need help with?"
    elif step == "follow_up":
        if len(value) < 2:
            return None, "Please share a little more, or type “Nothing else” if there's nothing to add."
    elif step == "date":
        try:
            chosen_date = date.fromisoformat(value)
        except ValueError:
            return None, "Please enter the date as YYYY-MM-DD (for example, 2026-12-05)."
        if chosen_date < datetime.now(ZoneInfo(customer_timezone)).date():
            return None, "That date has already passed. Please choose a future date."
        value = chosen_date.isoformat()
    elif step == "time":
        parsed_time = None
        for pattern in ("%I:%M %p", "%I %p", "%H:%M"):
            try:
                parsed_time = datetime.strptime(value.upper(), pattern).time()
                break
            except ValueError:
                continue
        if parsed_time is None:
            return None, "Please enter a time like 2:30 PM or 14:30."
        value = parsed_time.strftime("%H:%M")

    return value, None


def conversation_response(
    conversation_id: str, state: ConversationState, message: str | None = None
) -> dict[str, object]:
    if message is None:
        message = state.last_message
    if not message and state.step == "name":
        message = (
            f"Hi! I'm your appointment assistant. "
            f"{next_question(state.step, state.follow_up_question)}"
        )
    return {
        "conversation_id": conversation_id,
        "message": message,
        "details": state.details,
        "step": state.step,
        "complete": state.step == "complete",
        "appointment": (
            vars(state.appointment) if state.appointment is not None else None
        ),
        "ai_enabled": bool(GROQ_API_KEY),
    }


def validation_response(
    conversation_id: str, state: ConversationState, error: str
) -> dict[str, object]:
    message = f"{error} {next_question(state.step, state.follow_up_question)}"
    return conversation_response(conversation_id, state, message)


async def advance_conversation(
    state: ConversationState, answer: str, original_message: str
) -> ConversationState:
    step = state.step
    details = {**state.details, step: answer}
    next_index = FIELD_ORDER.index(step) + 1
    next_step = FIELD_ORDER[next_index] if next_index < len(FIELD_ORDER) else "complete"
    follow_up_question = state.follow_up_question

    if step == "purpose":
        follow_up_question = await groq_service.create_follow_up_question(answer)
    reply = await groq_service.acknowledgement(step, original_message)

    appointment = state.appointment
    if next_step == "complete":
        appointment = Appointment(
            id=str(uuid4()),
            customer_name=details["name"],
            phone=details["phone"],
            email=details["email"],
            purpose=details["purpose"],
            follow_up=details["follow_up"],
            appointment_date=details["date"],
            appointment_time=details["time"],
            timezone=state.timezone,
        )
        formatted_date = date.fromisoformat(details["date"]).strftime(
            "%A, %B %d, %Y"
        ).replace(" 0", " ")
        formatted_time = datetime.strptime(details["time"], "%H:%M").strftime(
            "%I:%M %p"
        ).lstrip("0")
        reply = (
            f"{reply} Your appointment is confirmed for {formatted_date} at "
            f"{formatted_time} ({state.timezone}). You can review your details "
            "and add it to your calendar below."
        )
    else:
        reply = f"{reply} {next_question(next_step, follow_up_question)}"

    return ConversationState(
        timezone=state.timezone,
        step=next_step,
        details=details,
        follow_up_question=follow_up_question,
        appointment=appointment,
        last_message=reply,
        history=state.history
        + [
            {"role": "user", "content": original_message},
            {"role": "assistant", "content": reply},
        ],
    )


async def handle_message(state: ConversationState, message: str) -> ConversationState:
    if not GROQ_API_KEY:
        answer, error = validate_answer(state.step, message, state.timezone)
        if error:
            reply = f"{error} {next_question(state.step, state.follow_up_question)}"
            return ConversationState(
                timezone=state.timezone,
                step=state.step,
                details=state.details.copy(),
                follow_up_question=state.follow_up_question,
                last_message=reply,
                history=state.history
                + [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": reply},
                ],
            )
        return await advance_conversation(state, answer or "", message)

    history = state.history + [{"role": "user", "content": message}]
    extracted, model_next_step, model_reply = await groq_service.process_conversation_turn(
        state.history,
        message,
        state.details,
        datetime.now(ZoneInfo(state.timezone)).date().isoformat(),
        state.timezone,
        FIELD_ORDER,
    )

    details = state.details.copy()
    invalid_field = None
    validation_error = None
    for field_name in FIELD_ORDER:
        value = extracted[field_name]
        if value is None or not value.strip():
            continue
        normalized_value, error = validate_answer(
            field_name, value, state.timezone
        )
        if error:
            if invalid_field is None:
                invalid_field = field_name
                validation_error = error
            details.pop(field_name, None)
            continue
        details[field_name] = normalized_value or value.strip()

    if invalid_field is not None:
        next_step = invalid_field
        reply = f"{validation_error} {next_question(next_step, state.follow_up_question)}"
    else:
        next_step = next(
            (field_name for field_name in FIELD_ORDER if field_name not in details),
            "complete",
        )
        if next_step == "complete":
            reply = ""
        elif (
            model_next_step != next_step
            or not model_reply
            or "?" not in model_reply
        ):
            reply = await groq_service.revise_conversation_reply(
                state.history,
                message,
                details,
                next_step,
                model_reply,
                state.timezone,
            )
        else:
            reply = model_reply
        if next_step != "complete" and (
            "?" not in reply or len(reply) > 500
        ):
            raise HTTPException(
                status_code=502,
                detail="Groq returned an invalid conversational response. Please try again.",
            )

    appointment = state.appointment
    if next_step == "complete":
        appointment = Appointment(
            id=str(uuid4()),
            customer_name=details["name"],
            phone=details["phone"],
            email=details["email"],
            purpose=details["purpose"],
            follow_up=details["follow_up"],
            appointment_date=details["date"],
            appointment_time=details["time"],
            timezone=state.timezone,
        )
        formatted_date = date.fromisoformat(details["date"]).strftime(
            "%A, %B %d, %Y"
        ).replace(" 0", " ")
        formatted_time = datetime.strptime(details["time"], "%H:%M").strftime(
            "%I:%M %p"
        ).lstrip("0")
        reply = (
            f"Your appointment is confirmed for {formatted_date} at "
            f"{formatted_time} ({state.timezone}). You can review your details "
            "and add it to your calendar below."
        )

    return ConversationState(
        timezone=state.timezone,
        step=next_step,
        details=details,
        follow_up_question=state.follow_up_question,
        appointment=appointment,
        last_message=reply,
        history=history + [{"role": "assistant", "content": reply}],
    )
