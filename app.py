# ---------------------------------------------
# app.py — Streamlit entry point (FREE STACK)
#
# What this file does:
# - Renders the UI (sidebar + main area)
# - Captures voice or typed input
# - Auto-fills the text input with the latest transcript
# - Calls the local LLM (via services.llm) to extract intent
# - Calls Google Routes + Places helpers (via services.maps)
# - Speaks back a summary (browser TTS) and shows a map with pins
#
# Directory modules used:
# - utils.settings:        loads GOOGLE_MAPS_API_KEY from .env
# - services.stt:          transcribe_audio() using faster-whisper
# - services.llm:          extract_intent() using Ollama
# - services.maps:         compute_route_polyline(), places_along_route()
# - ui.tts_browser:        speak_text() to speak with browser TTS
# - ui.maps_embed:         render_map() to embed Google Map with route + pins
# ---------------------------------------------

import streamlit as st
import hashlib, uuid

# Pull configuration and helper functions from our modules
from utils.settings import GOOGLE_MAPS_API_KEY
from services.maps import compute_route_polyline, places_along_route
from services.stt import transcribe_audio
from services.llm import extract_intent
from ui.maps_embed import render_map
from ui.tts_browser import speak_text

# ------------------------------
# Session state bootstrapping
# ------------------------------
# Streamlit re-runs the script top-to-bottom on each interaction.
# session_state lets us persist values between runs (like memory).
# We define keys we’ll use and give them defaults if missing.

if "user_query" not in st.session_state:
    # The canonical text for the user’s request (typed or transcribed)
    st.session_state.user_query = ""

if "last_audio_hash" not in st.session_state:
    # Hash of the last audio blob we processed (so we don’t re-transcribe the same clip)
    st.session_state.last_audio_hash = None

if "pending_user_query" not in st.session_state:
    # A temporary place to store the next value for the text box, which we apply BEFORE the widget renders
    st.session_state.pending_user_query = None

if "speak_queue" not in st.session_state:
    st.session_state.speak_queue = None

if "speak_nonce" not in st.session_state:
    st.session_state.speak_nonce = None

# If a previous run prepared a new text value (from voice), apply it now
# Doing this BEFORE creating the text_input widget avoids the
# “cannot modify session_state after widget is instantiated” error.
if st.session_state.pending_user_query is not None:
    st.session_state.user_query = st.session_state.pending_user_query
    st.session_state.pending_user_query = None

# ------------------------------
# Page header / metadata
# ------------------------------
# Configure the Streamlit page and show a title/subtitle.
st.set_page_config(page_title="Driving Concierge (Free Stack)", layout="wide")
st.title("🚗 AI Driving Concierge — Free Stack")
st.caption("Local LLM (Ollama) + Whisper (faster-whisper) + Browser TTS")

# ------------------------------
# Sidebar – Trip setup & prefs
# ------------------------------
# The sidebar collects user context (origin/destination, vehicle, preferences).
# This data influences the LLM planning and the Places search.
with st.sidebar:
    st.header("Trip Setup")

    # Freeform addresses/cities work; Google Routes will geocode them.
    origin = st.text_input("Origin", value="Iasi, Romania")
    destination = st.text_input("Destination", value="Athens, Greece")

    # Vehicle info helps pick category (EV vs gas) and future range logic.
    st.markdown("**Vehicle**")
    energy_mode = st.selectbox("Energy", ["EV", "Gasoline"], index=0)
    est_range_km = st.number_input("Estimated range (km)", min_value=50, max_value=1200, value=300, step=10)
    buffer_pct = st.slider("Reserve buffer (%)", min_value=5, max_value=30, value=15, step=5)

    # Preferences shape the search query (e.g., scenic/family)
    st.markdown("**Driver preferences**")
    fast = st.checkbox("Fast trip (min detour)", value=True)
    scenic = st.checkbox("Scenic")
    family = st.checkbox("Family-friendly")
    max_results = st.slider("Max stops to show", 1, 8, 4)

# ------------------------------
# Main area – Left/Right columns
# ------------------------------
# Left: input (voice/typed) and Go button.
# Right: the map render after results are ready.
left, right = st.columns([1, 1])

