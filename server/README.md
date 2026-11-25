# Relay server

`relay.py` is a tiny TCP relay between the two keychains. Python 3.9+, standard library only.

- Authenticates each keychain (ID + token, constant-time compare).
- Forwards `BUZZ` / `TAP` to the partner, **queues messages while the partner is offline**,
  delivers them one at a time, resends until `ACK`ed, drops them after `queue_ttl_s`
  (default 7 days). The queue survives restarts (`state.json`).
- Logs every heartbeat with battery voltage, free stack on the ATtiny85 and the gap since
  the previous ping, which is what you need for tuning the heartbeat interval.

## Run

```sh
cp config.example.json config.json   # set the two tokens (same as firmware/keychain/config.h)
python3 relay.py --config config.json --state state.json
```

Open **TCP port 7070** (or whatever `port` says) in the firewall. The keychains connect
out from 1NCE's network, so the server needs a public IP or DNS name. Nothing has to reach
the keychains directly.

### As a service (Debian/Ubuntu)

```sh
sudo useradd -r -s /usr/sbin/nologin keychain
sudo mkdir -p /opt/keychain-relay && sudo cp relay.py config.json /opt/keychain-relay/
sudo chown -R keychain: /opt/keychain-relay
sudo cp keychain-relay.service /etc/systemd/system/
sudo systemctl enable --now keychain-relay
journalctl -u keychain-relay -f
```

## Test

```sh
python3 -m unittest -v test_relay                  # 15 end-to-end tests with simulated keychains
python3 fake_device.py --host <server> --id 2 --token <token 2>   # play keychain B by hand
```

## Notes

- **Traffic is not encrypted.** It's plain TCP: the SIM800L's TLS is outdated and costs too
  much flash and power. What's exposed is a buzz or a rhythm. The token stops strangers from
  impersonating a keychain, but someone on the network path could read or replay it. Use a
  long random token and don't reuse it anywhere else.
- **Data use** is a few hundred bytes per message plus the heartbeats (~15–20 MB per
  keychain per year at 5 min), well inside 1NCE's 500 MB / 10 years.
