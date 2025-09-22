import argparse
import os
import queue
import sys
from pathlib import Path
from typing import Iterable, Optional
import locale
import unicodedata
import time
import threading

import pyaudio
import azure.cognitiveservices.speech as speechsdk
import pygame
import io
import tempfile

from openai import AzureOpenAI, OpenAI

WELCOME_PROMPT = "ආයුබෝවන්, සම්පත් බැංකුවට ඔබව සාදරයෙන් පිළිගනිමු. මට උදව් කළ හැක්කේ කෙසේද?"

# Set UTF-8 encoding for proper Sinhala character display
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Set locale for proper Unicode handling
try:
    # Try Sinhala locale first
    locale.setlocale(locale.LC_ALL, 'si_LK.UTF-8')
    os.environ['LANG'] = 'si_LK.UTF-8'
    os.environ['LC_ALL'] = 'si_LK.UTF-8'
except:
    try:
        # Fallback to English UTF-8
        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
        os.environ['LANG'] = 'en_US.UTF-8'
        os.environ['LC_ALL'] = 'en_US.UTF-8'
    except:
        try:
            # Final fallback
            locale.setlocale(locale.LC_ALL, 'C.UTF-8')
        except:
            pass  # Use system default

# Load environment variables from .env file if it exists
def load_env_file():
    env_file = Path(__file__).parent.parent / '.env'
    if env_file.exists():
        with open(env_file, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

load_env_file()

# Initialize OpenAI client (Official OpenAI API)
openai_client = None
model_name = None
enable_ai_responses = False
_last_interim_display = ""

try:
    # Use official OpenAI API (much more reliable!)
    if os.getenv('OPENAI_API_KEY'):
        openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        model_name = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
        print(f"🤖 OpenAI API සම්බන්ධ කරමින්: {model_name}")
        
        # Test the connection
        test_response = openai_client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "හෙලෝ"}],
            max_tokens=10
        )
        
        enable_ai_responses = os.getenv('ENABLE_AI_RESPONSES', 'false').lower() == 'true'
        print(f"✅ OpenAI සම්බන්ධතාවය සාර්ථකයි!")
        print(f"🌟 AI සිංහල පිළිතුරු සක්‍රිය: {enable_ai_responses}")
        
    else:
        print("⚠️ OPENAI_API_KEY .env ගොනුවේ නැත")
        enable_ai_responses = False
        
except Exception as e:
    print(f"❌ OpenAI දෝෂයක්: {str(e)}")
    print("🔄 AI responses අක්‍රිය කරමින්...")
    enable_ai_responses = False

def normalize_sinhala_text(text):
    """Normalize Sinhala text to fix common character encoding issues"""
    if not text:
        return text
    
    # Normalize Unicode characters (NFC is standard for Sinhala)
    normalized = unicodedata.normalize('NFC', text)
    
    # Remove problematic zero-width characters that can cause display issues
    normalized = normalized.replace('\u200c', '')  # Remove ZWNJ
    normalized = normalized.replace('\u200d', '')  # Remove ZWJ
    normalized = normalized.replace('\ufeff', '')  # Remove BOM
    
    # Ensure proper Sinhala character combinations
    # Fix common spacing issues
    normalized = ' '.join(normalized.split())  # Normalize whitespace
    
    return normalized

def get_sinhala_response(prompt: str) -> str:
    """Generate intelligent Sinhala response using OpenAI"""
    if not openai_client or not enable_ai_responses:
        return ""
    
    try:
        print("🤔 AI සිතමින්...", end="", flush=True)
        
        # Enhanced system prompt for natural Sinhala conversation
        system_prompt = """ඔබ සිංහල භාෂාවෙන් කතා කරන බුද්ධිමත් සහායකයෙකි. 
        ඔබේ ගුණාංග:
        - සිංහල සංස්කෘතිය සහ භාෂාව ගැඹුරින් දන්නවා
        - ස්වභාවික, මිත්‍රශීලී සිංහල භාෂාවෙන් කතා කරනවා  
        - කෙටි, ප්‍රයෝජනවත් පිළිතුරු දෙනවා
        - ප්‍රශ්නවලට නිවැරදි සහ උපකාරී පිළිතුරු දෙනවා
        - සිංහල වචන සහ ප්‍රකාශන නිවැරදිව භාවිතා කරනවා"""
        
        response = openai_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.7,
            top_p=0.9,
            frequency_penalty=0.1,
            presence_penalty=0.1
        )
        
        # Clear the "thinking" indicator
        print("\r" + " " * 20 + "\r", end="", flush=True)
        
        ai_response = response.choices[0].message.content.strip()
        return ai_response
        
    except Exception as e:
        print(f"\r❌ AI දෝෂයක්: {str(e)}")
        return ""

