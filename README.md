# Dasceq customer enquiry & appointment assistant

A small, ready-to-demo conversational assistant built with a static HTML/CSS/JavaScript frontend and FastAPI backend. It collects customer details, asks a purpose-specific follow-up, validates appointment preferences, and offers Google Calendar and `.ics` invites.

## Requirements

- Python 3.12
- A Groq API key for AI responses and hosted audio transcription
- A browser with microphone support for voice input (Chrome or Edge recommended)

## Run locally

From the project directory, create and activate a virtual environment, then install dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Add your Groq key to `.env`:

```text
GROQ_API_KEY=your_groq_api_key_here
```

The project includes `.env` and `.envsample`; keep real API keys in `.env`, which is git-ignored. `GROQ_MODEL` and `GROQ_TRANSCRIPTION_MODEL` can be changed there if you prefer other models available to your Groq account. If the key is blank, the appointment flow still works in demo mode with deterministic replies; AI chat and transcription require a key.

Start the app using the project entry point:

```powershell
python main.py
```

Or use `py main.py`. Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The API health check is at `/api/health`.

## Try it

With a Groq API key configured, customers can provide several details in one message or chat naturally while the assistant extracts and validates their name, phone, email, enquiry, a relevant follow-up, appointment date, and appointment time. The assistant asks for whatever is still missing, and only confirms when all required details are valid. Without a key, a guided step-by-step demo flow remains available. A successful booking displays a confirmation and calendar links. Conversations are temporary and stored only in server memory while the server is running; no database or permanent appointment storage is used. Start over to create a fresh conversation.

Select the microphone to record a voice message. The recording is sent to Groq's hosted Whisper transcription API—no speech-recognition model needs to be downloaded or installed. The assistant can also read responses aloud using the browser's built-in speech synthesis. Microphone access requires localhost or HTTPS. Transcription requires a Groq API key and is subject to your account's model access and usage limits.

## Project layout

```text
backend/
  app/
    api/
      routes.py               FastAPI endpoints
    core/
      config.py               Environment settings
    models/
      conversation.py         Conversation and appointment data models
    services/
      conversation_service.py Conversation flow and validation
      groq_service.py         Groq chat and transcription
      calendar_service.py     Calendar invite generation
    main.py                   FastAPI app setup
frontend/
  index.html      Chat interface
  styles.css      Responsive styling
  app.js          Chat, voice recording, speech, and calendar actions
main.py           Uvicorn entry point
requirements.txt
.env              Local configuration (git-ignored)
.envsample        Configuration template
```
