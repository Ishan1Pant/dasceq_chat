from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi.responses import Response

from backend.app.models.conversation import Appointment


def escape_ical(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def calendar_file(appointment: Appointment) -> Response:
    local_start = datetime.combine(
        date.fromisoformat(appointment.appointment_date),
        time.fromisoformat(appointment.appointment_time),
        tzinfo=ZoneInfo(appointment.timezone),
    )
    utc_start = local_start.astimezone(timezone.utc)
    utc_end = (local_start + timedelta(hours=1)).astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Dasceq//Appointment Assistant//EN",
        "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT",
        f"UID:{appointment.id}@dasceq-chat",
        f"DTSTAMP:{now.strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART:{utc_start.strftime('%Y%m%dT%H%M%SZ')}",
        f"DTEND:{utc_end.strftime('%Y%m%dT%H%M%SZ')}",
        f"SUMMARY:{escape_ical('Appointment: ' + appointment.customer_name)}",
        f"DESCRIPTION:{escape_ical(appointment.purpose + ' — ' + appointment.follow_up)}",
        "END:VEVENT",
        "END:VCALENDAR",
        "",
    ]
    return Response(
        content="\r\n".join(lines),
        media_type="text/calendar",
        headers={"Content-Disposition": 'attachment; filename="appointment.ics"'},
    )


def google_calendar_url(appointment: Appointment) -> str:
    local_start = datetime.combine(
        date.fromisoformat(appointment.appointment_date),
        time.fromisoformat(appointment.appointment_time),
        tzinfo=ZoneInfo(appointment.timezone),
    )
    local_end = local_start + timedelta(hours=1)
    params = {
        "action": "TEMPLATE",
        "text": f"Appointment: {appointment.customer_name}",
        "dates": f"{local_start:%Y%m%dT%H%M%S}/{local_end:%Y%m%dT%H%M%S}",
        "ctz": appointment.timezone,
        "details": f"{appointment.purpose}\n{appointment.follow_up}",
    }
    query = "&".join(f"{key}={quote(value)}" for key, value in params.items())
    return f"https://calendar.google.com/calendar/render?{query}"
