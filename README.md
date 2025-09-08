# 🚗 Driving Concierge — Free Stack

An AI-powered **in-car assistant / concierge** built for a hackathon.  
It helps drivers plan smarter trips by suggesting stops along the route:
- ⚡ EV charging stations
- ⛽ Gas stations
- ☕ Coffee & food
- 👨‍👩‍👧 Family-friendly stops
- 🛠 Service centers

Features:
- 🎙 Voice input (transcribed locally with [faster-whisper])
- 🤖 Local LLM planning (via [Ollama], e.g. Llama 3.2)
- 🗺 Route & places from Google Maps (Routes + Places API)
- 🔊 Spoken output using the browser’s built-in Text-to-Speech
- 🖥 Interactive Streamlit web app

---

## 🛠 Prerequisites

- **Python 3.10+**  
- **pip** (Python package manager)  
- **Ollama** (for local LLMs): [Download here](https://ollama.ai)  
- A **Google Maps API key** with the following APIs enabled:
  - Routes API
  - Places API (New)
  - Maps JavaScript API

---

## 📦 Installation

Clone the repo (or copy the files) and set up your environment:

```bash
# 1. Create project folder
mkdir driving-concierge && cd driving-concierge

# 2. (Optional) create a virtual environment
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
.venv\Scripts\activate      # Windows PowerShell

# 3. Install dependencies
pip install -r requirements.txt
```

Dependencies include:
- `streamlit` → UI framework
- `faster-whisper` → Speech-to-text
- `requests` → API calls
- `pydantic` → JSON validation
- `python-dotenv` → Load secrets from `.env`

---

## 🔑 Configuration

1. Copy `.env.example` → `.env`
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your Google Maps API key:
   ```
   GOOGLE_MAPS_API_KEY=AIza...
   ```

⚠️ Never commit your real `.env` file to GitHub. Use `.env.example` for sharing.

---

## 🤖 Set up Ollama (local LLM)

1. [Install Ollama](https://ollama.ai) (macOS, Windows, or Linux).  
2. Start the server:
   ```bash
   ollama serve
   ```
3. Pull a model (choose one depending on your machine):
   ```bash
   ollama pull llama3.2:3b   # small, fast
   # or
   ollama pull llama3.1:8b   # larger, better reasoning
   ```

---

## ▶️ Running the App

Launch the Streamlit app:

```bash
streamlit run app.py
```

- Open the link printed in your terminal (usually http://localhost:8501).
- In the sidebar, set:
  - Origin and destination
  - Vehicle type (EV or Gasoline)
  - Preferences (fast, scenic, family-friendly)
- Either:
  - Speak into the mic 🎤 (your text will appear in the input box automatically), or
  - Type directly into the input box.
- Click **Go**:
  - The app transcribes your request (if spoken).
  - The LLM extracts intent & builds a Places query.
  - Google APIs find relevant stops along the route.
  - A spoken summary plays 🔊.
  - A map appears 🗺 with your route and markers.

---

## 🧩 Project Structure

```
driving-concierge/
├─ app.py                 # Streamlit entry point (UI + workflow)
├─ services/              # Core services
│  ├─ stt.py              # Speech-to-text (faster-whisper)
│  ├─ llm.py              # Local LLM intent extraction
│  └─ maps.py             # Google Routes + Places API calls
├─ ui/                    # UI helpers
│  ├─ maps_embed.py       # Embed Google Map with route + markers
│  └─ tts_browser.py      # Browser-based text-to-speech
├─ utils/
│  └─ settings.py         # Loads secrets (Google API key) from .env
├─ requirements.txt       # Python dependencies
├─ .env.example           # Example environment file
└─ README.md              # This file
```

---

## 🚀 Tips for Hackathon Teams

- 🔧 If Whisper accuracy is low, switch to `"base"` or `"small"` in `services/stt.py`.
- ⚡ If LLM is too slow, try `llama3.2:3b` instead of `llama3.1:8b`.
- 🗺 Google APIs are free for limited usage. Monitor your quota during demos.
- 🔊 If auto-speech replays on refresh, we use a **nonce system** to ensure it only speaks once per response.

---

## 🐞 Troubleshooting

### ❌ Ollama 404: `requests.exceptions.HTTPError: 404 Client Error`
- Ensure Ollama server is running:
  ```bash
  ollama serve
  ```
- Check if the endpoint works:
  ```bash
  curl http://localhost:11434/api/tags
  ```
  If it fails, restart Ollama or update to the latest version.
- Some older versions don’t support `/api/chat`. Our code falls back to `/api/generate`.

### ❌ Audio input not working in Streamlit
- Ensure your browser has **mic permissions enabled**.
- In Chrome: lock icon (🔒) → Site settings → Allow Microphone.
- Safari: Preferences → Websites → Microphone → Allow for localhost.

### ❌ Google Maps errors or blank map
- Double-check your `.env` file → is the API key valid?
- Make sure **Routes API**, **Places API (New)**, and **Maps JavaScript API** are enabled in Google Cloud Console.
- Restrict API key to `http://localhost:8501/*` for safety.

### ❌ Speech not playing
- Some browsers block auto-play. Click anywhere in the page before pressing Go.
- If still blocked, fall back to a manual "🔊 Speak" button.

### ❌ Very slow Whisper transcription
- Default uses `"tiny"` model (~75 MB). Faster but less accurate.
- Change to `"base"` or `"small"` in `services/stt.py` if CPU is decent.

---

## 📜 License

MIT — feel free to use and adapt for your hackathon projects.
