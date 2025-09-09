# AI Driving Concierge

A voice-controlled dashboard for managing car comfort settings using Streamlit and AI audio processing.


## Features

### Voice Control
- **Audio Recording**: Click to record voice commands for adjusting car settings
- **Real-time Processing**: AI processes audio commands and updates settings automatically

### Dashboard Controls
- **Temperature Control**: Adjustable temperature display in °C
- **Fan Speed Management**: Variable fan speed control in RPM
- **Steering Wheel Heating**: Simple On/Off toggle
- **Seat Heating**: Separate controls for Left (L), Right (R), and Back seats with heating levels 0 (Off) to 3 (Max)

### Prerequisites
Install the required dependencies:
```bash
pip install -m requirements.txt
```

### Environment Setup
Configure your OpenAI API key:
```bash
OPENAI_API_KEY = "your-api-key-here"
```

## Usage

### Getting Started
1. **Start the application:**
   ```bash
   streamlit run app.py
   ```

2. **Voice Commands:**
   - Click the record button to start recording
   - Speak your command clearly
   - Examples:
     - "Set temperature to 22 degrees"
     - "Decrease the fan speed by 10"
     - "Turn on the steering wheel heating"
     - "Set left seat heating to level 2"
   - The AI will process your command and update the dashboard automatically

## Technical Architecture

### How It Works
1. **Audio Capture**: `app.py` captures audio using `audio_recorder_streamlit` and passes raw bytes to `do_the_action`

2. **Speech Recognition**: `ai_utils.speech_to_text` sends audio bytes to OpenAI Whisper (`model="whisper-1"`) to generate plain text transcript

3. **Command Processing**: `ai_utils.generate_response` calls the LLM with a tool schema for all available car actions

4. **Action Execution**: LLM determines which tools to call and in what order; Python functions in `function_tools.py` update `st.session_state`

5. **UI Update**: `app.py` reruns automatically and dashboard panels reflect the new state immediately

### Session State Management
The application tracks these settings in Streamlit session state:
- `temperature`: Integer value in °C
- `fan_speed`: Integer value in RPM  
- `steering_wheel_heating`: String status ("On"/"Off")
- `seat_heating`: function with levels 0-3 (integers) for Left (L), Right (R), and Back seats

## User Interface

The frontend is built with Streamlit and enhanced with custom CSS styling for an intuitive car dashboard experience.

![UI.png](UI.png)

## File Structure
- `app.py`: Main Streamlit application and UI logic
- `ai_utils.py`: Speech-to-text and LLM response generation
- `function_tools.py`: Car setting control functions
- `requirements.txt`: Python dependencies