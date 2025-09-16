import pyaudio


def main():
    pa = pyaudio.PyAudio()
    print("Input devices:")
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if int(info.get("maxInputChannels", 0)) > 0:
            name = info.get("name", "?")
            ch = int(info.get("maxInputChannels", 0))
            rate = int(info.get("defaultSampleRate", 0))
            print(f"[{i}] {name} — {ch} ch @ {rate} Hz")
    pa.terminate()


if __name__ == "__main__":
    main()

