# Import required libraries
import streamlit as st  # main Streamlit library for building web apps
from audio_recorder_streamlit import audio_recorder  # third-party component for recording audio in Streamlit
from ai_utils import do_the_action  # custom function for processing audio


# Initialize session state variables with default values if they don't exist
st.session_state.setdefault("temperature", 0)  # Current temperature setting (starts at 0°C)
st.session_state.setdefault("fan_speed", 50)  # Current fan speed (starts at 50 RPM)
st.session_state.setdefault("left_window", 'Close')
st.session_state.setdefault("right_window", 'Close')
st.session_state.setdefault("audio_bytes", None)  # Stores recorded audio data
st.session_state.setdefault("last_audio_sent", None)  # Tracks last processed audio to prevent duplicates
st.session_state.setdefault("processing", False)  # Flag to indicate if audio is being processed

# UI Display
st.title("AI Driving Concierge")

# Audio Recording Logic
if not st.session_state.processing:
    # Create audio recorder widget with custom styling
    audio = audio_recorder(
        text="Tune comfort settings", 
        recording_color="#FF0000",  # Red color when recording
        neutral_color="#FFFFFF",  # White color when not recording
        icon_size="3x",  # Large icon size
        pause_threshold = 5
    )

    st.subheader(f"🌡️ Temp: {st.session_state.temperature} °C")
    st.subheader(f"🌪️ Fan Speed: {st.session_state.fan_speed} RPM")
    st.subheader(f"⬅️Left Window: {st.session_state.left_window}")
    st.subheader(f"➡️ Right Window: {st.session_state.right_window}")

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
