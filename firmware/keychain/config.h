/*
 * Per-keychain configuration. Flash keychain A with DEVICE_ID 1 and keychain B with
 * DEVICE_ID 2 (or build with -DDEVICE_ID=2). Tokens must match server/config.json.
 */
#ifndef KEYCHAIN_CONFIG_H
#define KEYCHAIN_CONFIG_H

#ifndef DEVICE_ID
#define DEVICE_ID 1
#endif

#if DEVICE_ID == 1
#define DEVICE_TOKEN "change-me-token-for-keychain-1"
#else
#define DEVICE_TOKEN "change-me-token-for-keychain-2"
#endif

/* token: up to 40 characters, letters/digits/-/_ only */

/* your relay server (scripts in /server). A DNS name works too. */
#define SERVER_HOST "relay.example.com"
#define SERVER_PORT "7070"

/* 1NCE APN; no username/password */
#define APN "iot.1nce.net"

/* Heartbeat keeps the operator's NAT mapping alive and detects dead links.
 * Shorter = more reliable delivery, longer = better battery. Tune with the
 * server log (it prints the gap between heartbeats and any drops). */
#define HEARTBEAT_MINUTES 5

/* Motor/heart drive strength, 0..255 PWM duty. The 0820 motor is rated 3 V and the
 * battery is 3.5-4.2 V, so ~75 % duty keeps it in spec. */
#define DRIVE_PWM 190

/* Gesture timing */
#define GESTURE_END_MS 1500   /* no new press for this long = gesture finished */
#define DEBOUNCE_MS 20

#endif
