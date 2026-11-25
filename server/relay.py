#!/usr/bin/env python3
"""
Relay server for the GSM touch keychains (standard library only, Python 3.9+).

Each keychain keeps one TCP connection open over 1NCE GPRS and speaks the line
protocol in firmware/keychain/protocol.h:

  device -> server: HELLO <id> <token> | PING <mV> [<free stack>] | BUZZ <seq>
                    | TAP <seq> <d1>,<d2>,... | ACK <mid>
  server -> device: WELCOME | DENIED | PONG | OK <seq> | ERR <seq>
                    | MSG <mid> BUZZ | MSG <mid> TAP <d1>,<d2>,...

Messages for a keychain are queued (and persisted to disk) until that keychain
ACKs them. They are delivered one at a time, resent if not ACKed in time, and
dropped after queue_ttl_s.

  python3 relay.py --config config.json [--state state.json]
"""
import argparse
import asyncio
import hmac
import json
import logging
import os
import re
import time

MAX_ID = 999          # seq / mid wrap 1..999 (bounded line length on the ATtiny85)
MAX_TAPS = 19         # 10 presses + 9 gaps
MAX_LINE = 128
TAP_RE = re.compile(r"^[0-9]{1,3}(,[0-9]{1,3}){0,%d}$" % (MAX_TAPS - 1))

log = logging.getLogger("relay")


def valid_taps(s):
    if not TAP_RE.match(s):
        return False
    vals = [int(v) for v in s.split(",")]
    return len(vals) % 2 == 1 and all(1 <= v <= 255 for v in vals)


class Conn:
    def __init__(self, reader, writer):
        self.reader, self.writer = reader, writer
        self.dev = None
        self.inflight = None      # (mid, sent_at)
        self.peer = writer.get_extra_info("peername")

    def send(self, line):
        log.debug("-> %s %s", self.dev, line)
        self.writer.write((line + "\n").encode())

    def close(self):
        try:
            self.writer.close()
        except Exception:
            pass


