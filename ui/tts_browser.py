# -------------------------------------------------
# ui/tts_browser.py
#
# Purpose:
# - Make the assistant "speak" back to the driver by using
#   the browser’s built-in Web Speech API (`speechSynthesis`).
#
# Why do this in the browser?
# - Free (no API calls or keys needed).
# - Instant response (no network latency).
# - Works in most modern browsers (Chrome, Edge, Safari).
#
# How we avoid re-speaking on refresh:
# - We use a `nonce` (unique token generated for each new message).
# - The nonce is stored in `sessionStorage` in the browser tab.
# - If the same nonce is seen again (e.g., on refresh), we skip speaking.
# -------------------------------------------------

import streamlit as st
import json


def speak_text(text: str, nonce: str):
    """
    Speak the given `text` exactly once per unique `nonce`.

    Parameters:
      - text: the message to read out loud.
      - nonce: a unique identifier (e.g., uuid4 string) created
               in app.py each time a new message is generated.

    Flow:
      1. Python builds a small HTML+JS snippet and embeds it in the app.
      2. JavaScript checks sessionStorage for 'spokenNonce'.
      3. If the stored value matches the current nonce → do nothing.
      4. If it's new → use speechSynthesis to speak and update sessionStorage.
    """

    st.components.v1.html(f"""
<div></div>
<script>
  (function() {{
    // Values injected from Python
    const text = {json.dumps(text)};
    const nonce = {json.dumps(nonce)};

    try {{
      // Key where we store the last spoken nonce in this browser tab
      const key = "spokenNonce";
      const prev = sessionStorage.getItem(key);

      // If we've already spoken this message (same nonce), do nothing
      if (prev === nonce) return;

      // Cancel any ongoing speech (so repeats don’t overlap)
      window.speechSynthesis.cancel();

      // Create a new utterance with the text
      const u = new SpeechSynthesisUtterance(text);

      // Speak it out loud
      window.speechSynthesis.speak(u);

      // Remember that we’ve already spoken this nonce
      sessionStorage.setItem(key, nonce);
    }} catch (e) {{
      // Some browsers may block autoplay or throw errors
      // We silently ignore so the app doesn’t crash
    }}
  }})();
</script>
""", height=0)
