# -------------------------------------------------
# services/llm.py
#
# This module handles the "intelligence" part:
# - It defines a DriverRequest data model (structured fields we need).
# - It talks to a local Ollama model (running at localhost:11434).
# - It extracts structured JSON from free-form driver requests.
#
# Ollama provides two endpoints:
#   - /api/chat: for structured chat messages (system/user roles).
#   - /api/generate: for plain prompts (legacy / fallback).
#
# In this file, we try /chat first, and if it fails, we fallback to /generate.
# -------------------------------------------------

import re
import requests
from pydantic import BaseModel, Field, ValidationError

# -------------------------------------------------
# DriverRequest model
# -------------------------------------------------
# This defines the structured output we want from the LLM.
# Pydantic is used here because:
#  - It validates fields automatically.
#  - It makes sure we get the correct data types (int, str, etc).
#
# Fields:
# - intent: what the user wants (find stops, trip overview, or service check).
# - category: type of stop (ev, gas, food, rest, service).
# - search_query: concise query to send to Google Places API.
# - after_minutes: optional; "find something after 30 minutes".
# - notes: free-form notes (optional).
# - num_results: how many results to return (default=4).
# -------------------------------------------------
class DriverRequest(BaseModel):
    intent: str = Field(description="find_stops | trip_overview | service_check")
    category: str = Field(description="ev | gas | food | rest | service")
    search_query: str = Field(description="Concise query for Google Places Text Search")
    after_minutes: int | None = Field(default=None, description="Prefer stops after this many minutes")
    notes: str | None = None
    num_results: int | None = Field(default=4)


# -------------------------------------------------
# Internal helper: call Ollama /api/chat
# -------------------------------------------------
# /api/chat accepts a list of messages with roles (system, user).
# Example:
#   [{"role": "system", "content": "You are helpful."},
#    {"role": "user", "content": "Hello!"}]
#
# We prefer /chat because it handles context and roles cleanly.
# -------------------------------------------------
def _ollama_chat(messages, model="llama3.2:3b", temperature=0.2) -> str:
    url = "http://localhost:11434/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,  # disable streaming, return whole output
        "options": {"temperature": temperature}
    }
    r = requests.post(url, json=payload, timeout=120)

    # If the endpoint is missing (older Ollama versions), raise so we can fallback.
    if r.status_code == 404:
        raise FileNotFoundError("chat-not-found")

    r.raise_for_status()
    return r.json()["message"]["content"]


# -------------------------------------------------
# Internal helper: call Ollama /api/generate
# -------------------------------------------------
# /api/generate is a simpler endpoint that just takes a single string prompt.
# We use it if /chat is not available.
# -------------------------------------------------
def _ollama_generate(prompt, model="llama3.2:3b", temperature=0.2) -> str:
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature}
    }
    r = requests.post(url, json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()

    # Ollama sometimes returns {"response": "..."} or nested message.
    return data.get("response") or data.get("message", {}).get("content", "")


# -------------------------------------------------
# call_ollama
# -------------------------------------------------
# This is the public function we use in the app.
# - It tries /chat first.
# - If /chat is missing or errors with 404/501, it falls back to /generate.
#
# For fallback, we concatenate system and user messages into one big prompt.
# -------------------------------------------------
def call_ollama(messages, model="llama3.2:3b", temperature=0.2) -> str:
    """Try /api/chat first, then fallback to /api/generate."""
    try:
        return _ollama_chat(messages, model, temperature)
    except (FileNotFoundError, requests.HTTPError) as e:
        # If /chat fails with 404 (not found) or 501 (not implemented),
        # we reformat messages into a plain prompt and call /generate instead.
        status = getattr(e, "response", None).status_code if hasattr(e, "response") and e.response else None
        if isinstance(e, FileNotFoundError) or status in (404, 501):
            system = "\n".join(m["content"] for m in messages if m["role"] == "system")
            user = "\n".join(m["content"] for m in messages if m["role"] == "user")
            prompt = (system + "\n\n" + user).strip()
            return _ollama_generate(prompt, model, temperature)
        raise


# -------------------------------------------------
# extract_intent
# -------------------------------------------------
# This is the MAIN entry point for the rest of the app.
# - Takes the user’s free text (or speech transcript) + context (EV/Gas, prefs).
# - Asks the LLM to produce STRICT JSON only.
# - Uses regex to extract the JSON block from the model’s response.
# - Validates it into our DriverRequest model.
# - If parsing fails, falls back to a safe default (EV or Gas station).
#
# Example user_text: "Find me a charger after 30 minutes"
# → DriverRequest(intent="find_stops", category="ev", search_query="EV charging station", after_minutes=30)
# -------------------------------------------------
def extract_intent(user_text: str, energy_mode: str, fast: bool, scenic: bool, family: bool) -> DriverRequest:
    # System instruction: tells the model how to behave and what format to use.
    system = (
        "You are a driving concierge. Convert the user's request into STRICT JSON. "
        "Rules: intent=find_stops for any request to locate stops; category in {ev, gas, food, rest, service}. "
        "search_query must be short (e.g., 'EV charging station', 'gas station', 'coffee', 'playground'). "
        "If they say 'after X minutes', set after_minutes. Output JSON only, no prose."
    )

    # User content: includes the raw request + context (energy mode + preferences).
    user = f"""
User said: {user_text}

Context:
- Energy mode: {energy_mode}
- Prefs: fast={fast}, scenic={scenic}, family={family}

Return JSON exactly with keys: intent, category, search_query, after_minutes, notes, num_results.
"""

    # Call Ollama with both system + user messages.
    raw = call_ollama(
        [{"role": "system", "content": system},
         {"role": "user", "content": user}]
    )

    # Extract the JSON object from the raw string (model might wrap in ```).
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    js = m.group(0) if m else "{}"

    # Validate against our DriverRequest model.
    try:
        return DriverRequest.model_validate_json(js)
    except ValidationError:
        # If the model output was invalid or empty,
        # fall back to a safe default request so the app doesn’t crash.
        return DriverRequest(
            intent="find_stops",
            category="ev" if energy_mode.lower().startswith("ev") else "gas",
            search_query="EV charging station" if energy_mode.lower().startswith("ev") else "gas station",
            after_minutes=None,
            notes=None,
            num_results=4
        )
