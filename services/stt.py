# -------------------------------------------------
# services/stt.py
#
# This module handles **Speech-to-Text (STT)**.
# It uses the open-source `faster-whisper` library
# (a fast, CPU-friendly reimplementation of OpenAI's Whisper).
#
# Flow:
# - User records audio via Streamlit (`st.audio_input` in app.py).
# - The audio file object is passed here.
# - We save it temporarily, run Whisper transcription, and return plain text.
#
# Why use `faster-whisper`?
# - Faster and lighter than the original Whisper.
# - Can run on CPU-only machines (important for hackathons).
# -------------------------------------------------

import os
os.environ["CT2_FORCE_CPU"] = "1"   # Force CTranslate2 to always use CPU.
                                   # This avoids errors if no GPU is available,
                                   # and ensures consistent behavior across laptops.

from pathlib import Path
from faster_whisper import WhisperModel

# -------------------------------------------------
# Whisper model initialization
# -------------------------------------------------
# We load the Whisper model once at import time so it's reused across calls.
#
# Model sizes available: "tiny", "base", "small", "medium", "large-v2".
# - "tiny": ~75 MB → very fast, lower accuracy
# - "base": ~145 MB → better accuracy
# - "small": ~450 MB → good tradeoff
#
# For hackathons and demos, "tiny" is a good start since it downloads quickly.
# `device="cpu"` forces CPU inference (no GPU required).
# `compute_type="int8"` makes it more memory- and speed-efficient.
# -------------------------------------------------
_whisper = WhisperModel("tiny", device="cpu", compute_type="int8")


# -------------------------------------------------
# transcribe_audio()
# -------------------------------------------------
# Main function called by app.py when an audio file is available.
#
# Input: uploaded_file → Streamlit’s UploadedFile object (from st.audio_input).
# Steps:
#   1. Save the audio to disk (temporary file "user_audio.wav").
#   2. Call the Whisper model’s transcribe() method.
#   3. Collect all text segments and join them into one string.
#   4. Return the clean transcript.
#
# Output: plain text string containing what the user said.
# -------------------------------------------------
def transcribe_audio(uploaded_file) -> str:
    if not uploaded_file:
        return ""  # No audio uploaded → return empty string

    # Save the uploaded bytes to a temporary file
    tmp = Path("user_audio.wav")
    tmp.write_bytes(uploaded_file.getvalue())

    # Run transcription
    # - beam_size=1: simplest decoding (fastest), no fancy beam search.
    segments, _ = _whisper.transcribe(str(tmp), beam_size=1)

    # Concatenate the text of all segments and strip extra whitespace.
    return " ".join(seg.text.strip() for seg in segments).strip()
