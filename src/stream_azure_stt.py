import argparse
import os
import queue
import sys
from pathlib import Path
from typing import Iterable, Optional

import pyaudio
import azure.cognitiveservices.speech as speechsdk

# Load environment variables from .env file if it exists
def load_env_file():
    env_file = Path(__file__).parent.parent / '.env'
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

load_env_file()


def list_devices(pa: pyaudio.PyAudio) -> None:
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if int(info.get("maxInputChannels", 0)) > 0:
            print(f"[{i}] {info['name']} - {int(info['maxInputChannels'])} ch @ {int(info.get('defaultSampleRate', 0))} Hz")


class MicrophoneStream:
    def __init__(self, rate: int, chunk: int, device_index: Optional[int] = None, channels: int = 1):
        self.rate = rate
        self.chunk = chunk
        self.channels = channels
        self.device_index = device_index
        self._audio_interface = pyaudio.PyAudio()
        self._buff: "queue.Queue[bytes]" = queue.Queue()
        self._closed = True

    def __enter__(self):
        kwargs = dict(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.chunk,
            stream_callback=self._fill_buffer,
        )
        if self.device_index is not None:
            kwargs["input_device_index"] = self.device_index
        self._stream = self._audio_interface.open(**kwargs)
        self._closed = False
        return self

    def __exit__(self, exc_type, exc, traceback):
        try:
            self._stream.stop_stream()
            self._stream.close()
        finally:
            self._closed = True
            self._buff.put(None)
            self._audio_interface.terminate()

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self) -> Iterable[bytes]:
        while not self._closed:
            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]
            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break
            yield b"".join(data)


def stream_transcribe(
    key: str,
    region: Optional[str],
    endpoint: Optional[str],
    rate: int,
    device_index: Optional[int],
    channels: int,
    languages: list[str],
    interim: bool = True,
    show_lang: bool = True,
):
    if endpoint:
        speech_config = speechsdk.SpeechConfig(subscription=key, endpoint=endpoint)
    else:
        if not region:
            raise ValueError("Provide AZURE_SPEECH_REGION or --region when no endpoint is set")
        speech_config = speechsdk.SpeechConfig(subscription=key, region=region)

    autodetect = speechsdk.languageconfig.AutoDetectSourceLanguageConfig(languages=languages)

    fmt = speechsdk.audio.AudioStreamFormat(
        samples_per_second=rate,
        bits_per_sample=16,
        channels=channels,
    )
    push_stream = speechsdk.audio.PushAudioInputStream(stream_format=fmt)
    audio_config = speechsdk.audio.AudioConfig(stream=push_stream)

    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config,
        auto_detect_source_language_config=autodetect,
    )

    def on_recognizing(evt):
        if interim and evt.result.text:
            sys.stdout.write("\r" + evt.result.text + " " * 10)
            sys.stdout.flush()

    def on_recognized(evt):
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            text = evt.result.text
            if text:
                lang = None
                try:
                    lang = speechsdk.AutoDetectSourceLanguageResult(evt.result).language
                except Exception:
                    pass
                prefix = f"[{lang}] " if (show_lang and lang) else ""
                print("\r" + prefix + text)

    def on_canceled(evt):
        print(f"Canceled: {evt.reason}")
        if evt.error_details:
            print(evt.error_details)

    recognizer.recognizing.connect(on_recognizing)
    recognizer.recognized.connect(on_recognized)
    recognizer.canceled.connect(on_canceled)

    recognizer.start_continuous_recognition()

    chunk = int(rate / 10)
    with MicrophoneStream(rate, chunk, device_index=device_index, channels=channels) as mic:
        print("Listening… Press Ctrl+C to stop.\n")
        try:
            for data in mic.generator():
                push_stream.write(data)
        except KeyboardInterrupt:
            pass

    push_stream.close()
    recognizer.stop_continuous_recognition()


def main():
    parser = argparse.ArgumentParser(description="Stream mic audio to Azure Speech (Sinhala/English)")
    parser.add_argument("--region", default=os.environ.get("AZURE_SPEECH_REGION"), help="Azure region, e.g., uaenorth")
    parser.add_argument("--endpoint", default=os.environ.get("AZURE_SPEECH_ENDPOINT"), help="Full endpoint URL (optional)")
    parser.add_argument("--key", default=os.environ.get("AZURE_SPEECH_KEY"), help="Azure Speech key")
    parser.add_argument("--langs", default=os.environ.get("AZURE_SPEECH_LANGS", "si-LK,en-US"), help="Comma-separated language codes for auto-detect")
    parser.add_argument("--rate", type=int, default=44100, help="Sample rate in Hz")
    parser.add_argument("--channels", type=int, default=1, help="Number of input channels")
    parser.add_argument("--device", type=int, default=None, help="Input device index")
    parser.add_argument("--no-show-lang", action="store_true", help="Do not print detected language tag")
    args = parser.parse_args()

    if not args.key:
        print("Set --key or AZURE_SPEECH_KEY.", file=sys.stderr)
        sys.exit(1)

    languages = [s.strip() for s in args.langs.split(",") if s.strip()]
    stream_transcribe(
        key=args.key,
        region=args.region,
        endpoint=args.endpoint,
        rate=args.rate,
        device_index=args.device,
        channels=args.channels,
        languages=languages,
        show_lang=not args.no_show_lang,
    )


if __name__ == "__main__":
    main()

