---
name: m5-onboard
description: Provision, flash, and configure M5Stack and ESP32 microcontroller boards including Cardputer, Core, CoreS3, and Stick. Covers USB serial port enumeration, ROM download mode entry, esptool flashing parameters, MicroPython file deployment via mpremote, and peripheral verification. Use when provisioning or resetting an M5Stack or ESP32 device, flashing new firmware over serial, or setting up on-device MicroPython applications.
license: MIT
version: 0.1.0
---

# M5Stack & ESP32 Device Provisioning

Provisioning microcontroller boards over USB serial requires coordinating the bootloader state, matching baud rates, and selecting the correct flash offsets for the target SoC variant (ESP32 vs ESP32-S3). Flashing the wrong variant image or interrupting write cycles leaves the board in a boot loop.

```bash
# Verify USB connection and read chip information
esptool.py --port COM3 chip_id
```

Detailed board hardware specifications, USB vendor and product IDs, and flash offset maps are documented in [references/board-variants.md](references/board-variants.md).

## Provisioning Workflow

1. **Port Identification**: Identify the active serial port associated with the USB bridge (CP2104, CH9102) or native ESP32-S3 USB CDC interface.
2. **Download Mode Entry**: On native-USB boards such as Cardputer-Adv, software reset cannot always force the ROM bootloader into download mode. The user enters download mode physically by holding the `G0` button while toggling power or reset.
3. **Firmware Deployment**: Erase flash if changing partition schemes, then write the target firmware image at offset `0x0` using `esptool.py`.
4. **Application Payload**: Push user Python scripts (such as `main.py` and driver libraries) into the internal flash filesystem using `mpremote`.
5. **Reboot and Smoke Test**: Reset the device into normal execution mode and inspect serial console output for unhandled exceptions or boot crashes.

## Firmware Flashing

```bash
# Erase old partition table and flash image
esptool.py --chip esp32s3 --port /dev/ttyACM0 erase_flash

# Write composite MicroPython or UIFlow image
esptool.py --chip esp32s3 --port /dev/ttyACM0 --baud 921600 write_flash -z 0x0 firmware.bin
```

If communication fails at 921600 baud due to poor USB cabling or hub interference, drop back to 115200 baud for stable flashing.

## Application Deployment with mpremote

The `mpremote` utility provides access to the MicroPython REPL and filesystem over serial without requiring third-party IDE extensions.

```bash
# List files on device root
mpremote connect /dev/ttyACM0 fs ls

# Copy local application to main startup script
mpremote connect /dev/ttyACM0 cp main.py :main.py

# Open interactive REPL session
mpremote connect /dev/ttyACM0 repl
```

## Troubleshooting Common Failures

- **Device not recognized**: Check whether the USB cable is power-only. Data cables enumerate with a vendor ID in device manager or `dmesg`.
- **A fatal error occurred: Failed to connect to ESP32**: The chip is actively executing application code rather than waiting in the bootloader. Re-enter download mode by pulling GPIO0 low during reset.
- **Boot loop after flashing**: Verify whether the firmware image was built for octal (OPI) or quad (QPI) PSRAM matching the specific board revision.

## Honest limits

This workflow provisions firmware and copies scripts over USB. It cannot detect physical hardware damage such as blown I/O pins, defective lithium-polymer battery cells, or broken I2C pull-up resistors on external Grove sensor ports. Testing peripheral functionality requires running dedicated on-device diagnostics against display, speaker, and I2C buses.
