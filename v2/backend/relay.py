#!/usr/bin/env python3
"""
Relay server for the GSM touch keychains, v2 (standard library only, Python 3.9+).

Each keychain keeps one TCP connection open over 1NCE GPRS and speaks the line
protocol in firmware/keychain/protocol.h (unchanged from v1):

  device -> server: HELLO <id> <token> | PING <mV> [<free mem>] | BUZZ <seq>
                    | TAP <seq> <d1>,<d2>,... | ACK <mid>
  server -> device: WELCOME | DENIED | PONG | OK <seq> | ERR <seq>
                    | MSG <mid> BUZZ | MSG <mid> TAP <d1>,<d2>,...

Messages for a keychain are queued (and persisted to disk) until that keychain
ACKs them. They are delivered one at a time, resent if not ACKed in time, and
dropped after queue_ttl_s.

v2 additions:
  - read-only status page (JSON) on status_listen:status_port, default 127.0.0.1:8080:
      GET /status  -> who is online, battery, queue, message counters
      GET /health  -> "ok"
  - battery_log (CSV: unix time, device, mV) so battery life can be measured

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

# rough 1S LiPo resting-voltage curve (mV -> %), only for the status page
LIPO_CURVE = [(3400, 0), (3600, 10), (3700, 30), (3800, 55), (3900, 70), (4000, 82),
              (4100, 95), (4150, 100)]


def battery_pct(mv):
    if mv is None:
        return None
    if mv <= LIPO_CURVE[0][0]:
        return 0
    for (v0, p0), (v1, p1) in zip(LIPO_CURVE, LIPO_CURVE[1:]):
        if mv <= v1:
            return round(p0 + (p1 - p0) * (mv - v0) / (v1 - v0))
    return 100


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
        self.battery_log = cfg.get("battery_log")
        self.status_listen = cfg.get("status_listen", "127.0.0.1")
        self.status_port = cfg.get("status_port", 8080)       # null disables the page
        self.started = time.time()
        self.conns = {}                                   # dev -> Conn
        self.queue = {d: [] for d in self.devices}        # dev -> [{"mid","body","t"}]
        self.next_mid = {d: 1 for d in self.devices}
        self.last_seq = {}                                # dev -> (seq, t)
        self.stats = {d: {"sent": 0, "delivered": 0} for d in self.devices}
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
            self.stats[dev]["delivered"] += 1
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
                self.stats[c.dev]["disconnected_at"] = time.time()
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
        self.stats[dev]["connected_since"] = time.time()
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
                st["free_mem"] = int(parts[2])
            self._log_battery(dev, int(parts[1]))
            log.info("dev %s ping: battery %s mV, free mem %s B, gap %s",
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
                st["sent"] += 1
                log.info("dev %s -> dev %s: %s", dev, partner, body)
                self.enqueue(partner, body)
            c.send("OK %d" % seq)
        elif cmd == "ACK" and len(parts) == 2 and parts[1].isdigit():
            self.ack(dev, int(parts[1]))
        else:
            log.warning("dev %s: unknown line %r", dev, line[:60])

    # ---------------------------------------------------------------- battery log + status
    def _log_battery(self, dev, mv):
        if not self.battery_log:
            return
        try:
            with open(self.battery_log, "a") as f:
                f.write("%d,%s,%d\n" % (time.time(), dev, mv))
        except OSError as e:
            log.warning("battery log: %s", e)

    def status(self):
        now = time.time()
        out = {"time": int(now), "uptime_s": int(now - self.started), "devices": {}}
        for d, v in self.devices.items():
            st = self.stats[d]

            def ts(k):
                return int(st[k]) if k in st else None
            out["devices"][d] = {
                "name": v.get("name", ""),
                "partner": str(v["partner"]),
                "online": d in self.conns,
                "connected_since": ts("connected_since") if d in self.conns else None,
                "last_seen": ts("last_seen"),
                "last_ping": ts("last_ping"),
                "disconnected_at": ts("disconnected_at"),
                "battery_mv": st.get("mv"),
                "battery_pct_rough": battery_pct(st.get("mv")),
                "free_mem": st.get("free_mem"),
                "queued_for_it": len(self.queue[d]),
                "sent": st["sent"],
                "delivered_to_it": st["delivered"],
            }
        return out

    async def _http(self, reader, writer):
        """Minimal read-only HTTP/1.0 responder for /status and /health."""
        try:
            req = await asyncio.wait_for(reader.readline(), 5)
            for _ in range(50):                                  # skip the headers
                h = await asyncio.wait_for(reader.readline(), 5)
                if h in (b"\r\n", b"\n", b""):
                    break
            parts = req.decode("ascii", "replace").split()
            path = parts[1].split("?")[0] if len(parts) >= 2 else ""
            if len(parts) < 2 or parts[0] != "GET":
                code, ctype, body = "405 Method Not Allowed", "text/plain", "GET only\n"
            elif path == "/health":
                code, ctype, body = "200 OK", "text/plain", "ok\n"
            elif path in ("/", "/status"):
                code, ctype = "200 OK", "application/json"
                body = json.dumps(self.status(), indent=1) + "\n"
            else:
                code, ctype, body = "404 Not Found", "text/plain", "not found\n"
            data = body.encode()
            writer.write(("HTTP/1.0 %s\r\nContent-Type: %s\r\nContent-Length: %d\r\n"
                          "Cache-Control: no-store\r\nConnection: close\r\n\r\n"
                          % (code, ctype, len(data))).encode() + data)
            await writer.drain()
        except (asyncio.TimeoutError, ConnectionError, ValueError):
            pass
        finally:
            writer.close()

    async def serve(self, host, port):
        server = await asyncio.start_server(self.handle, host, port, limit=MAX_LINE)
        self._hk = asyncio.ensure_future(self.housekeeping())
        self.status_server = None
        if self.status_port is not None:
            self.status_server = await asyncio.start_server(
                self._http, self.status_listen, self.status_port, limit=4096)
            log.info("status page on http://%s:%s/status", self.status_listen,
                     self.status_server.sockets[0].getsockname()[1])
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
