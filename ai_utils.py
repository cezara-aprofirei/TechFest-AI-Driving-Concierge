# Import required libraries
import streamlit as st  # For accessing Streamlit session state
from openai import OpenAI  # OpenAI API client for GPT and Whisper
import io  # For handling byte streams (audio data)
import os  # For environment variable access
import json  # For parsing JSON responses from OpenAI
from function_tools import change_temperature, change_fan_speed  # Custom function to change car temperature
import dotenv  # For loading environment variables from .env file

# Load environment variables from .env file
dotenv.load_dotenv()

# Get OpenAI API key from environment variables
api_key = os.getenv("OPENAI_API_KEY")
# Initialize OpenAI client with API key
client = OpenAI(api_key=api_key)

def speech_to_text(audio_bytes: bytes) -> str:
    """
    This function takes raw audio data and uses OpenAI's Whisper API to transcribe
    the spoken words into text.

    Args:
        audio_bytes (bytes):Raw audio data in bytes format

    Returns:
        str: Transcribed text from the audio. Returns the spoken words as a 
             plain text string.
    """
    # Create a BytesIO object from audio bytes
    audio_file = io.BytesIO(audio_bytes)
    # Set filename for the API
    audio_file.name = "audio.wav" 
    
    # Call OpenAI Whisper API to transcribe audio
    response = client.audio.transcriptions.create(
        model="whisper-1",  # OpenAI's speech-to-text model
        file=audio_file,  # Audio file to transcribe
        response_format="text"  # Return plain text instead of JSON
    )
    return response

def generate_response(user_message: str) -> str:
    """
    Sends a user message to OpenAI with tool support.
    Allows multiple tool calls in sequence before final response.
    """
    messages = [
        {"role": "system", "content": "You are an assistant that adjusts the car's comfort features like temperature and fan speed based on user voice commands."},
        {"role": "user", "content": user_message}
    ]

    tool_functions = {
        "change_temperature": change_temperature,
        "change_fan_speed": change_fan_speed
    }

    tools = [
        {
            "type": "function",
            "function": {
                "name": "change_temperature",
                "description": change_temperature.__doc__,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "delta": {
                            "type": "integer",
                            "description": "Amount to change temperature by (positive or negative)"
                        }
                    },
                    "required": ["delta"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "change_fan_speed",
                "description": change_fan_speed.__doc__,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "delta": {
                            "type": "integer",
                            "description": "Amount to change fan speed by (positive or negative)"
                        }
                    },
                    "required": ["delta"]
                }
            }
        }
    ]

    while True:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )

        msg = response.choices[0].message

        # if no tool calls, return final message
        if not msg.tool_calls:
            final = msg.content
            print("Final GPT message:", final)
            return "success"

        # execute each tool call
        tool_messages = []
        for tool_call in msg.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)

            func = tool_functions.get(name)
            if func:
                try:
                    result = func(**args)
                    output = "success" if result else "failure"
                except Exception as e:
                    output = f"error: {e}"

                # add tool result to messages
                tool_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": name,
                    "content": output
                })

        # continue the conversation with tool results
        messages.append(msg)
        messages.extend(tool_messages)


def do_the_action(audio_bytes: bytes):
    """
    Process voice command and execute car control action.
    
    Converts audio to text using Whisper, then uses GPT to interpret
    and execute the appropriate car function (e.g., temperature control).
    
    Args:
        audio_bytes (bytes): Raw audio data from voice recording.
    
    Returns:
        str: "success" if command executed properly, "failure" otherwise.
    """
    # Step 1: Convert speech to text using Whisper
    user_message = speech_to_text(audio_bytes)
    print("Transcribed message:", user_message)  # Debug output

    # Step 2: Process the message with GPT and potentially execute tools
    result = generate_response(user_message)
    print("Tool execution result:", result)  # Debug output
    return result