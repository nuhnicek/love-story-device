# Programming the v3 board

Two stages:

1. **Once per board, over SWD:** the bootloader (MCUboot) and the first app go in through the 5 SWD pads. A Raspberry Pi Pico works as the probe.
2. **Every update after that, over USB-C:** MCUboot accepts new firmware over the on-board CP2102N, like an Arduino.

## 1. DIY SWD probe from a Raspberry Pi Pico (~€5)

### Turn the Pico into a probe

1. Download `debugprobe_on_pico.uf2` (or `debugprobe_on_pico2.uf2` for a Pico 2) from
   <https://github.com/raspberrypi/debugprobe/releases>.
2. Hold **BOOTSEL** on the Pico and plug it into USB. A drive called `RPI-RP2` appears.
3. Drag the `.uf2` file onto it. The Pico reboots as a CMSIS-DAP probe ("Debugprobe on Pico").

### Wiring

The SWD pads are on the **bottom** of the board, in a column next to the SIM holder.
Looking at the bottom side, top to bottom: **CK, IO, RST, VT, GND** (1.8 mm pitch).

```
 Raspberry Pi Pico                       keychain v3 (bottom side)
 ┌──────────────┐
 │ GP2  (pin 4) ├──[100 Ω]──────────────  CK   (SWDCLK)
 │ GP3  (pin 5) ├──[100 Ω]──────────────  IO   (SWDIO)
 │ GND  (pin 3) ├───────────────────────  GND
 │              │                         RST  (optional, see below)
 │              │                         VT   (leave open, or use it to check the board is powered: 3.0 V)
 └──────────────┘
```

- **100 Ω in series** on CK and IO. The Pico drives 3.3 V and the nRF9151 runs its I/O at 3.0 V. The resistors limit the current into the protection diodes. Leave them out only if you have nothing at hand; it usually works without them, but it isn't nice.
- **Power the keychain from its own battery or from USB-C**, never from the Pico. The probe only talks to the chip.
- **RST** isn't needed for normal flashing. If the chip ever won't respond, briefly touch RST to GND while the tool connects.
- Pico pin numbers are the physical pins on the board's edge: pin 3 is a GND, pin 4 is GP2, pin 5 is GP3.

For more than one or two boards, make a small clip with **5 pogo pins (P75 type, 1.8 mm pitch)** that presses onto the pads. Otherwise tack-solder 5 thin wires and remove them afterwards.

### Software (pyOCD)

```sh
pip install pyocd
pyocd list                              # the Pico shows up as "Debugprobe on Pico (CMSIS-DAP)"
pyocd pack find nrf91                   # find the Nordic device pack for the nRF9151
pyocd pack install <name from the list>
```

The nRF Connect SDK builds the firmware (see `firmware/`, still to come). To flash it:

```sh
west build -b <our board> --sysbuild app        # app + MCUboot in one image
west flash --runner pyocd                       # or: pyocd flash -t <nrf9151 target> build/merged.hex
```

**A brand-new chip may be read-protected (APPROTECT).** Run a full chip erase first. It also unlocks the chip:

```sh
pyocd erase --chip -t <nrf9151 target>
```

**Modem firmware:** the nRF9151 ships with modem firmware already installed, so the first flash doesn't need it. Later modem updates go through the app (delta update over LTE, or a full update over USB-C), not through the probe.

### If the Pico doesn't work

The nRF9151 is newer than pyOCD's built-in nRF91 support. If pyOCD can't find the target or can't unlock the chip, use a **SEGGER J-Link EDU Mini** (~€60). With it, Nordic's own tools just work:

```sh
nrfutil device recover        # unlock + erase
west flash                    # default runner = J-Link
```

## 2. Updates over USB-C (no probe)

After the first SWD flash, MCUboot is on the chip:

- Plugging in USB-C powers the CP2102N USB-serial chip. It shows up as `/dev/tty.usbserial-*` (macOS) or `COMx` (Windows; driver: Silicon Labs CP210x).
- When the serial port opens, DTR/RTS reset the nRF9151 through Q2, the auto-reset transistor. MCUboot then waits about 0.5 s for an upload.
- Upload:

```sh
# one-time: go install github.com/apache/mynewt-mcumgr-cli/mcumgr@latest   (or use nrfutil mcu-manager)
mcumgr --conntype serial --connstring "dev=/dev/tty.usbserial-XXXX,baud=115200" image upload build/app/zephyr/zephyr.signed.bin
mcumgr --conntype serial --connstring "dev=/dev/tty.usbserial-XXXX,baud=115200" reset
```

- **Forced recovery:** hold the side button while resetting (or plugging in USB). MCUboot then stays in upload mode until a new image arrives.
- The **log output** of the running firmware comes out of the same USB-C port (115200 baud, any serial terminal).
