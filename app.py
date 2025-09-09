import streamlit as st
from audio_recorder_streamlit import audio_recorder
from ai_utils import do_the_action

# Initialize session state
st.session_state.setdefault("temperature", 0)
st.session_state.setdefault("fan_speed", 50)
st.session_state.setdefault("steering_wheel_heating", "Off")
st.session_state.setdefault("seat_heating", {"L": 0, "R": 0, "Back": 0})
st.session_state.setdefault("audio_bytes", None)
st.session_state.setdefault("last_audio_sent", None)
st.session_state.setdefault("processing", False)

# Title
st.title("Tune comfort settings")

# --- Stil pentru panouri ---
compact_style = """
    border: 1px solid #444;
    border-radius: 12px;
    padding: 10px 15px;
    text-align: center;
    background-color: #1e1e1e;
    color: #ffffff;
    font-size: 14px;
    box-shadow: 0 0 6px rgba(255, 255, 255, 0.08);
    min-height: 80px;
    display: flex;
    flex-direction: column;
    justify-content: center;
"""

# --- 5 coloane: microfon + cele 4 panouri în linie ---
mic_col, temp_col, fan_col, wheel_col, seat_col = st.columns([1, 1, 1, 1, 1.5])

# --- Microfon ---
with mic_col:
    if not st.session_state.processing:
        audio = audio_recorder(
            text="",
            recording_color="#FF0000",
            neutral_color="#FFFFFF",
            icon_size="5x",
            pause_threshold=2
        )
        if audio and audio != st.session_state.last_audio_sent:
            st.session_state.audio_bytes = audio
            st.session_state.last_audio_sent = audio
            st.session_state.processing = True
            st.rerun()

# --- Temperature Panel ---
with temp_col:
    st.markdown(
        f"""
        <div style="{compact_style}">
            <div style="font-size: 16px;">🌡️ Temperature</div>
            <div style="font-size: 24px; font-weight: bold;">{st.session_state.temperature} °C</div>
        </div>
        """, unsafe_allow_html=True
    )

# --- Fan Speed Panel ---
with fan_col:
    st.markdown(
        f"""
        <div style="{compact_style}">
            <div style="font-size: 16px;">🌪️ Fan Speed</div>
            <div style="font-size: 24px; font-weight: bold;">{st.session_state.fan_speed} RPM</div>
        </div>
        """, unsafe_allow_html=True
    )

# --- Steering Wheel Heating Panel ---
with wheel_col:
    st.markdown(
        f"""
        <div style="{compact_style}">
            <div style="font-size: 16px;">🛞 Wheel Heat</div>
            <div style="font-size: 24px; font-weight: bold;">{st.session_state.steering_wheel_heating}</div>
        </div>
        """, unsafe_allow_html=True
    )

# --- Seat Heating Panel ---
with seat_col:
    st.markdown(
        f"""
        <div style="{compact_style}">
            <div style="font-size: 16px;">♨️ Seat Heating</div>
            <div style="font-size: 20px; font-weight: bold; line-height: 1.6;">
                L: {st.session_state.seat_heating["L"]} | R: {st.session_state.seat_heating["R"]}<br>
                Back: {st.session_state.seat_heating["Back"]}
            </div>
        </div>
        """, unsafe_allow_html=True
    )


# --- Procesare audio ---
if st.session_state.processing and st.session_state.audio_bytes:
    with st.spinner("Processing audio..."):
        do_the_action(st.session_state.audio_bytes)
        st.session_state.audio_bytes = None
        st.session_state.processing = False
        st.success("Done! Temp updated.")
        st.rerun()