def get_display_width(text):
    """Calculate display width accounting for Sinhala characters"""
    width = 0
    for char in text:
        if ord(char) >= 0x0D80 and ord(char) <= 0x0DFF:  # Sinhala Unicode range
            width += 2  # Sinhala characters often take more space
        else:
            width += 1
    return width


def _clear_interim_line():
    """Clear the previously printed interim line from stdout"""
    global _last_interim_display
    if not _last_interim_display:
        return
    sys.stdout.write("\r" + " " * get_display_width(_last_interim_display) + "\r")
    sys.stdout.flush()
    _last_interim_display = ""


def on_recognizing(evt: speechsdk.SpeechRecognitionEventArgs, show_lang: bool = True) -> None:
    """Handle interim recognition events"""
    global _last_interim_display
    text = normalize_sinhala_text(evt.result.text)
    if not text:
        return

    prefix = ""
    if show_lang and getattr(evt.result, "language", None):
        prefix = f"[{evt.result.language}] "

    display = f"📝 {prefix}{text}"
    sys.stdout.write("\r" + display)
    sys.stdout.flush()
    _last_interim_display = display


def on_recognized(evt: speechsdk.SpeechRecognitionEventArgs, show_lang: bool = True) -> None:
    """Handle final recognition events and trigger AI/TTS"""
    if evt.result.reason != speechsdk.ResultReason.RecognizedSpeech:
        if evt.result.reason == speechsdk.ResultReason.NoMatch:
            _clear_interim_line()
            print("🤷‍♀️ වාක්‍යය හඳුනාගත නොහැකිවුණි.")
        return

    text = normalize_sinhala_text(evt.result.text)
    if not text:
        return

    _clear_interim_line()

    prefix = ""
    if show_lang and getattr(evt.result, "language", None):
        prefix = f"[{evt.result.language}] "

    print(f"✅ {prefix}{text}")

    if enable_ai_responses:
        ai_reply = get_sinhala_response(text)
        if ai_reply:
            print(f"🤖 {ai_reply}")
            speak_sinhala_text(ai_reply)


def on_canceled(evt: speechsdk.SpeechRecognitionCanceledEventArgs) -> None:
    """Handle cancellation events from the recognizer"""
    _clear_interim_line()
    print("❌ Azure Speech සේවය නතර විය.")
    if evt.reason:
        print(f"   ↳ හේතුව: {evt.reason}")
    result = getattr(evt, "result", None)
    details = getattr(result, "cancellation_details", None)
    if details:
        if getattr(details, "error_code", None):
            print(f"   ↳ දෝෂ කේතය: {details.error_code}")
        if getattr(details, "error_details", None):
            print(f"   ↳ විස්තර: {details.error_details}")


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


# Initialize TTS
speech_synthesizer = None
enable_tts = False

try:
    if os.getenv('AZURE_SPEECH_KEY') and os.getenv('AZURE_SPEECH_REGION'):
        # Configure speech synthesis
        speech_config = speechsdk.SpeechConfig(
            subscription=os.getenv('AZURE_SPEECH_KEY'),
            region=os.getenv('AZURE_SPEECH_REGION')
        )
        
        # Set Sinhala voice
        voice_name = os.getenv('AZURE_TTS_VOICE', 'si-LK-ThiliniNeural')
        speech_config.speech_synthesis_voice_name = voice_name
        
        # Use default audio output
        speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)
        
        enable_tts = os.getenv('ENABLE_TTS', 'false').lower() == 'true'
        
        if enable_tts:
            # Initialize pygame mixer for audio
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            print(f"🔊 සිංහල TTS සක්‍රිය: {voice_name}")
        
