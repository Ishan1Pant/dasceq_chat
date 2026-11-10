const messagesElement = document.querySelector("#messages");
const composer = document.querySelector("#composer");
const input = document.querySelector("#message-input");
const sendButton = document.querySelector("#send-button");
const typingIndicator = document.querySelector("#typing");
const errorBanner = document.querySelector("#error-banner");
const confirmation = document.querySelector("#confirmation");
const progressBar = document.querySelector("#progress-bar");
const stepLabel = document.querySelector("#step-label");
const stepCount = document.querySelector("#step-count");
const statusLabel = document.querySelector("#status-label");
const recordButton = document.querySelector("#record-button");
const soundToggle = document.querySelector("#sound-toggle");

const fieldLabels = {
  name: "GETTING STARTED",
  phone: "CONTACT DETAILS",
  email: "CONTACT DETAILS",
  purpose: "YOUR ENQUIRY",
  follow_up: "A LITTLE MORE DETAIL",
  date: "PICK A DATE",
  time: "PICK A TIME",
  complete: "APPOINTMENT CONFIRMED",
};
const fieldCount = 7;
let conversationId = null;
let currentStep = "name";
let isSending = false;
let mediaRecorder = null;
let recordingStream = null;
let recordedChunks = [];
let voiceRepliesEnabled = true;

function setBusy(busy) {
  isSending = busy;
  sendButton.disabled = busy || !input.value.trim() || currentStep === "complete";
  input.disabled = busy || currentStep === "complete";
  recordButton.disabled = busy || currentStep === "complete";
  typingIndicator.hidden = !busy;
  if (busy) {
    statusLabel.textContent = "Typing…";
  } else if (currentStep !== "complete") {
    statusLabel.textContent = "Ready to help";
  }
}

function showError(message) {
  errorBanner.textContent = message;
  errorBanner.hidden = false;
}

function clearError() {
  errorBanner.hidden = true;
  errorBanner.textContent = "";
}

function appendMessage(text, sender) {
  const row = document.createElement("div");
  row.className = `message-row ${sender}`;
  if (sender === "assistant") {
    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = "d";
    row.append(avatar);
  }
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  row.append(bubble);
  messagesElement.append(row);
  messagesElement.scrollTop = messagesElement.scrollHeight;
}

function formatDate(value) {
  const [year, month, day] = value.split("-").map(Number);
  return new Intl.DateTimeFormat(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(new Date(year, month - 1, day));
}

function formatTime(value) {
  const [hour, minute] = value.split(":").map(Number);
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(2020, 0, 1, hour, minute));
}

function updateProgress(step) {
  currentStep = step;
  const index = ["name", "phone", "email", "purpose", "follow_up", "date", "time"].indexOf(step);
  const completed = step === "complete" ? fieldCount : Math.max(0, index);
  progressBar.style.width = `${(completed / fieldCount) * 100}%`;
  stepLabel.textContent = fieldLabels[step] || "YOUR ENQUIRY";
  stepCount.textContent = step === "complete" ? "Done" : `${Math.min(completed + 1, fieldCount)} of ${fieldCount}`;
  if (step === "complete") {
    statusLabel.textContent = "Appointment confirmed";
    input.placeholder = "Your appointment is confirmed";
    input.disabled = true;
    sendButton.disabled = true;
    recordButton.disabled = true;
  }
}

function appendConfirmation(details, appointment, id) {
  confirmation.replaceChildren();
  const title = document.createElement("div");
  title.className = "confirmation-title";
  const check = document.createElement("span");
  check.className = "checkmark";
  check.textContent = "✓";
  const heading = document.createElement("span");
  heading.textContent = "Appointment details";
  title.append(check, heading);

  const grid = document.createElement("div");
  grid.className = "details-grid";
  const entries = [
    ["Name", details.name, ""],
    ["Phone", details.phone, ""],
    ["Email", details.email, "full"],
    ["Enquiry", details.purpose, "full"],
    ["Appointment", `${formatDate(details.date)} · ${formatTime(details.time)} (${appointment.timezone})`, "full"],
  ];
  for (const [label, value, extraClass] of entries) {
    const item = document.createElement("div");
    item.className = `detail-item ${extraClass}`.trim();
    const labelElement = document.createElement("span");
    labelElement.className = "detail-label";
    labelElement.textContent = label;
    const valueElement = document.createElement("span");
    valueElement.className = "detail-value";
    valueElement.textContent = value;
    item.append(labelElement, valueElement);
    grid.append(item);
  }

  const actions = document.createElement("div");
  actions.className = "calendar-actions";
  const downloadLink = document.createElement("a");
  downloadLink.href = `/api/conversations/${encodeURIComponent(id)}/calendar`;
  downloadLink.textContent = "Download calendar invite";
  downloadLink.setAttribute("download", "appointment.ics");
  const googleLink = document.createElement("a");
  googleLink.href = `/api/conversations/${encodeURIComponent(id)}/google-calendar`;
  googleLink.target = "_blank";
  googleLink.rel = "noopener noreferrer";
  googleLink.textContent = "Add to Google Calendar";
  googleLink.addEventListener("click", async (event) => {
    event.preventDefault();
    try {
      const response = await fetch(googleLink.href);
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "Couldn't create the calendar link.");
      window.open(body.url, "_blank", "noopener,noreferrer");
    } catch (error) {
      showError(error.message);
    }
  });
  actions.append(downloadLink, googleLink);
  confirmation.append(title, grid, actions);
  confirmation.hidden = false;
}

