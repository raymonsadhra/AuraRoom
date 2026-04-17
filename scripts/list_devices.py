"""
List camera and microphone devices for AuraRoom setup.

What this script does:
- Probes common OpenCV camera indices and lists available sounddevice inputs.

How it contributes to AuraRoom:
- Helps quickly choose the correct CAMERA_INDEX and AUDIO_DEVICE_INDEX values
  for hackathon setup on Raspberry Pi or laptop.

Hardware interaction:
- Directly tests camera and mic device availability.
"""

from __future__ import annotations

try:
    import cv2
except Exception:
    cv2 = None  # type: ignore

try:
    import sounddevice as sd
except Exception:
    sd = None  # type: ignore


def list_cameras(max_index: int = 6) -> None:
    print("\n=== Camera Probe (OpenCV) ===")
    if cv2 is None:
        print("OpenCV not installed.")
        return

    found = False
    for idx in range(max_index + 1):
        cap = cv2.VideoCapture(idx)
        ok, frame = cap.read()
        if ok and frame is not None:
            h, w = frame.shape[:2]
            print(f"Index {idx}: OK ({w}x{h})")
            found = True
        cap.release()

    if not found:
        print("No camera detected in tested range.")


def list_audio_inputs() -> None:
    print("\n=== Audio Input Devices (sounddevice) ===")
    if sd is None:
        print("sounddevice not installed.")
        return

    try:
        devices = sd.query_devices()
        default_input, _default_output = sd.default.device
    except Exception as exc:
        print(f"Could not query audio devices: {exc}")
        return

    found = False
    for i, dev in enumerate(devices):
        if dev.get("max_input_channels", 0) > 0:
            marker = " (default)" if i == default_input else ""
            print(
                f"Index {i}: {dev['name']} | channels={dev['max_input_channels']}"
                f" | default_samplerate={dev['default_samplerate']}{marker}"
            )
            found = True

    if not found:
        print("No audio input devices found.")


def main() -> None:
    list_cameras()
    list_audio_inputs()


if __name__ == "__main__":
    main()
