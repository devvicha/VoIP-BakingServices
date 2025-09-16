import argparse
import os
import queue
import sys
import threading
import time
from typing import Iterable, Optional

import pyaudio
from google.cloud import speech_v1 as speech


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
        stream_kwargs = dict(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.chunk,
            stream_callback=self._fill_buffer,
        )
        if self.device_index is not None:
            stream_kwargs["input_device_index"] = self.device_index

        self._stream = self._audio_interface.open(**stream_kwargs)
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
    language_code: str,
    rate: int,
    device_index: Optional[int],
    channels: int,
    alt_langs: Optional[list[str]] = None,
    enable_punctuation: bool = True,
    interim: bool = True,
):
    client = speech.SpeechClient()

    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=rate,
        language_code=language_code,
        alternative_language_codes=(alt_langs or []),
        enable_automatic_punctuation=enable_punctuation,
        audio_channel_count=channels,
        model="default",
    )

    streaming_config = speech.StreamingRecognitionConfig(
        config=config,
        interim_results=interim,
        single_utterance=False,
    )

    chunk = int(rate / 10)  # ~100ms
    with MicrophoneStream(rate, chunk, device_index=device_index, channels=channels) as mic:
        audio_generator = mic.generator()

        requests = (
            speech.StreamingRecognizeRequest(audio_content=content)
            for content in audio_generator
        )

        responses = client.streaming_recognize(streaming_config, requests)

        print("Listening… Press Ctrl+C to stop.\n")
        try:
            for response in responses:
                if not response.results:
                    continue
                result = response.results[0]
                if not result.alternatives:
                    continue
                transcript = result.alternatives[0].transcript
                if result.is_final:
                    print(transcript)
                else:
                    # Overwrite line for interim results
                    sys.stdout.write("\r" + transcript + " " * 10)
                    sys.stdout.flush()
        except KeyboardInterrupt:
            print("\nStopping…")


def main():
    parser = argparse.ArgumentParser(description="Stream mic audio to Google STT (Sinhala/English)")
    parser.add_argument("--lang", default="si-LK", help="Primary language code (e.g., si-LK or en-US)")
    parser.add_argument(
        "--alt",
        default="en-US",
        help="Comma-separated alternative language codes for auto-detect (e.g., en-US,en-GB)",
    )
    parser.add_argument("--rate", type=int, default=44100, help="Sample rate in Hz (match your device)")
    parser.add_argument("--channels", type=int, default=1, help="Number of input channels")
    parser.add_argument(
        "--device",
        type=int,
        default=None,
        help="Input device index (see list_devices.py)",
    )
    args = parser.parse_args()

    creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds:
        print(
            "WARNING: GOOGLE_APPLICATION_CREDENTIALS is not set. Export it to your service account JSON.",
            file=sys.stderr,
        )

    alt_langs = [s.strip() for s in args.alt.split(",") if s.strip()]
    stream_transcribe(
        language_code=args.lang,
        rate=args.rate,
        device_index=args.device,
        channels=args.channels,
        alt_langs=alt_langs,
    )


if __name__ == "__main__":
    main()

