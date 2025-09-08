# Import required libraries
import streamlit as st  # main Streamlit library for building web apps
from audio_recorder_streamlit import audio_recorder  # third-party component for recording audio in Streamlit
from ai_utils import do_the_action  # custom function for processing audio


# Initialize session state variables with default values if they don't exist
st.session_state.setdefault("temperature", 0)  # Current temperature setting (starts at 0°C)
st.session_state.setdefault("fan_speed", 50)  # Current fan speed (starts at 50 RPM)
st.session_state.setdefault("steering_wheel_heating", "Off") # defaults for steering wheel heating feature
st.session_state.setdefault("seat_heating", {"L": "Off", "R": "Off", "Back": "Off"})  # defaults for seat heating features
st.session_state.setdefault("audio_bytes", None)  # Stores recorded audio data
st.session_state.setdefault("last_audio_sent", None)  # Tracks last processed audio to prevent duplicates
st.session_state.setdefault("processing", False)  # Flag to indicate if audio is being processed

# UI Display
st.title("AI Driving Concierge")

if not st.session_state.processing:
    audio = audio_recorder(
        text="Tune comfort settings", 
        recording_color="#FF0000",
        neutral_color="#FFFFFF",
        icon_size="2x",  # smaller icon
        pause_threshold=5
    )

    st.markdown(
        "<h4 style='color:#ffffff; margin-bottom: 20px;'>", 
        unsafe_allow_html=True
    )

    # First row - 2 columns
    col1, col2 = st.columns(2)

    # Compact styling
    compact_style = """
        border: 1px solid #444;
        border-radius: 12px;
        padding: 10px 15px;
        text-align: center;
        background-color: #1e1e1e;
        color: #ffffff;
        font-size: 14px;
        box-shadow: 0 0 6px rgba(255, 255, 255, 0.08);
        margin-bottom: 10px;
    """

    with col1:
        st.markdown(
            f"""
            <div style="{compact_style}">
                <div style="font-size: 16px;">🌡️ Temperature</div>
                <div style="font-size: 24px; font-weight: bold;">{st.session_state.temperature} °C</div>
            </div>
            """, unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            f"""
            <div style="{compact_style}">
                <div style="font-size: 16px;">🌪️ Fan Speed</div>
                <div style="font-size: 24px; font-weight: bold;">{st.session_state.fan_speed} RPM</div>
            </div>
            """, unsafe_allow_html=True
        )

    # Second row - 2 columns
    col3, col4 = st.columns(2)

    with col3:
        st.markdown(
            f"""
            <div style="{compact_style}">
                <div style="font-size: 16px;">🛞 Steering Wheel Heating</div>
                <div style="font-size: 24px; font-weight: bold;">{st.session_state.steering_wheel_heating}</div>
            </div>
            """, unsafe_allow_html=True
        )

    with col4:
        st.markdown(
            f"""
            <div style="{compact_style}">
                <div style="font-size: 16px;">♨️ Seat Heating</div>
                <div style="font-size: 18px; font-weight: bold;">
                    L: {st.session_state.seat_heating["L"]} | 
                    R: {st.session_state.seat_heating["R"]} | 
                    Back: {st.session_state.seat_heating["Back"]}
                </div>
            </div>
            """, unsafe_allow_html=True
        )



    # Check if new audio was recorded and it's different from last one
    if audio and audio != st.session_state.last_audio_sent:
        # Store audio and switch to processing mode
        st.session_state.audio_bytes = audio  # Save the audio data
        st.session_state.last_audio_sent = audio  # Update tracker to prevent reprocessing
        st.session_state.processing = True  # Set processing flag
        st.rerun()  # Refresh the app to show processing state

# Process audio if ready
elif st.session_state.processing and st.session_state.audio_bytes:
    # Show spinner while processing audio
    with st.spinner("Processing audio..."):
        # Call AI function to process the audio
        do_the_action(st.session_state.audio_bytes)
        
        # Clean up and reset state
        st.session_state.audio_bytes = None  # Clear audio data
        st.session_state.processing = False  # Reset processing flag
        
        # Show success message
        st.success("Done! Temp updated.")
        
        # Refresh app to show updated variable and reset UI
        st.rerun()