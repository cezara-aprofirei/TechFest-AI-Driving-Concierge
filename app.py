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
import pydeck as pdk
import pandas as pd
import hashlib, uuid

# Pull configuration and helper functions from our modules
from utils.settings import GOOGLE_MAPS_API_KEY
from services.maps import compute_route_polyline, places_along_route
from services.stt import transcribe_audio
from services.llm import extract_intent
from ui.maps_embed import render_map
from ui.tts_browser import speak_text

st.set_page_config(page_title="In-Car Navigation UI", layout="wide", initial_sidebar_state="collapsed")

# --- States ---
if "mode" not in st.session_state:
    st.session_state.mode = "map"   # "map" or "advanced"

if "is_loading" not in st.session_state:
    st.session_state.is_loading = False

if "user_query" not in st.session_state:
    # The canonical text for the user’s request (typed or transcribed)
    st.session_state.user_query = ""

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

# --- Helpers ---
def set_mode(new_mode: str):
    st.session_state.mode = new_mode

def set_route_loading(new__is_loading: str):
    st.session_state.is_loading = new__is_loading

def set_user_query(new_query: str):
    st.session_state.user_query = new_query

def set_speak_queue(new_text: str):
    st.session_state.speak_queue = new_text

def set_speak_nonce(new_nonce: str):
    st.session_state.speak_nonce = new_nonce

def set_pending_user_query(new_text: str):
    st.session_state.pending_user_query = new_text

