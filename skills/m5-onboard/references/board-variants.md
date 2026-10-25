# M5Stack & ESP32 Hardware Variant Reference

Specifications, USB identifiers, and pin mappings for common ESP32 and M5Stack boards.

## Device Identification Matrix

| Board Model | Chipset | USB Interface | Default Flash Size | Boot Pin (Download Mode) |
|---|---|---|---|---|
| **Cardputer-Adv** | ESP32-S3 (Dual-core Xtensa) | Native USB-JTAG (303a:1001) | 8 MB / 16 MB Octal PSRAM | Hold `G0` button during power/reset |
| **Cardputer (v1)** | ESP32-S3 | Native USB / CH9102 bridge | 8 MB | Hold `G0` button during reset |
| **M5Core (Basic/Gray)**| ESP32-D0WDQ6-V3 | CP2104 or CH9102 bridge | 16 MB | Automatic DTR/RTS reset |
| **M5Core2 / CoreS3** | ESP32-D0WDQ6-V3 / S3 | CP2104 / Native USB | 16 MB | Hold power button or G0 pin |
| **M5StickC Plus / Plus2**| ESP32-PICO / S3 | CH552 / Native USB | 4 MB / 8 MB | Hold `G0` (front button) during reset |

## USB Detection and Port Enumeration

On Windows:
```powershell
Get-CimInstance Win32_SerialPort | Select-Object DeviceID, Description, PNPDeviceID
```

On Linux / macOS:
```bash
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
```

ESP32-S3 devices using native USB appear as CDC-ACM devices (`/dev/ttyACM0` or `COMx`). Standard bridge chips (CP210x, CH9102) appear as `/dev/ttyUSB0`.

## Flashing Parameters with esptool

```bash
# Erase flash before full firmware provisioning
esptool.py --port /dev/ttyUSB0 erase_flash

# Write MicroPython / UIFlow binary image
esptool.py --port /dev/ttyUSB0 --chip esp32s3 write_flash -z 0x0 firmware.bin
```

## MicroPython File Transfer (mpremote / ampy)

```bash
# Upload application scripts directly to device flash storage
mpremote connect /dev/ttyUSB0 cp app.py :main.py
mpremote connect /dev/ttyUSB0 repl
```