except Exception as e:
    print(f"⚠️ TTS setup දෝෂයක්: {str(e)}")
    enable_tts = False

def stream_transcribe(
    key,
    region,
    lang_codes="si-LK",
    device_id=None,
    show_lang=True,
    rate=16000,
    channels=1,
):
    """Start streaming transcription - Sinhala only with TTS"""

    print("\n" + "=" * 60)
    print("🇱🇰 සිංහල කථන හඳුනාගැනීම + AI + TTS")
    print("=" * 60)
    print(f"🎤 මයික්‍රොෆෝන්: සක්‍රිය")
    print(f"🎚️ සැම්පල් වේගය: {rate} Hz — නාලිකා {channels}")
    print(f"🌍 භාෂාව: සිංහල පමණක්")
    print(f"🤖 AI සහායක: {'සක්‍රිය' if enable_ai_responses else 'අක්‍රිය'}")
    print(f"🔊 සිංහල TTS: {'සක්‍රිය' if enable_tts else 'අක්‍රිය'}")
    if enable_ai_responses:
        print(f"🧠 AI මොඩලය: {model_name}")
    if enable_tts:
        print(f"🎵 TTS හඬ: {os.getenv('AZURE_TTS_VOICE', 'si-LK-ThiliniNeural')}")
    print("=" * 60)
    print("📢 සිංහලෙන් කතා කරන්න...")
    print("🎧 AI පිළිතුරු ශ්‍රවණය කරන්න...")
    print("🛑 නතර කිරීමට Ctrl+C ඔබන්න")
    print("=" * 60)

    # Attempt to auto-select an iPhone microphone when available
    selected_device = device_id
    device_name = None
    auto_selected = False
    pa = None

    try:
        pa = pyaudio.PyAudio()
        if selected_device is None:
            for idx in range(pa.get_device_count()):
                info = pa.get_device_info_by_index(idx)
                if "iphone" in info.get("name", "").lower():
                    selected_device = idx
                    device_name = info.get("name")
                    auto_selected = True
                    break
        if selected_device is not None and device_name is None:
            info = pa.get_device_info_by_index(selected_device)
            device_name = info.get("name")
    except Exception as lookup_err:
        print(f"⚠️ මයික් භාවිත සඳහා උපකරණ පරීක්ෂණ දෝෂයක්: {lookup_err}")
    finally:
        if pa:
            pa.terminate()

    if selected_device is not None and device_name:
        if auto_selected:
            print(f"📱 iPhone මයික් ස්වයංක්‍රීයව තේරුණි: {device_name} (#{selected_device})")
        else:
            print(f"🎤 තෝරාගත් උපකරණය: {device_name} (#{selected_device})")
    else:
        print("🎤 Default macOS මයික් භාවිතා කෙරේ")

    greeting_text = normalize_sinhala_text(WELCOME_PROMPT)
    print(f"📣 {greeting_text}")
    speak_sinhala_text(greeting_text, force=True)

    # Configure speech recognition
    speech_key = key
    service_region = region

    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
    speech_config.speech_recognition_language = lang_codes

    audio_stream = None
    audio_thread = None
    audio_stop_event = threading.Event()

    if selected_device is not None:
        chunk_size = max(320, int(rate / 10))
        audio_format = speechsdk.audio.AudioStreamFormat(
            samples_per_second=rate,
            bits_per_sample=16,
            channels=channels,
        )
        audio_stream = speechsdk.audio.PushAudioInputStream(stream_format=audio_format)
        audio_config = speechsdk.audio.AudioConfig(stream=audio_stream)

        def feed_device_audio():
            stream = None
            pa_local = pyaudio.PyAudio()
            try:
                stream = pa_local.open(
                    format=pyaudio.paInt16,
                    channels=channels,
                    rate=rate,
                    input=True,
                    frames_per_buffer=chunk_size,
                    input_device_index=selected_device,
                )
                while not audio_stop_event.is_set():
                    data = stream.read(chunk_size, exception_on_overflow=False)
                    if not data:
                        continue
                    try:
                        audio_stream.write(data)
                    except Exception:
                        break
            except Exception as mic_err:
                print(f"❌ මයික් දෝෂයක්: {mic_err}")
            finally:
                audio_stop_event.set()
                if stream:
                    try:
                        stream.stop_stream()
                        stream.close()
                    except Exception:
                        pass
                pa_local.terminate()
                try:
                    audio_stream.close()
                except Exception:
                    pass

        audio_thread = threading.Thread(target=feed_device_audio, daemon=True)
        audio_thread.start()
    else:
        audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)

    speech_recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config,
    )

    speech_recognizer.recognizing.connect(lambda evt: on_recognizing(evt, show_lang))
    speech_recognizer.recognized.connect(lambda evt: on_recognized(evt, show_lang))
    speech_recognizer.canceled.connect(on_canceled)

    speech_recognizer.start_continuous_recognition()

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        audio_stop_event.set()
        speech_recognizer.stop_continuous_recognition()
        if audio_stream:
            try:
                audio_stream.close()
            except Exception:
                pass
        if audio_thread and audio_thread.is_alive():
            audio_thread.join(timeout=1.0)

