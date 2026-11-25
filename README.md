# GSM touch keychain (pair)

Press the button on one keychain and the other one vibrates and blinks, over 2G (SIM800L).

**Current version: [`v2/`](v2/README.md)**, the module build: XIAO ESP32-C3 + SIM800L + 802530 LiPo, no custom PCB.
It has the parts list, schematic, case STLs/G-code and the relay backend.

v1 (custom PCB, ATtiny85):

- `hardware/` — carrier PCB (KiCad 10), parts list, cost estimate, gerbers, assembly files. Start at [hardware/README.md](hardware/README.md).
- `firmware/` — ATtiny85 firmware (1NCE GPRS → relay server), host unit tests.
- `server/` — relay server (Python, no dependencies) + tests + fake keychain for bring-up.
- `enclosure/` — 3D-printed case (OpenSCAD), heart perfboard layout, STLs and ready-to-print
  Ender-3 V2/Pro G-code.
- `.mcp.json` — project-scoped KiCad MCP servers (`mcp-server-kicad`: PCB + project tools).
