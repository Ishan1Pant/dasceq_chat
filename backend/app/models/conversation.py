from dataclasses import dataclass, field

from pydantic import BaseModel, Field


class ConversationStart(BaseModel):
    timezone: str = "UTC"


class MessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


@dataclass
class Appointment:
    id: str
    customer_name: str
    phone: str
    email: str
    purpose: str
    follow_up: str
    appointment_date: str
    appointment_time: str
    timezone: str


@dataclass
class ConversationState:
    timezone: str
    step: str = "purpose"
    details: dict[str, str] = field(default_factory=dict)
    follow_up_question: str | None = None
    appointment: Appointment | None = None
    last_message: str = ""
    history: list[dict[str, str]] = field(default_factory=list)
