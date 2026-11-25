# Backend: relay server (v2)

`relay.py` passes taps between the two keychains. It's a single Python file (3.9+,
standard library only), started from the tested v1 relay. The line protocol is unchanged,
so the v1 firmware and the coming v2 firmware both work with it.

```
keychain A ──2G/GPRS──► 1NCE ──internet──► relay.py :7070 ◄── … ◄── keychain B
                                                │
                                   status page :8080 (localhost only)
```

## What it does

- **Logs each keychain in** with its ID and token. The token comparison is constant-time.
- **Forwards taps:** passes `BUZZ` / `TAP` to the partner immediately over the open connection.
- **Queues messages while the partner is offline.**
  - Messages go out one at a time and are resent until the keychain sends `ACK`.
  - A message is dropped after `queue_ttl_s` (7 days).
  - The queue survives restarts (`state.json`).
- **Ignores duplicates:** a message the keychain sends twice (the same `seq`) is forwarded only once.
- **New in v2:**
  - **Status page:** `GET /status` (JSON) shows, per keychain:
    - online or offline, last seen, last check-in;
    - battery mV and a rough %;
    - messages waiting, sent and delivered.
    `GET /health` answers `ok`, for uptime monitors.
  - **Battery log:** `battery.csv` gets one line per check-in (`unix time, device, mV`).
    Plot it to see the real battery life and compare it with the 1-week target.

## Run it

### Plain Python

```sh
cp config.example.json config.json   # put two long random tokens in (same as in the firmware)
python3 relay.py --config config.json --state state.json
curl -s localhost:8080/status        # on the server itself
```

Generate tokens with `python3 -c "import secrets; print(secrets.token_urlsafe(18))"`.

### Docker

```sh
mkdir data && cp config.example.json data/config.json   # edit the tokens
# inside the container the status page must listen on all interfaces:
#   "status_listen": "0.0.0.0"   (compose still only publishes it on 127.0.0.1)
sudo chown -R 10001 data
docker compose up -d --build
docker compose logs -f
```

### systemd (Debian/Ubuntu, no Docker)

```sh
sudo useradd -r -s /usr/sbin/nologin keychain
sudo mkdir -p /opt/keychain-relay && sudo cp relay.py config.json /opt/keychain-relay/
sudo chown -R keychain: /opt/keychain-relay
sudo cp keychain-relay.service /etc/systemd/system/
sudo systemctl enable --now keychain-relay
journalctl -u keychain-relay -f
```

### Network

- **Port 7070/TCP** must be reachable from the internet. The keychains connect out from
  1NCE's network, so the server needs a public IP or a DNS name. Any small VPS works, or a
  home server with port forwarding.
- **Port 8080 (status) stays private.** View it with `ssh -L 8080:localhost:8080 server`,
  then open http://localhost:8080/status.

## Test

```sh
python3 -m unittest -v test_relay        # 19 end-to-end tests with simulated keychains
python3 fake_device.py --host <server> --id 2 --token <token 2>   # play keychain B by hand
```

`fake_device.py` lets you test one real keychain before the second one exists:
- `b` sends a buzz;
- `t 30,20,60` sends a tap pattern;
- incoming messages are shown and acknowledged automatically.

## Config (`config.json`)

| Key | Default | |
|---|---|---|
| `listen`, `port` | 0.0.0.0, 7070 | where the keychains connect |
| `devices` | | ID → name, token, partner ID |
| `queue_ttl_s` | 604800 | drop undelivered messages after 7 days |
| `resend_s` | 60 | resend if not ACKed |
| `idle_timeout_s` | 1200 | close a connection that has been silent this long. Keep it above 2 × the firmware check-in interval |
| `hello_timeout_s` | 30 | a new connection must log in within this time |
| `status_listen`, `status_port` | 127.0.0.1, 8080 | status page; `null` port disables it |
| `battery_log` | none | CSV path for battery voltages; leave it out to disable |

## Security notes

- **Traffic is plain TCP.** The SIM800L's TLS is outdated and slow.
  - What's exposed is that someone buzzed someone, and the tap rhythm.
  - Someone on the network path could read the token and pretend to be a keychain. They could send buzzes, but read nothing beyond that.
  - Use long random tokens that aren't reused anywhere.
- **The status page is read-only** and never shows the tokens. Still, don't publish it.

## Next steps (backend)

- [ ] Put it on a server with a public IP or DNS name; set `SERVER_HOST` in the firmware.
- [ ] After a week of use, check `battery.csv` and the check-in gaps in the log.
- [ ] Optional: a small web page or phone notification for "battery low" or "keychain offline".
