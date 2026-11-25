# Keychain firmware (ATtiny85 + SIM800L, 1NCE data)

`keychain/keychain.ino` — Arduino sketch for ATTinyCore. Compiled and size-checked:
**7.4 KB of 8 KB flash, 324 B of 512 B RAM** (188 B left for the stack; the measured
worst case is reported live, see "Stack check" below).

## What it does

| You do | Your keychain | Partner's keychain |
|---|---|---|
| short press (< 0.5 s) | 2 short blips = delivered to server | vibrates + heart glows, 3 pulses / 1.5 s |
| long press, or a tapped rhythm (up to 10 presses, gesture ends 1.5 s after the last release) | 2 short blips | replays your exact rhythm |
| anything, but sending failed twice | one long 0.8 s buzz | — |
| power on | 1 blip | — |

If the partner is out of coverage or its battery is flat, the server keeps the message
(up to 7 days by default) and delivers it as soon as the partner reconnects.

## How it works

- **Link:** the SIM800L attaches to 2G GPRS on the 1NCE APN `iot.1nce.net` and keeps one
  TCP connection to your relay server (`/server`). The line protocol is documented in
  `keychain/protocol.h`.
- **Receiving:** incoming data is held *inside the modem* (`AT+CIPRXGET=1`). The modem's
  notification wakes the ATtiny85 through the UART pin, then the ATtiny fetches the data
  with `AT+CIPRXGET=2`. Nothing is lost during wake-up, and the RING pin isn't needed.
- **Sleep:** the ATtiny85 is in power-down nearly all the time and the SIM800L sleeps
  between transfers (`AT+CSCLK=2`).
- **Heartbeat:** every `HEARTBEAT_MINUTES` (default 5) it sends `PING <battery mV> <free
  stack>`. That keeps the operator's NAT mapping open, so the server can push to the
  keychain, and it detects dead links. If there's no `PONG`, it reconnects.
- **Recovery:** reconnects back off (8 s → 30 s → 1 min → 5 min → 10 min). Every 3rd failure
  pulses the SIM800L's RST pin (PB3, open-drain via 1 kΩ). A software watchdog resets the
  ATtiny85 if the firmware ever stops making progress for ~6 min.
- **Delivery:** each message is acknowledged end-to-end (`OK` from the server to the
  sender, `ACK` from the receiver). Duplicates caused by lost acknowledgements are filtered
  on both sides.

## Configure

Edit `keychain/config.h`:

- `SERVER_HOST`, `SERVER_PORT`: your relay server.
- `DEVICE_TOKEN` for IDs 1 and 2. Generate each with
  `python3 -c "import secrets; print(secrets.token_urlsafe(24))"` and put the same values in
  `server/config.json`.
- `DEVICE_ID`: **1** for keychain A, **2** for keychain B.
- `HEARTBEAT_MINUTES`, `DRIVE_PWM`, gesture timings: optional.

## Build and flash

Do this **before the SIM800L is soldered on** (see `hardware/README.md`, "Assembly order").
A 5 V programmer must never power the SIM800L.

```sh
brew install arduino-cli          # or the Arduino IDE with ATTinyCore
arduino-cli config add board_manager.additional_urls http://drazzy.com/package_drazzy.com_index.json
arduino-cli core update-index && arduino-cli core install ATTinyCore:avr

FQBN="ATTinyCore:avr:attinyx5:chip=85,clock=8internal,bod=disable,millis=enabled"
PORT=/dev/cu.usbmodem1101         # the Arduino running the ArduinoISP sketch

# once per chip: sets the fuses (8 MHz internal, BOD off)
arduino-cli burn-bootloader -b "$FQBN" -P arduinoasisp -p "$PORT"
# keychain A (DEVICE_ID 1 in config.h), then change to 2 and repeat for keychain B
arduino-cli compile -b "$FQBN" firmware/keychain
arduino-cli upload  -b "$FQBN" -P arduinoasisp -p "$PORT" firmware/keychain
```

ISP wiring to the carrier's pads: `RST`→Arduino D10, `MOSI`→D11, `MISO`→D12, `SCK`→D13,
`GND`→GND, `VCC`→5 V **only if the SIM800L isn't fitted yet**.

## Tests

```sh
cc -Wall -Wextra -Werror -o /tmp/test_protocol firmware/test/test_protocol.c && /tmp/test_protocol
```

These cover the line parser, the TAP formatter, line-length limits and gesture
classification (the same header the firmware uses).

## Bring-up checklist

1. Start the relay (`server/README.md`), then power keychain A.
2. Run `python3 server/fake_device.py --host <server> --id 2 --token <token 2>` to play the
   part of keychain B. `b` sends a buzz to A, and a press on A shows up as `MSG … BUZZ`.
3. In the server log, check that each `ping:` line shows a sensible battery voltage and
   **free stack ≥ ~30 B**. Check the gap between pings too: if pushes to the keychain stop
   working after a while, the operator's NAT drops idle connections sooner than your
   heartbeat, so lower `HEARTBEAT_MINUTES`.
4. If the modem never answers: the ATtiny85's internal 8 MHz oscillator can be a few % off,
   which garbles 9600 baud. Calibrate `OSCCAL` (ATTinyCore ships a tuning example) or try
   another chip.

## Battery life

**Not measured yet.** Staying online costs more than the original missed-call design,
because every heartbeat wakes the radio. The longer the heartbeat interval, the longer
the battery lasts. Measure with the real 1NCE NAT timeout and pick the longest interval
that still delivers reliably. The server log (ping gaps, battery mV) is the tool for that.
