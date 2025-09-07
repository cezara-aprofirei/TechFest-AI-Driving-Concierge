import streamlit as st
import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()
api_key = os.getenv('OPENAI_API_KEY')

# Initialize OpenAI client
client = OpenAI()

# Streamlit UI
st.title("Transcription with Whisper")

# Audio input for transcription
audio_value = st.audio_input("Record a voice message to transcribe")

if audio_value:
    # Transcribe audio
    transcript = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_value
    )

    transcript_text = transcript.text
    st.write(transcript_text)

    # Download button
    if "downloaded" not in st.session_state:
        st.session_state.downloaded = False

    if st.download_button(
        label="Download Transcription",
        file_name="transcription.txt",
        data=transcript_text,
    ):
        st.session_state.downloaded = True

    # Success message
    if st.session_state.downloaded:
        st.success("Transcription file downloaded successfully!")