# --- Global CSS: zero padding, no scroll, exact-fit rows ---
st.markdown(
    """
    <style>
      /* Ensure all sizing includes borders/padding */
      *, *::before, *::after { box-sizing: border-box; }

      /* Kill scroll and gutters everywhere */
      html, body { height: 100vh; overflow: hidden; padding: 0 !important; margin: 0 !important; }
      [data-testid="stAppViewContainer"] { height: 100vh; overflow: hidden; padding: 0 !important; margin: 0 !important; }
      [data-testid="stMainBlockContainer"],
      .stMainBlockContainer,
      .stMainBlockContainer.block-container,
      .main .block-container,
      section.main > div.block-container { padding: 0 !important; margin: 0 !important; max-width: 100% !important; }

      /* Header/toolbar must be removed from layout (visibility keeps the gap) */
      [data-testid="stHeader"], header, [data-testid="stToolbar"] { display: none !important; height: 0 !important; padding: 0 !important; margin: 0 !important; }
      footer { display: none !important; }

      /* Tweak Streamlit column wrappers to participate in full-height flex */
      [data-testid="stHorizontalBlock"] { height: 100%; margin: 0 !important; }
      [data-testid="stHorizontalBlock"] > div { height: 100%; }
      [data-testid="column"] { display: flex; }
      [data-testid="column"] > div { flex: 1 1 auto; display: flex; flex-direction: column; min-height: 0; }

      /* Controls look */
      .stButton > button { height: 3rem; border-radius: 16px; font-size: 1.05rem; font-weight: 600; }
      .stTextInput > div > div > input { font-size: 1.05rem; height: 3rem; }

      /* Layout variables */
      :root {
        --row-top: 12vh;
        --row-bot: 12vh;
        --gapX: 1rem;
        --panel-radius: 16px;
      }
      @media (max-width: 1199.98px) {
        :root { --row-top: 14vh; --row-bot: 14vh; --gapX: 0.75rem; }
      }
      @media (max-width: 767.98px) {
        :root { --row-top: 16vh; --row-bot: 16vh; --gapX: 0.5rem; }
      }

      /* TOP row: fixed height, no outer margins */
      div[data-testid="stVerticalBlock"]:has(> div:has(> .top-row-hook)) {
          height: var(--row-top);
          background: #0f172a10;
          border-radius: var(--panel-radius);
          padding: 0.5rem;
          display: flex; flex-direction: column; justify-content: center;
          margin: 0 !important;
      }

      /* MIDDLE wrapper exact height = 100vh - (top + bottom) */
      .middle-row {
          height: calc(100vh - var(--row-top) - var(--row-bot));
          display: flex; gap: var(--gapX);
          padding: 0 var(--gapX);
          margin: 0 !important;
      }

      /* LEFT panel: 100% height */
      div[data-testid="stVerticalBlock"]:has(> div:has(> .left-panel-hook)) {
          height: 100%;
          background: #0f172a10;
          border-radius: var(--panel-radius);
          padding: 0.75rem;
          display: flex; flex-direction: column; min-height: 0;
      }
      /* MODES fills all available height inside left panel */
      div[data-testid="stVerticalBlock"]:has(> div:has(> .modes-hook)) {
          flex: 1 1 auto; display: flex; flex-direction: column; justify-content: center; min-height: 0;
      }
      /* ACTIONS stays at the bottom */
      div[data-testid="stVerticalBlock"]:has(> div:has(> .actions-hook)) { flex: 0 0 auto; margin-top: 0.5rem; }

      /* RIGHT panel: 100% height; internal sections constrained */
      div[data-testid="stVerticalBlock"]:has(> div:has(> .main-panel-hook)) {
          height: 100%;
          background: #0f172a08;
          border-radius: var(--panel-radius);
          padding: 0.5rem;
          display: flex; flex-direction: column; gap: 0.5rem;
          min-width: 0; min-height: 0; overflow: hidden;
      }
      /* PARAMS auto-height */
      div[data-testid="stVerticalBlock"]:has(> div:has(> .params-hook)) { flex: 0 0 auto; }
      /* MAP takes the rest */
      div[data-testid="stVerticalBlock"]:has(> div:has(> .map-hook)) { flex: 1 1 auto; display: flex; flex-direction: column; min-height: 0; }
      [data-testid="stDeckGlJsonChart"] { flex: 1; min-height: 0; }

      /* BOTTOM row: fixed height, no margins */
      div[data-testid="stVerticalBlock"]:has(> div:has(> .bottom-row-hook)) {
          height: var(--row-bot);
          background: #0f172a10;
          border-radius: var(--panel-radius);
          padding: 0.5rem;
          display: flex; flex-direction: column; justify-content: center;
          margin: 0 !important;
      }
      .bottom-row { display: flex; justify-content: center; width: 100%; gap: 0.5rem; }
      .bottom-row .stButton { margin: 0 0.35rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- TOP ROW ---
top_row = st.container(border=True)
with top_row:
    st.markdown('<span class="top-row-hook"></span>', unsafe_allow_html=True)
    padL, c1, c2, padR = st.columns([1, 3, 3, 1])
    with c1:
        origin = st.text_input("Origin", placeholder="Enter origin…", key="origin")
    with c2:
        destination = st.text_input("Destination", placeholder="Enter destination…", key="destination")

# --- MIDDLE ROW ---
side_col, main_col = st.columns([1, 3], gap="large")

# LEFT PANEL (Modes 100% height, Actions at bottom)
with side_col:
    left_panel = st.container(border=True)
    with left_panel:
        st.markdown('<span class="left-panel-hook"></span>', unsafe_allow_html=True)

        modes_box = st.container()
        with modes_box:
            st.markdown('<span class="modes-hook"></span>', unsafe_allow_html=True)
            st.markdown("#### Modes")
            st.button("Simple Recommendations", use_container_width=True, on_click=set_mode, args=("map",))
            st.button("Advanced Recommendations", use_container_width=True, on_click=set_mode, args=("advanced",))

# RIGHT PANEL (swaps content, fills height)
with main_col:
    main_panel = st.container(border=True)
    with main_panel:
        st.markdown('<span class="main-panel-hook"></span>', unsafe_allow_html=True)

        # -------- Simple Map mode integration here --------
        if st.session_state.mode == "map":
            map_box = st.container()
            with map_box:
                st.markdown('<span class="map-hook"></span>', unsafe_allow_html=True)
                st.markdown("**Map**")
                
        else:
            params_box = st.container()
            with params_box:
                left_params, right_params = st.columns([1, 1])
                with left_params:
                    st.markdown("**🎙️ Speak or type your request**")
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

                with right_params:
                    # Vehicle info helps pick category (EV vs gas) and future range logic.
                    st.markdown("**Vehicle**")
                    energy_mode = st.selectbox("Energy", ["EV", "Gasoline"], index=0)
                    max_results = st.slider("Max stops to show", 1, 8, 4)
                    # Preferences shape the search query (e.g., scenic/family)
                    st.markdown("**Driver preferences**")
                    fast = st.checkbox("Fast trip (min detour)", value=True)
                    scenic = st.checkbox("Scenic")
                    family = st.checkbox("Family-friendly")

        

                # Primary action button. When pressed, we read the final text and start the pipeline.
                go = st.button(
                    "Go",
                    type="primary",
                    use_container_width=True,
                    disabled=st.session_state.is_loading  # disable if loading
                )

            # ------------------------------
            # Action: run the planner + map
            # ------------------------------
            if go:
                # create a status panel with live updates
                status = st.status("Starting...", expanded=False)

                try:
                    st.session_state.is_loading = True  # disable button until done
                    status.update(label="🧠 Understanding your request...", state="running")
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
                    status.update(label="🗺️ Calculating route...", state="running")
                    try:
                        route = compute_route_polyline(origin, destination)
                    except Exception as e:
                        st.error(f"Route error: {e}")
                        st.stop()

                    # ...then find relevant places **along that route** using Places “Text Search (New)”.
                    status.update(label="📍 Searching places along your route...", state="running")
                    try:
                        results = places_along_route(route["polyline"], text_query, limit=max_results * 2)
                    except Exception as e:
                        st.error(f"Places error: {e}")
                        st.stop()

                    status.update(label="✨ Preparing results...", state="running")

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
                    
                    if not GOOGLE_MAPS_API_KEY:
                        st.error("Missing GOOGLE_MAPS_API_KEY in .env")
                    else:
                        # render_map() embeds a Google Map and draws the route + pins.
                        render_map(GOOGLE_MAPS_API_KEY, route["polyline"], top)
                    
                    status.update(label="✅ Done", state="complete")
                
                except Exception as e:
                    status.update(label=f"❌ Error: {e}", state="error")
                    st.stop()
                finally:
                    st.session_state.is_loading = False  # re-enable button

# --- BOTTOM ROW ---
bottom_row = st.container(border=True)
with bottom_row:
    st.markdown('<span class="bottom-row-hook"></span>', unsafe_allow_html=True)
    st.markdown('<div class="bottom-row">', unsafe_allow_html=True)
    s1, cA, cB, cC, cD, cE, s2 = st.columns([1, 1.2, 1.2, 1.2, 1.2, 1.2, 1], gap="large")
    with cA: st.button("🎤  Mic", use_container_width=True)
    with cB: st.button("Temperature", use_container_width=True)
    with cC: st.button("Fan Speed", use_container_width=True)
    with cD: st.button("Steering wheel", use_container_width=True)
    with cE: st.button("Seat Heating", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# Speak once per submission; will NOT re-speak on page refresh
if st.session_state.speak_queue and st.session_state.speak_nonce:
    speak_text(st.session_state.speak_queue, st.session_state.speak_nonce)
    # clear queue so subsequent reruns (and refresh) won’t speak
    st.session_state.speak_queue = None
    st.session_state.speak_nonce = None