def speak_sinhala_text(text: str, *, force: bool = False):
    """Speak Sinhala text using Azure TTS"""
    if ((not enable_tts) and not force) or not speech_synthesizer or not text.strip():
        return
    
    try:
        print("🔊 කථනය කරමින්...", end="", flush=True)
        
        # Clean the text for speech
        clean_text = normalize_sinhala_text(text)
        
        # Create SSML for better pronunciation
        ssml = f"""
        <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="si-LK">
            <voice name="{os.getenv('AZURE_TTS_VOICE', 'si-LK-ThiliniNeural')}">
                <prosody rate="medium" pitch="medium">
                    {clean_text}
                </prosody>
            </voice>
        </speak>
        """
        
        # Synthesize speech
        result = speech_synthesizer.speak_ssml_async(ssml).get()
        
        # Clear the speaking indicator
        print("\r" + " " * 20 + "\r", end="", flush=True)
        
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            print("🎵 කථනය සම්පූර්ණයි", flush=True)
        else:
            print(f"❌ TTS දෝෂයක්: {result.reason}")
            
    except Exception as e:
        print(f"\r❌ කථන දෝෂයක්: {str(e)}")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Azure Speech-to-Text with Sinhala AI responses')
    default_rate = int(os.getenv('AZURE_INPUT_RATE', '16000'))
    default_channels = int(os.getenv('AZURE_INPUT_CHANNELS', '1'))
    parser.add_argument('--key', help='Azure Speech key (or set AZURE_SPEECH_KEY env var)')
    parser.add_argument('--region', help='Azure Speech region (or set AZURE_SPEECH_REGION env var)')
    parser.add_argument('--device', type=int, help='Audio device ID (optional)')
    parser.add_argument('--list-devices', action='store_true', help='List available audio devices')
    parser.add_argument('--rate', type=int, default=default_rate, help='Sample rate in Hz when using a custom mic (default: 16000)')
    parser.add_argument('--channels', type=int, default=default_channels, help='Channel count when using a custom mic (default: 1)')
    
    args = parser.parse_args()
    
    if args.list_devices:
        pa = pyaudio.PyAudio()
        list_devices(pa)
        pa.terminate()
        return
    
    # Get configuration from environment or command line
    key = args.key or os.getenv('AZURE_SPEECH_KEY')
    region = args.region or os.getenv('AZURE_SPEECH_REGION')
    lang_codes = os.getenv('AZURE_SPEECH_LANGS', 'si-LK')
    
    if not key or not region:
        print("❌ Azure Speech key සහ region අවශ්‍යයි!")
        print("💡 .env ගොනුවේ AZURE_SPEECH_KEY සහ AZURE_SPEECH_REGION සකසන්න")
        return
    
    try:
        # Fixed: Remove the 'languages' parameter, use 'lang_codes' instead
        stream_transcribe(
            key=key,
            region=region,
            lang_codes=lang_codes,
            device_id=args.device,
            show_lang=True,
            rate=args.rate,
            channels=args.channels,
        )
    except KeyboardInterrupt:
        print("\n\n🛑 පරිශීලකයා විසින් නතර කරන ලදී")
        print("👋 ආයුබෝවන්!")
    except Exception as e:
        print(f"\n❌ දෝෂයක්: {str(e)}")

if __name__ == "__main__":
    main()