with left:
    st.subheader("🎙️ Speak or type your request")

    # Toggle to automatically fill the text box with the latest voice transcript.
    auto_fill = st.checkbox(
        "Auto-fill from microphone",
        value=True,
        help="Transcribe the latest recording into the text box automatically."
    )

    # Choose how new transcripts should interact with existing text.
    fill_mode = st.radio("When filling", ["Replace text", "Append to text"], horizontal=True)

    # 1) Render the microphone widget first.
    # After the user records and releases, Streamlit provides the audio blob.
    audio_file = st.audio_input("Press to record, then release", help="Your browser will ask for mic permission.")

    # 2) If we have a new recording AND auto-fill is on, transcribe it.
    # We hash the raw bytes to detect if it’s a brand-new clip.
    if auto_fill and audio_file is not None:
        audio_bytes = audio_file.getvalue()
        audio_hash = hashlib.sha1(audio_bytes).hexdigest()

        if audio_hash != st.session_state.last_audio_hash:
            # New audio detected → run STT (speech-to-text)
            try:
                # Note: we import from our services module (faster-whisper under the hood)
                from services.stt import transcribe_audio
                transcript = transcribe_audio(audio_file)
            except Exception as e:
                st.warning(f"Transcription error: {e}")
                transcript = ""

            # If STT produced text, decide how to insert it.
            if transcript:
                if fill_mode == "Replace text" or not st.session_state.user_query:
                    new_text = transcript
                else:
                    # Append with a space if needed
                    sep = "" if st.session_state.user_query.endswith((" ", "")) else " "
                    new_text = st.session_state.user_query + sep + transcript

                # IMPORTANT: We do NOT set st.session_state.user_query directly now,
                # because the text_input widget doesn’t exist yet in this run.
                # Instead, we stash it in 'pending_user_query' and force a rerun.
                st.session_state.pending_user_query = new_text
                st.session_state.last_audio_hash = audio_hash

                # Rerun so the next run can apply 'pending_user_query' BEFORE the widget renders.
                st.rerun()

    # 3) Render the text input AFTER the above logic.
    # It will read the current st.session_state.user_query as its initial value.
    text_fallback = st.text_input(
        "Or type instead",
        key="user_query",  # links the widget to st.session_state["user_query"]
        placeholder="e.g., find a fast charger 30 minutes from now"
    )

# Primary action button. When pressed, we read the final text and start the pipeline.
go = st.button("Go", type="primary", use_container_width=True)

# ------------------------------
# Action: run the planner + map
# ------------------------------
if go:
    # 1) Finalize the user request. Prefer the text box; if empty, try transcribing the current clip once more.
    user_text = (st.session_state.user_query or "").strip()
    if not user_text:
        user_text = transcribe_audio(audio_file)  # fallback if someone only used mic with auto-fill off
    if not user_text:
        st.warning("Say something or type a request.")
        st.stop()

    # 2) Plan via the local LLM (Ollama).
    # This turns the free-form request into structured JSON: {intent, category, search_query, after_minutes, ...}
    plan = extract_intent(user_text, energy_mode, fast, scenic, family)

    # 3) Build a concrete Places text query from the plan + user prefs.
    if plan.category == "ev":
        default_query = "EV charging station"
    elif plan.category == "gas":
        default_query = "gas station"
    else:
        default_query = plan.search_query or "rest stop"

    # Use the plan’s query if present, otherwise fall back to our defaults.
    text_query = plan.search_query or default_query

    # Light “profile” nudges: for family/scenic food/rest requests, bias the query terms.
    if family and plan.category in ("food", "rest"):
        text_query += " playground OR family friendly"
    if scenic and plan.category in ("food", "rest"):
        text_query += " scenic view"

    # 4) Get the route polyline from Google Routes (encodes the path on the map).
    try:
        route = compute_route_polyline(origin, destination)
    except Exception as e:
        st.error(f"Route error: {e}")
        st.stop()

    # ...then find relevant places **along that route** using Places “Text Search (New)”.
    try:
        results = places_along_route(route["polyline"], text_query, limit=max_results * 2)
    except Exception as e:
        st.error(f"Places error: {e}")
        st.stop()

    # 5) Optional light filtering: for EV/Gas we can prefer stops after N minutes (if the user asked).
    filtered = results
    if plan.category in ("ev", "gas"):
        def ok(r):
            if plan.after_minutes is None:
                return True
            # detour_s is origin→place travel time from routing summaries.
            # We treat it as “minutes into the trip” (good heuristic for hackathons).
            mins = (r.get("detour_s") or 0) / 60
            return mins >= plan.after_minutes

        filtered = [r for r in results if ok(r)]

    # Show at most max_results to keep the UI clean.
    top = filtered[:max_results] if filtered else results[:max_results]

    # 6) Create a concise spoken summary and speak it with the browser’s SpeechSynthesis.
    if top:
        lines = []
        for i, r in enumerate(top, 1):
            mins = int(round((r.get("detour_s") or 0) / 60))
            lines.append(f"{i}. {r['name']} — ~{mins} min detour; {r['address']}")
        summary_text = f"I found {len(top)} result(s) for “{text_query}” along your route. \n" + "\n".join(lines[:3])
    else:
        summary_text = f"I couldn't find good matches for “{text_query}” on your route."

    st.success(summary_text)
    # Queue speech for this run only
    st.session_state.speak_queue = summary_text
    st.session_state.speak_nonce = str(uuid.uuid4())  # Browser TTS (no API key needed)

    # 7) Finally, render the interactive map (route polyline + markers with info windows).
    with right:
        st.subheader("🗺️ Map")
        if not GOOGLE_MAPS_API_KEY:
            st.error("Missing GOOGLE_MAPS_API_KEY in .env")
        else:
            # render_map() embeds a Google Map and draws the route + pins.
            render_map(GOOGLE_MAPS_API_KEY, route["polyline"], top)

# Speak once per submission; will NOT re-speak on page refresh
if st.session_state.speak_queue and st.session_state.speak_nonce:
    speak_text(st.session_state.speak_queue, st.session_state.speak_nonce)
    # clear queue so subsequent reruns (and refresh) won’t speak
    st.session_state.speak_queue = None
    st.session_state.speak_nonce = None