function speak(text) {
  if (!voiceRepliesEnabled || !("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1;
  window.speechSynthesis.speak(utterance);
}

async function beginConversation() {
  clearError();
  messagesElement.replaceChildren();
  confirmation.hidden = true;
  confirmation.replaceChildren();
  progressBar.style.width = "0%";
  setBusy(true);
  try {
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
    const response = await fetch("/api/conversations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ timezone }),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "Couldn't start a conversation.");
    conversationId = body.conversation_id;
    updateProgress(body.step);
    appendMessage(body.message, "assistant");
    statusLabel.textContent = body.ai_enabled ? "Groq AI · ready to help" : "Demo mode · ready to help";
    if (!body.ai_enabled) statusLabel.title = "Add your Groq API key to .env to enable AI chat and voice transcription.";
  } catch (error) {
    showError(error.message);
    statusLabel.textContent = "Connection issue";
  } finally {
    setBusy(false);
    input.focus();
  }
}

async function sendMessage(message) {
  if (!message.trim() || !conversationId || isSending) return;
  clearError();
  appendMessage(message.trim(), "user");
  input.value = "";
  input.style.height = "auto";
  setBusy(true);
  try {
    const response = await fetch(`/api/conversations/${encodeURIComponent(conversationId)}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: message.trim() }),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "Couldn't send your message.");
    updateProgress(body.step);
    appendMessage(body.message, "assistant");
    speak(body.message);
    if (body.complete && body.appointment) {
      appendConfirmation(body.details, body.appointment, conversationId);
      input.blur();
    }
  } catch (error) {
    showError(error.message);
    appendMessage("I couldn't send that just now. Please try again.", "assistant");
  } finally {
    setBusy(false);
    if (currentStep !== "complete") input.focus();
  }
}

async function toggleRecording() {
  clearError();
  if (mediaRecorder?.state === "recording") {
    mediaRecorder.stop();
    recordButton.classList.remove("recording");
    recordButton.setAttribute("aria-label", "Record a voice message");
    recordButton.title = "Record a voice message";
    return;
  }

  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    showError("Audio recording isn't supported in this browser. Try a current version of Chrome or Edge.");
    return;
  }
  try {
    recordingStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recordedChunks = [];
    mediaRecorder = new MediaRecorder(recordingStream);
    mediaRecorder.addEventListener("dataavailable", (event) => {
      if (event.data.size) recordedChunks.push(event.data);
    });
    mediaRecorder.addEventListener("stop", async () => {
      recordingStream?.getTracks().forEach((track) => track.stop());
      recordingStream = null;
      const recording = new Blob(recordedChunks, { type: mediaRecorder.mimeType || "audio/webm" });
      if (!recording.size) {
        showError("No audio was recorded. Please try again.");
        return;
      }
      const formData = new FormData();
      const extension = recording.type.includes("mp4") ? "mp4" : recording.type.includes("ogg") ? "ogg" : "webm";
      formData.append("audio", recording, `voice-message.${extension}`);
      setBusy(true);
      try {
        const response = await fetch("/api/transcribe", { method: "POST", body: formData });
        const body = await response.json();
        if (!response.ok) throw new Error(body.detail || "Couldn't transcribe that recording.");
        input.value = body.text;
        input.dispatchEvent(new Event("input"));
        input.focus();
      } catch (error) {
        showError(error.message);
      } finally {
        setBusy(false);
      }
    }, { once: true });
    mediaRecorder.start();
    recordButton.classList.add("recording");
    recordButton.setAttribute("aria-label", "Stop recording");
    recordButton.title = "Stop recording";
    statusLabel.textContent = "Recording… select the microphone to stop";
  } catch (error) {
    showError(error.name === "NotAllowedError"
      ? "Microphone access was denied. Allow microphone access in your browser and try again."
      : "Couldn't start recording. Check your microphone and try again.");
  }
}

composer.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage(input.value);
});

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 100)}px`;
  sendButton.disabled = isSending || !input.value.trim() || currentStep === "complete";
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    composer.requestSubmit();
  }
});

recordButton.addEventListener("click", toggleRecording);
document.querySelector("#new-chat").addEventListener("click", beginConversation);
soundToggle.addEventListener("click", () => {
  voiceRepliesEnabled = !voiceRepliesEnabled;
  soundToggle.setAttribute("aria-pressed", String(!voiceRepliesEnabled));
  soundToggle.setAttribute("aria-label", `Turn voice replies ${voiceRepliesEnabled ? "off" : "on"}`);
  if (!voiceRepliesEnabled && "speechSynthesis" in window) window.speechSynthesis.cancel();
});
document.querySelector("#voice-help").addEventListener("click", () => {
  showError("Select the microphone, allow access, and speak. Groq’s hosted Whisper API transcribes your recording—no speech model is installed on your computer.");
  window.setTimeout(clearError, 7000);
});

beginConversation();
