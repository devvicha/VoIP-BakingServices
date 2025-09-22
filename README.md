# VoIP-BakingServices — Sinhala Voice Assistant

Streams Sinhala audio from macOS or iPhone microphones into Azure Speech for live transcription, normalises Unicode, shows interim/final text with language tags, manages device selection and errors, optionally adds OpenAI replies plus Sinhala TTS with a forced welcome greeting, and supports device listing, custom capture rates, and `.env` / CLI configuration.

## Key Features
- **Real-time Sinhala STT** powered by Azure Cognitive Services with interim and final captions.
- **Warm customer greeting** (`"ආයුබෝවන්…"`) spoken before listening begins, ensuring users hear a prompt immediately.
- **Optional AI assistant**: send recognised utterances to OpenAI for Sinhala responses when `ENABLE_AI_RESPONSES=true`.
- **Sinhala TTS playback** using Azure neural voices (enable via `ENABLE_TTS=true`).
- **Automatic mic selection** (auto-picks iPhone input when available) with manual override and device listing support.
- **Robust Unicode handling** so Sinhala text renders correctly in terminals and logs.

## Requirements
- Python 3.13 (uses `.venv` in this repository by default).
- Azure Speech resource (`AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`).
- Optional OpenAI API key (`OPENAI_API_KEY`) when enabling AI replies.
- macOS microphone permissions granted to your terminal/IDE (`System Settings → Privacy & Security → Microphone`).
- Audio dependencies installed inside the virtualenv:
  ```bash
  python -m pip install azure-cognitiveservices-speech pyaudio pygame openai
  ```

## Project Setup
1. Clone the repository and create a virtual environment (if you do not already use the included `.venv`).
2. Install the dependencies listed above inside that environment.
3. Copy `.env.example` to `.env` (if available) or create `.env` manually with:
   ```dotenv
   AZURE_SPEECH_KEY=your-key
   AZURE_SPEECH_REGION=uaenorth
   AZURE_SPEECH_LANGS=si-LK
   AZURE_TTS_VOICE=si-LK-ThiliniNeural
   ENABLE_TTS=true
   ENABLE_AI_RESPONSES=false
   OPENAI_API_KEY=optional-openai-key
   OPENAI_MODEL=gpt-4o
   ```
4. (Optional) Follow the Sinhala font instructions in `SINHALA_SETUP.md` and `vscode-sinhala-settings.json` if your terminal renders Sinhala poorly.

## Running the Assistant
List input devices if you need to confirm the microphone index:
```bash
python src/stream_azure_stt.py --list-devices
```

Start live transcription (auto-selects iPhone mic when possible):
```bash
python src/stream_azure_stt.py --rate 16000 --channels 1
```

Common flags:
- `--key`, `--region`: override environment variables for Azure credentials.
- `--device`: specify a particular microphone index.
- `--rate`, `--channels`: match your audio interface (defaults pulled from env or sensible fallbacks).

When the script launches it prints system status, plays the Sinhala welcome message via TTS, and then begins streaming audio to Azure Speech. Recognised text appears live; if AI responses are enabled, they are printed and spoken back in Sinhala.

## Troubleshooting
- **OpenAI connection error**: confirm network access and the `OPENAI_API_KEY` environment variable.
- **`SPXERR_MIC_ERROR`**: check macOS microphone permissions and verify the selected device is connected.
- **CoreAudio / TTS failures**: ensure no other app is exclusively using the audio output device and that `ENABLE_TTS` is set correctly.
- **Sinhala text rendering issues**: revisit `SINHALA_SETUP.md` for terminal/font configuration tips.

## Repository Notes
- `src/stream_azure_stt.py` holds the Azure/OpenAI pipeline implementation and the welcome greeting logic.
- `SINHALA_SETUP.md` documents macOS + VSCode steps for Sinhala input/output support.
- `vscode-sinhala-settings.json` provides a ready-to-paste VS Code settings snippet for Sinhala-friendly fonts.

Happy building — ආයුබෝවන්!
