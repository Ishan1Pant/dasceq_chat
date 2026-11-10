from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from backend.app.core.config import GROQ_API_KEY, MAX_AUDIO_BYTES
from backend.app.models.conversation import ConversationStart, MessageRequest
from backend.app.services import calendar_service, conversation_service, groq_service

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str | bool]:
    return {"status": "ok", "ai_enabled": bool(GROQ_API_KEY)}


@router.post("/conversations")
def start_conversation(payload: ConversationStart) -> dict[str, object]:
    try:
        ZoneInfo(payload.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(status_code=400, detail="Please use a valid timezone.") from None

    conversation_id = str(uuid4())
    state = conversation_service.new_conversation(payload.timezone)
    conversation_service.CONVERSATIONS[conversation_id] = state
    return conversation_service.conversation_response(conversation_id, state)


@router.post("/conversations/{conversation_id}/messages")
async def send_message(conversation_id: str, payload: MessageRequest) -> dict[str, object]:
    state = conversation_service.CONVERSATIONS.get(conversation_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found. Start a new conversation and try again.",
        )
    if state.step == "complete":
        return conversation_service.conversation_response(
            conversation_id,
            state,
            "This appointment is already confirmed. Start over to schedule another.",
        )

    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Please enter a message.")
    next_state = await conversation_service.handle_message(state, message)
    conversation_service.CONVERSATIONS[conversation_id] = next_state
    return conversation_service.conversation_response(conversation_id, next_state)


@router.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)) -> dict[str, str]:
    if not GROQ_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Voice transcription needs a Groq API key. Add it to the GROQ_API_KEY setting in .env.",
        )
    if not audio.filename:
        raise HTTPException(status_code=400, detail="Please record or select an audio file.")

    content = await audio.read(MAX_AUDIO_BYTES + 1)
    if len(content) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio must be smaller than 20 MB.")
    if not content:
        raise HTTPException(status_code=400, detail="The audio recording is empty.")
    return {"text": await groq_service.transcribe(content, audio.filename, audio.content_type)}


@router.get("/conversations/{conversation_id}/calendar")
def download_calendar_event(conversation_id: str) -> Response:
    state = conversation_service.CONVERSATIONS.get(conversation_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    if state.appointment is None:
        raise HTTPException(status_code=409, detail="Confirm the appointment before downloading it.")
    return calendar_service.calendar_file(state.appointment)


@router.get("/conversations/{conversation_id}/google-calendar")
def google_calendar_link(conversation_id: str) -> dict[str, str]:
    state = conversation_service.CONVERSATIONS.get(conversation_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    if state.appointment is None:
        raise HTTPException(status_code=409, detail="Confirm the appointment before adding it to a calendar.")
    return {"url": calendar_service.google_calendar_url(state.appointment)}
