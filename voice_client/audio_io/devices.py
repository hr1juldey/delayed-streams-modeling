"""Audio device listing utilities."""

from typing import Any

import sounddevice as sd


def list_input_devices() -> list[dict[str, Any]]:
    """List available audio input devices.

    Returns:
        List of device dictionaries with keys:
        - index: device index
        - name: device name
        - channels: maximum input channels
        - sample_rate: default sample rate
    """
    devices = []
    device_list = sd.query_devices()
    for i, info in enumerate(device_list):
        # Handle both dict-like and object-like device info
        if isinstance(info, dict):
            max_input = info.get("max_input_channels", 0)
            name = info.get("name", f"Device {i}")
            samplerate = info.get("default_samplerate", 48000)
        else:
            max_input = info.max_input_channels
            name = info.name
            samplerate = info.default_samplerate

        if max_input > 0:
            devices.append(
                {
                    "index": i,
                    "name": name,
                    "channels": max_input,
                    "sample_rate": samplerate,
                }
            )
    return devices


def list_output_devices() -> list[dict[str, Any]]:
    """List available audio output devices.

    Returns:
        List of device dictionaries with keys:
        - index: device index
        - name: device name
        - channels: maximum output channels
        - sample_rate: default sample rate
    """
    devices = []
    device_list = sd.query_devices()
    for i, info in enumerate(device_list):
        # Handle both dict-like and object-like device info
        if isinstance(info, dict):
            max_output = info.get("max_output_channels", 0)
            name = info.get("name", f"Device {i}")
            samplerate = info.get("default_samplerate", 48000)
        else:
            max_output = info.max_output_channels
            name = info.name
            samplerate = info.default_samplerate

        if max_output > 0:
            devices.append(
                {
                    "index": i,
                    "name": name,
                    "channels": max_output,
                    "sample_rate": samplerate,
                }
            )
    return devices
