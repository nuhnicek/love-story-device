#!/usr/bin/env python3
"""
Pretend to be a keychain, so you can test the real one before its partner exists.

  python3 fake_device.py --host relay.example.com --id 2 --token <token of keychain 2>

Commands:  b = BUZZ    t 30,20,60 = TAP (10 ms units, odd count)    p = PING    q = quit
Incoming MSG lines are printed and ACKed automatically.
"""
import argparse
import asyncio
import sys


async def main(a):
    r, w = await asyncio.open_connection(a.host, a.port)
    w.write(("HELLO %s %s\n" % (a.id, a.token)).encode())
    await w.drain()
    seq = 0

    async def reader():
        while True:
            line = await r.readline()
            if not line:
                print("[connection closed]")
                return
            s = line.decode().strip()
            print("<", s)
            if s.startswith("MSG "):
                mid = s.split()[1]
                w.write(("ACK %s\n" % mid).encode())
                await w.drain()
                print("> ACK", mid)

    rt = asyncio.ensure_future(reader())
    loop = asyncio.get_running_loop()
    while not rt.done():
        cmd = (await loop.run_in_executor(None, sys.stdin.readline)).strip()
        if cmd in ("q", ""):
            break
        seq = seq % 999 + 1
        if cmd == "b":
            out = "BUZZ %d" % seq
        elif cmd.startswith("t "):
            out = "TAP %d %s" % (seq, cmd[2:].strip())
        elif cmd == "p":
            out = "PING 4000 100"
        else:
            print("? b | t 30,20,60 | p | q")
            continue
        print(">", out)
        w.write((out + "\n").encode())
        await w.drain()
    w.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7070)
    ap.add_argument("--id", required=True)
    ap.add_argument("--token", required=True)
    asyncio.run(main(ap.parse_args()))