class Relay:
    def __init__(self, cfg, state_path=None):
        self.devices = {str(k): v for k, v in cfg["devices"].items()}
        for d, v in self.devices.items():
            if str(v["partner"]) not in self.devices:
                raise ValueError("device %s: partner %s not configured" % (d, v["partner"]))
        self.ttl = cfg.get("queue_ttl_s", 7 * 86400)
        self.resend_s = cfg.get("resend_s", 60)
        self.idle_s = cfg.get("idle_timeout_s", 1200)
        self.hello_s = cfg.get("hello_timeout_s", 30)
        self.state_path = state_path
        self.conns = {}                                   # dev -> Conn
        self.queue = {d: [] for d in self.devices}        # dev -> [{"mid","body","t"}]
        self.next_mid = {d: 1 for d in self.devices}
        self.last_seq = {}                                # dev -> (seq, t)
        self.stats = {d: {} for d in self.devices}
        self._load()

    # ---------------------------------------------------------------- state
    def _load(self):
        if not self.state_path or not os.path.exists(self.state_path):
            return
        with open(self.state_path) as f:
            st = json.load(f)
        for d in self.devices:
            self.queue[d] = st.get("queue", {}).get(d, [])
            self.next_mid[d] = st.get("next_mid", {}).get(d, 1)
        log.info("state loaded: %s", {d: len(q) for d, q in self.queue.items()})

    def _save(self):
        if not self.state_path:
            return
        tmp = self.state_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"queue": self.queue, "next_mid": self.next_mid}, f)
        os.replace(tmp, self.state_path)

    # ---------------------------------------------------------------- delivery
    def _new_mid(self, dev):
        mid = self.next_mid[dev]
        self.next_mid[dev] = mid % MAX_ID + 1
        return mid

    def enqueue(self, dev, body):
        self.queue[dev].append({"mid": self._new_mid(dev), "body": body, "t": time.time()})
        self._save()
        self.deliver(dev)

    def deliver(self, dev, force=False):
        c = self.conns.get(dev)
        q = self.queue.get(dev)
        if not c or not q:
            return
        if c.inflight and not force:
            return
        m = q[0]
        c.inflight = (m["mid"], time.monotonic())
        c.send("MSG %d %s" % (m["mid"], m["body"]))

    def ack(self, dev, mid):
        c = self.conns.get(dev)
        q = self.queue[dev]
        if q and q[0]["mid"] == mid:
            q.pop(0)
            self._save()
            log.info("dev %s acked mid %d (%d left)", dev, mid, len(q))
        if c and c.inflight and c.inflight[0] == mid:
            c.inflight = None
        self.deliver(dev)

    async def housekeeping(self, every=1.0):
        while True:
            await asyncio.sleep(every)
            now = time.time()
            changed = False
            for dev, q in self.queue.items():
                keep = [m for m in q if now - m["t"] < self.ttl]
                if len(keep) != len(q):
                    log.warning("dev %s: dropped %d expired message(s)", dev, len(q) - len(keep))
                    self.queue[dev] = keep
                    changed = True
            if changed:
                self._save()
            for dev, c in list(self.conns.items()):
                if c.inflight and time.monotonic() - c.inflight[1] > self.resend_s:
                    log.info("dev %s: resending mid %d", dev, c.inflight[0])
                    self.deliver(dev, force=True)
                elif not c.inflight:
                    self.deliver(dev)

    # ---------------------------------------------------------------- connection
    async def handle(self, reader, writer):
        c = Conn(reader, writer)
        try:
            line = await asyncio.wait_for(reader.readline(), self.hello_s)
            if not self._hello(c, line):
                c.send("DENIED")
                await writer.drain()
                return
            while True:
                line = await asyncio.wait_for(reader.readline(), self.idle_s)
                if not line:
                    break
                self._line(c, line.decode("ascii", "replace").strip())
                await writer.drain()
        except asyncio.TimeoutError:
            log.info("dev %s %s: timeout, closing", c.dev, c.peer)
        except (ConnectionError, asyncio.IncompleteReadError, ValueError) as e:
            log.info("dev %s %s: %s", c.dev, c.peer, e)
        finally:
            if c.dev and self.conns.get(c.dev) is c:
                del self.conns[c.dev]
                log.info("dev %s disconnected", c.dev)
            c.close()

    def _hello(self, c, raw):
        parts = raw.decode("ascii", "replace").split()
        if len(parts) != 3 or parts[0] != "HELLO" or parts[1] not in self.devices:
            log.warning("%s: bad hello %r", c.peer, raw[:60])
            return False
        dev = parts[1]
        if not hmac.compare_digest(parts[2].encode(), self.devices[dev]["token"].encode()):
            log.warning("%s: wrong token for dev %s", c.peer, dev)
            return False
        old = self.conns.get(dev)
        if old:
            log.info("dev %s reconnected, dropping old connection", dev)
            old.close()
        c.dev = dev
        self.conns[dev] = c
        log.info("dev %s (%s) connected from %s", dev, self.devices[dev].get("name", ""), c.peer)
        c.send("WELCOME")
        self.deliver(dev)
        return True

    def _line(self, c, line):
        dev = c.dev
        st = self.stats[dev]
        st["last_seen"] = time.time()
        parts = line.split(" ")
        cmd = parts[0]
        partner = str(self.devices[dev]["partner"])
        if cmd == "PING" and 2 <= len(parts) <= 3 and all(p.isdigit() for p in parts[1:]):
            gap = time.time() - st["last_ping"] if "last_ping" in st else None
            st.update(last_ping=time.time(), mv=int(parts[1]))
            if len(parts) == 3:
                st["stack_free"] = int(parts[2])
            log.info("dev %s ping: battery %s mV, free stack %s B, gap %s",
                     dev, parts[1], parts[2] if len(parts) == 3 else "?",
                     "%.0f s" % gap if gap is not None else "-")
            c.send("PONG")
        elif cmd in ("BUZZ", "TAP") and len(parts) >= 2 and parts[1].isdigit():
            seq = int(parts[1])
            if cmd == "BUZZ" and len(parts) == 2:
                body = "BUZZ"
            elif cmd == "TAP" and len(parts) == 3 and valid_taps(parts[2]):
                body = "TAP " + parts[2]
            else:
                log.warning("dev %s: bad %s %r", dev, cmd, line)
                c.send("ERR %d" % seq)
                return
            prev = self.last_seq.get(dev)
            if prev and prev[0] == seq and time.time() - prev[1] < 600:
                log.info("dev %s: duplicate seq %d ignored", dev, seq)
            else:
                self.last_seq[dev] = (seq, time.time())
                log.info("dev %s -> dev %s: %s", dev, partner, body)
                self.enqueue(partner, body)
            c.send("OK %d" % seq)
        elif cmd == "ACK" and len(parts) == 2 and parts[1].isdigit():
            self.ack(dev, int(parts[1]))
        else:
            log.warning("dev %s: unknown line %r", dev, line[:60])

    async def serve(self, host, port):
        server = await asyncio.start_server(self.handle, host, port, limit=MAX_LINE)
        self._hk = asyncio.ensure_future(self.housekeeping())
        return server


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--state", default="state.json")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    with open(a.config) as f:
        cfg = json.load(f)
    relay = Relay(cfg, a.state)

    async def run():
        server = await relay.serve(cfg.get("listen", "0.0.0.0"), cfg.get("port", 7070))
        log.info("listening on %s", ", ".join(str(s.getsockname()) for s in server.sockets))
        async with server:
            await server.serve_forever()

    asyncio.run(run())


if __name__ == "__main__":
    main()
