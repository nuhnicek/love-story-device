/* Host unit tests for firmware/keychain/protocol.h
 *   cc -Wall -Wextra -Werror -o /tmp/test_protocol firmware/test/test_protocol.c && /tmp/test_protocol
 */
#include <stdio.h>
#include "../keychain/protocol.h"

static int fails = 0;
#define CHECK(c) do { if (!(c)) { printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); fails++; } } while (0)

int main(void) {
  proto_msg_t m;
  char buf[128];
  uint8_t taps[PROTO_MAX_TAPS];

  /* simple server lines */
  CHECK(proto_parse("WELCOME", &m) == MSG_WELCOME);
  CHECK(proto_parse("DENIED", &m) == MSG_DENIED);
  CHECK(proto_parse("PONG", &m) == MSG_PONG);
  CHECK(proto_parse("OK 42", &m) == MSG_OK && m.id == 42);
  CHECK(proto_parse("OK", &m) == MSG_NONE);
  CHECK(proto_parse("OK 4x", &m) == MSG_NONE);
  CHECK(proto_parse("OK 70000", &m) == MSG_NONE);
  CHECK(proto_parse("", &m) == MSG_NONE);
  CHECK(proto_parse("garbage", &m) == MSG_NONE);

  /* buzz */
  CHECK(proto_parse("MSG 7 BUZZ", &m) == MSG_BUZZ && m.id == 7);
  CHECK(proto_parse("MSG BUZZ", &m) == MSG_NONE);
  CHECK(proto_parse("MSG 7 BUZZZ", &m) == MSG_NONE);

  /* tap patterns */
  CHECK(proto_parse("MSG 9 TAP 10,20,30", &m) == MSG_TAP && m.id == 9 && m.n == 3 &&
        m.taps[0] == 10 && m.taps[1] == 20 && m.taps[2] == 30);
  CHECK(proto_parse("MSG 9 TAP 10,20", &m) == MSG_NONE);        /* even count */
  CHECK(proto_parse("MSG 9 TAP 0", &m) == MSG_NONE);            /* zero */
  CHECK(proto_parse("MSG 9 TAP 256", &m) == MSG_NONE);          /* > 255 */
  CHECK(proto_parse("MSG 9 TAP 10,,20", &m) == MSG_NONE);
  CHECK(proto_parse("MSG 9 TAP 10,20,", &m) == MSG_NONE);
  CHECK(proto_parse("MSG 9 TAP 1 2", &m) == MSG_NONE);
  {
    /* 23 values OK, 25 values rejected */
    char line[200] = "MSG 1 TAP ";
    int i;
    for (i = 0; i < PROTO_MAX_TAPS; i++) strcat(line, i ? ",5" : "5");
    CHECK(proto_parse(line, &m) == MSG_TAP && m.n == PROTO_MAX_TAPS);
    strcat(line, ",5,5");
    CHECK(proto_parse(line, &m) == MSG_NONE);
  }

  /* formatting round trip */
  taps[0] = 12; taps[1] = 34; taps[2] = 255;
  CHECK(proto_format_tap(buf, sizeof buf, 65535, taps, 3) > 0);
  CHECK(strcmp(buf, "TAP 65535 12,34,255\n") == 0);
  CHECK(proto_format_tap(buf, sizeof buf, 1, taps, 2) == 0);     /* even */
  CHECK(proto_format_tap(buf, 10, 1, taps, 3) == 0);             /* too small */
  {
    /* round trip: what the device sends, relayed by the server as "MSG <mid> TAP <list>" */
    char line[140] = "MSG 3 TAP ";
    uint8_t n = proto_format_tap(buf, sizeof buf, 3, taps, 3);
    CHECK(n == strlen(buf));
    buf[n - 1] = 0;                                   /* drop "\n" */
    strcat(line, buf + strlen("TAP 3 "));             /* just the duration list */
    CHECK(proto_parse(line, &m) == MSG_TAP && m.n == 3 && m.taps[0] == 12 && m.taps[2] == 255);
  }
  {
    /* worst cases fit the firmware's PROTO_LINE_MAX line buffer */
    uint8_t big[PROTO_MAX_TAPS];
    char line[200] = "MSG 999 TAP ";
    int i;
    memset(big, 255, sizeof big);
    CHECK(proto_format_tap(buf, PROTO_LINE_MAX, PROTO_MAX_ID, big, PROTO_MAX_TAPS) > 0);
    CHECK(strlen(buf) + 1 <= PROTO_LINE_MAX);
    for (i = 0; i < PROTO_MAX_TAPS; i++) strcat(line, i ? ",255" : "255");
    CHECK(strlen(line) + 1 <= PROTO_LINE_MAX);      /* longest incoming line */
    CHECK(proto_parse(line, &m) == MSG_TAP && m.n == PROTO_MAX_TAPS);
  }

  /* control-line parser agrees with the full parser */
  {
    uint16_t id;
    CHECK(proto_parse_ctl("OK 42", &id) == MSG_OK && id == 42);
    CHECK(proto_parse_ctl("OK x", &id) == MSG_NONE);
    CHECK(proto_parse_ctl("PONG", &id) == MSG_PONG);
    CHECK(proto_parse_ctl("WELCOME", &id) == MSG_WELCOME);
    CHECK(proto_parse_ctl("DENIED", &id) == MSG_DENIED);
    CHECK(proto_parse_ctl("MSG 1 BUZZ", &id) == MSG_NONE);
  }

  /* gesture classification */
  taps[0] = 49;
  CHECK(proto_is_buzz(taps, 1));
  taps[0] = 50;
  CHECK(!proto_is_buzz(taps, 1));
  taps[0] = 10;
  CHECK(!proto_is_buzz(taps, 3));

  if (fails) { printf("%d FAILED\n", fails); return 1; }
  printf("all protocol tests passed\n");
  return 0;
}
