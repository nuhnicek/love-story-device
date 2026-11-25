"""End-to-end tests for relay.py with simulated keychains.   python3 -m unittest -v test_relay"""
import asyncio
import json
import os
import tempfile
import unittest

import relay

CFG = {
    "devices": {
        "1": {"name": "A", "token": "tokA", "partner": "2"},
        "2": {"name": "B", "token": "tokB", "partner": "1"},
    },
    "resend_s": 0.4,
    "idle_timeout_s": 2,
    "hello_timeout_s": 1,
    "status_port": 0,          # ephemeral port for the tests
}


class Dev:
    """A fake keychain speaking the line protocol."""

    def __init__(self, port):
        self.port = port

    async def connect(self, dev, token, expect="WELCOME"):
        self.r, self.w = await asyncio.open_connection("127.0.0.1", self.port)
        await self.send("HELLO %s %s" % (dev, token))
        if expect:
            self.assert_eq(await self.recv(), expect)
        return self

    async def send(self, line):
        self.w.write((line + "\n").encode())
        await self.w.drain()

    async def recv(self, timeout=2.0):
        line = await asyncio.wait_for(self.r.readline(), timeout)
        return line.decode().strip()

    async def nothing(self, timeout=0.25):
        try:
            line = await asyncio.wait_for(self.r.readline(), timeout)
            return line == b""            # closed counts as "nothing more"
        except asyncio.TimeoutError:
            return True

    @staticmethod
    def assert_eq(a, b):
        if a != b:
            raise AssertionError("%r != %r" % (a, b))

    def close(self):
        self.w.close()


class RelayTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.mkdtemp()
        self.state = os.path.join(self.tmp, "state.json")
        await self.start()

    async def start(self):
        cfg = json.loads(json.dumps(CFG))
        cfg["battery_log"] = os.path.join(self.tmp, "battery.csv")
        self.relay = relay.Relay(cfg, self.state)
        self.server = await self.relay.serve("127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]
        self.status_port = self.relay.status_server.sockets[0].getsockname()[1]

    async def stop(self):
        self.relay._hk.cancel()
        self.relay.status_server.close()
        await self.relay.status_server.wait_closed()
        self.server.close()
        await self.server.wait_closed()

    async def asyncTearDown(self):
        await self.stop()

    async def dev(self, d, token=None, expect="WELCOME"):
        return await Dev(self.port).connect(d, token or CFG["devices"][d]["token"], expect)

    async def http_get(self, path):
        r, w = await asyncio.open_connection("127.0.0.1", self.status_port)
        w.write(("GET %s HTTP/1.1\r\nHost: x\r\n\r\n" % path).encode())
        await w.drain()
        raw = await asyncio.wait_for(r.read(), 2)
        w.close()
        head, _, body = raw.decode().partition("\r\n\r\n")
        return head.split("\r\n")[0], body

    # ------------------------------------------------------------------ tests
    async def test_status_page(self):
        a = await self.dev("1")
        await a.send("PING 3850 20000")
        self.assertEqual(await a.recv(), "PONG")
        await a.send("BUZZ 3")
        self.assertEqual(await a.recv(), "OK 3")
        code, body = await self.http_get("/status")
        self.assertIn("200", code)
        st = json.loads(body)
        d1, d2 = st["devices"]["1"], st["devices"]["2"]
        self.assertTrue(d1["online"])
        self.assertFalse(d2["online"])
        self.assertEqual(d1["battery_mv"], 3850)
        self.assertEqual(d1["sent"], 1)
        self.assertEqual(d2["queued_for_it"], 1)      # B is offline: BUZZ waits for it
        self.assertNotIn("token", body)               # never leak the tokens

    async def test_health_and_404(self):
        code, body = await self.http_get("/health")
        self.assertIn("200", code)
        self.assertEqual(body, "ok\n")
        code, _ = await self.http_get("/nope")
        self.assertIn("404", code)

    async def test_battery_log(self):
        a = await self.dev("2")
        for mv in (4100, 4050):
            await a.send("PING %d" % mv)
            self.assertEqual(await a.recv(), "PONG")
        with open(self.relay.battery_log) as f:
            rows = [r.split(",") for r in f.read().split()]
        self.assertEqual([(r[1], r[2]) for r in rows], [("2", "4100"), ("2", "4050")])

    def test_battery_pct(self):
        self.assertEqual(relay.battery_pct(3300), 0)
        self.assertEqual(relay.battery_pct(4200), 100)
        self.assertEqual(relay.battery_pct(3800), 55)
        self.assertIsNone(relay.battery_pct(None))

    async def test_wrong_token_denied(self):
        d = await self.dev("1", "nope", expect=None)
        self.assertEqual(await d.recv(), "DENIED")
        self.assertTrue(await d.nothing())

    async def test_unknown_device_denied(self):
        d = await Dev(self.port).connect("9", "x", expect=None)
        self.assertEqual(await d.recv(), "DENIED")

    async def test_ping_pong_and_stats(self):
        a = await self.dev("1")
        await a.send("PING 3987 61")
        self.assertEqual(await a.recv(), "PONG")
        self.assertEqual(self.relay.stats["1"]["mv"], 3987)
        self.assertEqual(self.relay.stats["1"]["free_mem"], 61)
        await a.send("PING 3900")                # free-stack field is optional
        self.assertEqual(await a.recv(), "PONG")

    async def test_buzz_delivered_and_acked(self):
        a, b = await self.dev("1"), await self.dev("2")
        await a.send("BUZZ 5")
        self.assertEqual(await a.recv(), "OK 5")
        self.assertEqual(await b.recv(), "MSG 1 BUZZ")
        await b.send("ACK 1")
        await asyncio.sleep(0.05)
        self.assertEqual(self.relay.queue["2"], [])

    async def test_tap_forwarded_verbatim(self):
        a, b = await self.dev("1"), await self.dev("2")
        await b.send("TAP 7 30,20,80")
        self.assertEqual(await b.recv(), "OK 7")
        self.assertEqual(await a.recv(), "MSG 1 TAP 30,20,80")

    async def test_bad_tap_rejected(self):
        a, b = await self.dev("1"), await self.dev("2")
        for bad in ("TAP 1 30,20", "TAP 2 0", "TAP 3 256", "TAP 4 1,,2", "TAP 5",
                    "TAP 6 " + ",".join(["5"] * 21)):
            await a.send(bad)
            self.assertTrue((await a.recv()).startswith("ERR"), bad)
        self.assertTrue(await b.nothing())

    async def test_offline_partner_gets_queue_on_connect(self):
        a = await self.dev("1")
        await a.send("BUZZ 1")
        self.assertEqual(await a.recv(), "OK 1")
        await a.send("TAP 2 10,10,10")
        self.assertEqual(await a.recv(), "OK 2")
        b = await self.dev("2")
        self.assertEqual(await b.recv(), "MSG 1 BUZZ")
        self.assertTrue(await b.nothing())        # one at a time until ACK
        await b.send("ACK 1")
        self.assertEqual(await b.recv(), "MSG 2 TAP 10,10,10")
        await b.send("ACK 2")
        await asyncio.sleep(0.05)
        self.assertEqual(self.relay.queue["2"], [])

    async def test_unacked_message_is_resent(self):
        a, b = await self.dev("1"), await self.dev("2")
        await a.send("BUZZ 1")
        await a.recv()
        self.assertEqual(await b.recv(), "MSG 1 BUZZ")
        self.assertEqual(await b.recv(timeout=2.5), "MSG 1 BUZZ")   # resent, no ACK
        await b.send("ACK 1")
        await asyncio.sleep(0.05)
        self.assertEqual(self.relay.queue["2"], [])

    async def test_duplicate_seq_not_queued_twice(self):
        a = await self.dev("1")
        await a.send("BUZZ 9")
        self.assertEqual(await a.recv(), "OK 9")
        await a.send("BUZZ 9")                    # device retried after a lost OK
        self.assertEqual(await a.recv(), "OK 9")
        self.assertEqual(len(self.relay.queue["2"]), 1)

    async def test_queue_survives_restart(self):
        a = await self.dev("1")
        await a.send("BUZZ 1")
        await a.recv()
        a.close()
        await self.stop()
        await self.start()
        b = await self.dev("2")
        self.assertEqual(await b.recv(), "MSG 1 BUZZ")

    async def test_mid_wraps_at_999(self):
        self.relay.next_mid["2"] = 999
        a, b = await self.dev("1"), await self.dev("2")
        await a.send("BUZZ 1")
        await a.recv()
        self.assertEqual(await b.recv(), "MSG 999 BUZZ")
        await b.send("ACK 999")
        await a.send("BUZZ 2")
        await a.recv()
        self.assertEqual(await b.recv(), "MSG 1 BUZZ")

    async def test_reconnect_replaces_old_connection(self):
        old = await self.dev("1")
        new = await self.dev("1")
        self.assertTrue(await old.nothing(0.5))
        await new.send("PING 4000 50")
        self.assertEqual(await new.recv(), "PONG")

    async def test_idle_connection_closed(self):
        a = await self.dev("1")
        line = await a.r.readline()                # wait for server-side close (idle 2 s)
        self.assertEqual(line, b"")

    async def test_overlong_line_closes(self):
        a = await self.dev("1")
        await a.send("X" * 400)
        self.assertTrue(await a.nothing(1.0))

    async def test_expired_messages_dropped(self):
        self.relay.ttl = 0.2
        a = await self.dev("1")
        await a.send("BUZZ 1")
        await a.recv()
        await asyncio.sleep(1.5)
        self.assertEqual(self.relay.queue["2"], [])


if __name__ == "__main__":
    unittest.main()
