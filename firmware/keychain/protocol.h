/*
 * Keychain <-> relay server line protocol (ASCII, one message per '\n' line).
 * Pure C, no Arduino dependencies, so it is unit-tested on the host
 * (firmware/test/test_protocol.c) and shared with nothing else.
 *
 * Device -> server                     Server -> device
 *   HELLO <id> <token>                   WELCOME | DENIED
 *   PING <battery mV> <free stack B>     PONG
 *   BUZZ <seq>                           OK <seq>          (message queued for partner)
 *   TAP <seq> <d1>,<d2>,...              OK <seq>
 *   ACK <mid>                            MSG <mid> BUZZ
 *                                        MSG <mid> TAP <d1>,<d2>,...
 *
 * TAP durations alternate press / gap / press ..., in 10 ms units (1..255),
 * always starting and ending with a press, at most PROTO_MAX_TAPS values.
 * seq and mid run 1..PROTO_MAX_ID and wrap, which bounds every line to
 * PROTO_LINE_MAX - 1 characters (the ATtiny85 has 512 bytes of RAM).
 */
#ifndef KEYCHAIN_PROTOCOL_H
#define KEYCHAIN_PROTOCOL_H

#include <stdint.h>
#include <string.h>

#define PROTO_MAX_TAPS 19          /* 10 presses + 9 gaps */
#define PROTO_MAX_ID 999           /* seq / mid wrap 1..999 -> longest line 87 chars */
#define PROTO_LINE_MAX 88          /* buffer for the longest line + NUL */
#define PROTO_SHORT_PRESS_10MS 50  /* < 500 ms single press = BUZZ */

enum {
  MSG_NONE = 0,
  MSG_WELCOME,
  MSG_DENIED,
  MSG_PONG,
  MSG_OK,       /* seq in .id */
  MSG_BUZZ,     /* mid in .id */
  MSG_TAP       /* mid in .id, taps in .taps[.n] */
};

typedef struct {
  uint8_t type;
  uint16_t id;
  uint8_t n;
  uint8_t taps[PROTO_MAX_TAPS];
} proto_msg_t;

/* parse an unsigned decimal at *p, advance *p; returns -1 if no digits */
static int32_t proto_num(const char **p) {
  int32_t v = -1;
  while (**p >= '0' && **p <= '9') {
    v = (v < 0 ? 0 : v) * 10 + (**p - '0');
    if (v > 65535) return -1;
    (*p)++;
  }
  return v;
}

static uint8_t proto_starts(const char *s, const char *prefix) {
  return strncmp(s, prefix, strlen(prefix)) == 0;
}

/* parse "d1,d2,..." into taps; returns count, 0 on any error */
static uint8_t proto_parse_taps(const char *p, uint8_t *taps) {
  uint8_t n = 0;
  for (;;) {
    int32_t v = proto_num(&p);
    if (v < 1 || v > 255 || n >= PROTO_MAX_TAPS) return 0;
    taps[n++] = (uint8_t)v;
    if (*p == ',') { p++; continue; }
    if (*p == 0) break;
    return 0;
  }
  return (n & 1) ? n : 0;  /* must start and end with a press -> odd count */
}

/* parse one server line (no trailing CR/LF). Returns msg->type. */
static uint8_t proto_parse(const char *line, proto_msg_t *msg) {
  const char *p;
  int32_t v;
  msg->type = MSG_NONE; msg->id = 0; msg->n = 0;
  if (strcmp(line, "WELCOME") == 0) return msg->type = MSG_WELCOME;
  if (strcmp(line, "DENIED") == 0) return msg->type = MSG_DENIED;
  if (strcmp(line, "PONG") == 0) return msg->type = MSG_PONG;
  if (proto_starts(line, "OK ")) {
    p = line + 3;
    v = proto_num(&p);
    if (v < 0 || *p) return MSG_NONE;
    msg->id = (uint16_t)v;
    return msg->type = MSG_OK;
  }
  if (proto_starts(line, "MSG ")) {
    p = line + 4;
    v = proto_num(&p);
    if (v < 0 || *p != ' ') return MSG_NONE;
    msg->id = (uint16_t)v;
    p++;
    if (strcmp(p, "BUZZ") == 0) return msg->type = MSG_BUZZ;
    if (proto_starts(p, "TAP ")) {
      msg->n = proto_parse_taps(p + 4, msg->taps);
      return msg->type = msg->n ? MSG_TAP : MSG_NONE;
    }
  }
  return MSG_NONE;
}

/* control lines only (WELCOME/DENIED/PONG/OK <seq>); no 27-byte struct on the
 * stack (the ATtiny85 has 512 bytes of RAM). MSG lines return MSG_NONE. */
static uint8_t proto_parse_ctl(const char *line, uint16_t *id) {
  const char *p;
  int32_t v;
  *id = 0;
  if (strcmp(line, "WELCOME") == 0) return MSG_WELCOME;
  if (strcmp(line, "DENIED") == 0) return MSG_DENIED;
  if (strcmp(line, "PONG") == 0) return MSG_PONG;
  if (proto_starts(line, "OK ")) {
    p = line + 3;
    v = proto_num(&p);
    if (v < 0 || *p) return MSG_NONE;
    *id = (uint16_t)v;
    return MSG_OK;
  }
  return MSG_NONE;
}

/* append unsigned decimal; returns new length or 0 if it does not fit */
static uint8_t proto_put_num(char *buf, uint8_t len, uint8_t cap, uint16_t v) {
  char tmp[6];
  uint8_t k = 0;
  do { tmp[k++] = (char)('0' + v % 10); v /= 10; } while (v);
  if (len + k + 1 > cap) return 0;
  while (k) buf[len++] = tmp[--k];
  buf[len] = 0;
  return len;
}

static uint8_t proto_put_str(char *buf, uint8_t len, uint8_t cap, const char *s) {
  uint8_t k = (uint8_t)strlen(s);
  if (len + k + 1 > cap) return 0;
  memcpy(buf + len, s, k + 1);
  return len + k;
}

/* "TAP <seq> d1,d2,...\n"; returns length (0 = buffer too small / bad input) */
static uint8_t proto_format_tap(char *buf, uint8_t cap, uint16_t seq,
                                const uint8_t *taps, uint8_t n) {
  uint8_t len, i;
  if (n == 0 || n > PROTO_MAX_TAPS || !(n & 1)) return 0;
  len = proto_put_str(buf, 0, cap, "TAP ");
  if (len) len = proto_put_num(buf, len, cap, seq);
  for (i = 0; len && i < n; i++) {
    len = proto_put_str(buf, len, cap, i ? "," : " ");
    if (len) len = proto_put_num(buf, len, cap, taps[i] ? taps[i] : 1);
  }
  if (len) len = proto_put_str(buf, len, cap, "\n");
  return len;
}

/* a gesture of one press shorter than 500 ms is a BUZZ, anything else a TAP */
static uint8_t proto_is_buzz(const uint8_t *taps, uint8_t n) {
  return n == 1 && taps[0] < PROTO_SHORT_PRESS_10MS;
}

#endif
