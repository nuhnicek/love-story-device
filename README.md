# GSM touch keychain (pair)

Press the button on one keychain and the other one vibrates and blinks, over 2G (SIM800L).

- `hardware/` — carrier PCB + heart LED board (KiCad 10), parts list, cost estimate,
  gerbers, assembly files. Start at [hardware/README.md](hardware/README.md).
- `firmware/` — ATtiny85 firmware (1NCE GPRS → relay server), host unit tests.
- `server/` — relay server (Python, no dependencies) + tests + fake keychain for bring-up.
- `.mcp.json` — project-scoped KiCad MCP servers (`mcp-server-kicad`: PCB + project tools).
