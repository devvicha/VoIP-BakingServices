Google Speech-to-Text (Sinhala + English) — Live Streaming
==========================================================

This project streams audio from your Mac's input device (e.g., your iPhone acting as a mic) to Google Cloud Speech-to-Text and prints live transcriptions. It supports Sinhala (`si-LK`) and English (`en-US`, `en-GB`, etc.) via multi-language recognition.

Prerequisites
-------------
- Conda environment: `conda activate speech-to-text-google`
- Packages (already in `environment.yml`): `pyaudio`, `portaudio`, `google-cloud-speech`, `grpcio`, `protobuf`, `azure-cognitiveservices-speech`
- Google Cloud project with Speech-to-Text API enabled
- Service account JSON credentials

Google Cloud Setup
------------------
1. Create a Google Cloud project (or use an existing one).
2. Enable the Speech-to-Text API.
3. Create a service account and download a JSON key.
4. Point the client to your key:

   macOS/zsh example:
   `export GOOGLE_APPLICATION_CREDENTIALS="/absolute/path/to/your-key.json"`

Using Your iPhone as a Microphone
---------------------------------
Use any app that exposes your iPhone as a virtual mic on macOS (e.g., WO Mic or similar). Once connected, macOS will show a new input device. You can select it by index in this project.

List Input Devices
------------------
`python src/list_devices.py`

Note the index of your iPhone mic device and its default sample rate.

Run Live Transcription
----------------------
Basic (Sinhala primary, English alt):
`python src/stream_google_stt.py --lang si-LK --alt en-US --rate 44100 --channels 1 --device <INDEX>`

Examples:
- Sinhala primary, English alt:
  `python src/stream_google_stt.py --lang si-LK --alt en-US --rate 44100 --device 3`
- English primary with Sinhala alt:
  `python src/stream_google_stt.py --lang en-US --alt si-LK --rate 48000 --device 3`

Flags
-----
- `--lang`: Primary BCP-47 language code (e.g., `si-LK`, `en-US`).
- `--alt`: Comma-separated alternative language codes for auto-detect.
- `--rate`: Sample rate in Hz. Match your input device (44100 or 48000 common).
- `--channels`: Channels (1 recommended).
- `--device`: Input device index from `src/list_devices.py`. Omit to use default input.

Notes
-----
- Match `--rate` and `--channels` to your input device to avoid audio issues.
- The script prints interim results in-place, and final results on new lines.
- Stop with Ctrl+C.

Troubleshooting
---------------
- Authentication: ensure `GOOGLE_APPLICATION_CREDENTIALS` is exported and file is readable.
- Microphone: if you get silence or errors, try a different `--rate` (44100 vs 48000) and verify the device index.
- Permissions: macOS may prompt to allow microphone access for your terminal.

Azure Speech Recognition
------------------------
Set environment variables from your Azure Speech resource (from the Azure portal):
- `export AZURE_SPEECH_KEY="<KEY 1 or KEY 2>"`
- `export AZURE_SPEECH_REGION="uaenorth"` (or set `AZURE_SPEECH_ENDPOINT="https://uaenorth.api.cognitive.microsoft.com/"`)
- Optional language list: `export AZURE_SPEECH_LANGS="si-LK,en-US"`

List input devices (same as for Google):
`python src/list_devices.py`

Run Azure live transcription with auto language detection:
`python src/stream_azure_stt.py --rate 44100 --device <INDEX>`

Options:
- `--key`, `--region`, `--endpoint` can be passed as flags or via env vars.
- `--langs` a comma-separated list for auto-detect (e.g., `si-LK,en-US`).
- `--rate`, `--channels`, `--device` should match your input.

Notes:
- Azure auto language detection uses your candidate list. Recognition quality improves if you list only languages you expect.
- Ensure the language codes you use are supported by Azure in your region.
