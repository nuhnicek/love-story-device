/*
 * GSM touch keychain — ATtiny85 + SIM800L, 1NCE data SIM, own relay server.
 *
 * Each keychain keeps one TCP connection to the relay server (/server) over 2G GPRS.
 *   short press (< 0.5 s)        -> "BUZZ": partner vibrates + heart glows 1.5 s
 *   long press or tap sequence   -> "TAP":  partner replays the exact rhythm
 * The server queues messages until the partner acknowledges them, so nothing is lost
 * while a keychain is out of coverage.
 *
 * Pins (carrier board netlist):
 *   PB0  MCU_RX  <- 1k <- SIM800L TXD     (SoftwareSerial RX, also ISP MOSI)
 *   PB1  MCU_TX  -> 47k/100k -> SIM RXD   (SoftwareSerial TX, also ISP MISO)
 *   PB2  BTN     side button to GND       (internal pull-up, also ISP SCK)
 *   PB3  RST_DRV -> 1k -> SIM800L RST     (open drain: only ever driven LOW)
 *   PB4  DRV     -> AO3400A gate          (PWM: motor + heart board together)
 *   PB5  RESET                            (kept for ISP)
 *
 * Power: the ATtiny85 sleeps in power-down. It wakes on the button, on any UART
 * activity from the modem (incoming data is held in the modem by AT+CIPRXGET=1, so
 * nothing is lost while waking), or on the ~8 s watchdog tick that times the
 * heartbeat. The SIM800L sleeps by itself between transfers (AT+CSCLK=2).
 *
 * Build (ATTinyCore): board "ATtiny25/45/85 (No bootloader)", chip ATtiny85,
 * clock 8 MHz internal, B.O.D. disabled, millis enabled. Burn the bootloader once
 * (sets fuses), then upload with "Arduino as ISP". See firmware/README.md.
 */
#include <SoftwareSerial.h>
#include <avr/interrupt.h>
#include <avr/pgmspace.h>
#include <avr/sleep.h>
#include <avr/wdt.h>
#include <stdlib.h>

#include "config.h"
#include "protocol.h"

#define PIN_RX 0
#define PIN_TX 1
#define PIN_BTN 2
#define PIN_SRST 3
#define PIN_DRV 4

#define STR_(x) #x
#define STR(x) STR_(x)

#define HEARTBEAT_TICKS ((uint16_t)(HEARTBEAT_MINUTES * 60UL / 8))
#define HANG_TICKS 45  /* ~6 min without petDog(): firmware hung -> watchdog reset */

SoftwareSerial sim(PIN_RX, PIN_TX);

/* ------------------------------------------------------------------ watchdog */
volatile uint16_t wdtTicks;
volatile uint8_t hangTicks;

/* disable a watchdog left running by a watchdog reset, before anything else runs */
void wdtOffEarly(void) __attribute__((naked, used, section(".init3")));
void wdtOffEarly(void) {
  MCUSR = 0;
  wdt_disable();
}

ISR(WDT_vect) {
  wdtTicks++;
  if (++hangTicks >= HANG_TICKS) WDTCR |= _BV(WDE); /* next timeouts reset the chip */
}

static void wdtStart() {
  cli();
  wdt_reset();
  WDTCR = _BV(WDCE) | _BV(WDE);
  WDTCR = _BV(WDIE) | _BV(WDP3) | _BV(WDP0); /* interrupt every ~8 s, no reset */
  sei();
}

static inline void petDog() { hangTicks = 0; }

static void delayPet(uint16_t ms) {
  while (ms > 100) { petDog(); delay(100); ms -= 100; }
  delay(ms);
}

/* ------------------------------------------------------------------ motor + heart */
static void driveOn() { analogWrite(PIN_DRV, DRIVE_PWM); }
static void driveOff() { analogWrite(PIN_DRV, 0); digitalWrite(PIN_DRV, LOW); }

static void playBuzz() { /* 1.5 s: three pulses */
  for (uint8_t i = 0; i < 3; i++) { driveOn(); delayPet(300); driveOff(); delayPet(200); }
}

static void playTaps(const uint8_t *t, uint8_t n) {
  for (uint8_t i = 0; i < n; i++) {
    if (i & 1) driveOff(); else driveOn();
    delayPet((uint16_t)t[i] * 10);
  }
  driveOff();
}

static void blip(uint8_t k) { /* "sent" confirmation */
  while (k--) { driveOn(); delay(60); driveOff(); delay(140); }
}

static void blipError() { driveOn(); delayPet(800); driveOff(); }

/* ------------------------------------------------------------------ modem I/O */
static const char T_OK[] PROGMEM = "OK\r\n";
static const char T_ERR[] PROGMEM = "ERROR";
static const char T_CLOSED[] PROGMEM = "CLOSED";
static const char T_DEACT[] PROGMEM = "DEACT";
static const char T_RXURC[] PROGMEM = "RXGET: 1";

static uint8_t mClosed, mDeact, mRx;
static volatile uint8_t rxActivity;
static uint8_t linkDown, dataPending, connected, denied;

/* streaming token matcher; returns 1 when token fully matched */
static uint8_t step(char c, PGM_P t, uint8_t *i) {
  if (c == (char)pgm_read_byte(t + *i)) {
    if (!pgm_read_byte(t + ++*i)) { *i = 0; return 1; }
  } else {
    *i = (c == (char)pgm_read_byte(t)) ? 1 : 0;
  }
  return 0;
}

/* next modem char (or -1 on timeout); watches for link-down / new-data URCs */
static int simGet(uint32_t timeoutMs) {
  uint32_t t0 = millis();
  while (!sim.available()) {
    if (millis() - t0 >= timeoutMs) return -1;
  }
  char c = sim.read();
  if (step(c, T_CLOSED, &mClosed) | step(c, T_DEACT, &mDeact)) linkDown = 1;
  if (step(c, T_RXURC, &mRx)) dataPending = 1;
  return (uint8_t)c;
}

static void simDrain() { while (sim.available()) simGet(0); }

static int8_t waitFor(uint32_t timeoutMs, PGM_P a, PGM_P b = NULL, PGM_P c = NULL) {
  uint8_t ia = 0, ib = 0, ic = 0;
  uint32_t t0 = millis();
  for (;;) {
    petDog();
    uint32_t el = millis() - t0;
    if (el >= timeoutMs) return -1;
    int ch = simGet(timeoutMs - el);
    if (ch < 0) return -1;
    if (step(ch, a, &ia)) return 0;
    if (b && step(ch, b, &ib)) return 1;
    if (c && step(ch, c, &ic)) return 2;
  }
}

static int16_t readNum(uint32_t timeoutMs) { /* digits, consumes the terminator */
  int16_t v = -1;
  for (;;) {
    int c = simGet(timeoutMs);
    if (c < 0) return -1;
    if (c < '0' || c > '9') return v;
    v = (v < 0 ? 0 : v) * 10 + (c - '0');
  }
}

static void cmdP(PGM_P s) {
  simDrain();
  sim.print((const __FlashStringHelper *)s);
  sim.write('\r');
}
#define CMD(s) cmdP(PSTR(s))

static bool atP(PGM_P s, uint32_t t) { cmdP(s); return waitFor(t, T_OK, T_ERR) == 0; }
#define AT(s, t) atP(PSTR(s), t)

/* the modem may be asleep (CSCLK=2): the first characters wake it */
static bool modemWake() {
  for (uint8_t i = 0; i < 5; i++) {
    CMD("AT");
    if (waitFor(300, T_OK) == 0) return true;
  }
  return false;
}

static void modemHardReset() {
  digitalWrite(PIN_SRST, LOW); /* PORT low first: never drive the 2.8 V pin high */
  pinMode(PIN_SRST, OUTPUT);
  delay(200);
  pinMode(PIN_SRST, INPUT);
  delayPet(5000);
}

static uint16_t batteryMv() { /* "+CBC: <bcs>,<bcl>,<mV>" */
  uint16_t mv = 0;
  CMD("AT+CBC");
  if (waitFor(1000, PSTR("+CBC: ")) == 0 && readNum(500) >= 0 && readNum(500) >= 0) {
    int16_t v = readNum(500);
    if (v > 0) mv = v;
  }
  waitFor(500, T_OK);
  return mv;
}

/* ------------------------------------------------------------------ TCP link */
/* One line buffer for both directions (RAM is 512 bytes): incoming lines are
 * assembled here, and an outgoing BUZZ/TAP is formatted here right before it is
 * sent (rebuilt from gest[] on every attempt, so incoming data can't corrupt it). */
static char lbuf[PROTO_LINE_MAX];
#define rxline lbuf
static uint8_t rxlen, rxOverflow;
static proto_msg_t inmsg;
static uint8_t haveMsg, lastType;
static uint16_t lastId, lastPlayed = 0xFFFF;

static void onLine() {
  if (strncmp_P(rxline, PSTR("MSG "), 4) == 0) {
    /* one message at a time; the server resends anything we haven't ACKed */
    if (!haveMsg && proto_parse(rxline, &inmsg)) haveMsg = 1;
    return;
  }
  uint16_t id;
  uint8_t t = proto_parse_ctl(rxline, &id);
  if (t) {
    lastType = t;
    lastId = id;
    if (t == MSG_DENIED) denied = 1;
  }
}

static void feed(char c) {
  if (c == '\r') return;
  if (c == '\n') {
    rxline[rxlen] = 0;
    if (rxlen && !rxOverflow) onLine();
    rxlen = 0; rxOverflow = 0;
    return;
  }
  if (rxlen < sizeof(rxline) - 1) rxline[rxlen++] = c;
  else rxOverflow = 1;
}

static bool tcpSendRaw(const char *s, uint8_t n, uint8_t fromFlash) {
  if (!modemWake()) return false;
  simDrain();
  sim.print(F("AT+CIPSEND="));
  sim.print(n);
  sim.write('\r');
  if (waitFor(3000, PSTR(">"), T_ERR) != 0) return false;
  if (fromFlash) sim.print((const __FlashStringHelper *)s);
  else sim.write((const uint8_t *)s, n);
  return waitFor(15000, PSTR("SEND OK"), PSTR("SEND FAIL"), T_ERR) == 0;
}
static bool tcpSend(const char *s) { return tcpSendRaw(s, strlen(s), 0); }
static bool tcpSendP(PGM_P s) { return tcpSendRaw(s, strlen_P(s), 1); }

/* drain everything the modem buffered for us: "+CIPRXGET: 2,<n>,<left>\r\n<n bytes>" */
static void pollData() {
  dataPending = 0;
  if (!modemWake()) return;
  for (uint8_t guard = 0; guard < 8; guard++) {
    CMD("AT+CIPRXGET=2,32");
    if (waitFor(3000, PSTR("+CIPRXGET: 2,"), T_ERR) != 0) return;
    int16_t n = readNum(500);
    int16_t left = readNum(500);
    if (n < 0 || left < 0) return;
    simGet(200); /* '\n' */
    for (int16_t i = 0; i < n; i++) {
      int c = simGet(1000);
      if (c < 0) return;
      feed(c);
    }
    waitFor(1000, T_OK);
    if (left == 0) return;
  }
}

static bool waitReply(uint8_t type, uint16_t id, uint32_t timeoutMs) {
  uint32_t t0 = millis(), lastPoll = millis();
  while (millis() - t0 < timeoutMs) {
    petDog();
    simDrain();
    if (dataPending || millis() - lastPoll > 2000) { pollData(); lastPoll = millis(); }
    if (lastType == type && (type != MSG_OK || lastId == id)) return true;
    if (denied || linkDown) return false;
  }
  return false;
}

static bool modemConnect() {
  connected = 0;
  if (!modemWake()) return false;
  AT("ATE0", 500);
  AT("AT+CSCLK=0", 500); /* stay awake while connecting */
  if (!AT("AT+CFUN=1", 10000)) return false;
  uint8_t reg = 0; /* packet-domain registration: 1 = home, 5 = roaming (1NCE roams) */
  for (uint8_t i = 0; i < 45 && !reg; i++) {
    CMD("AT+CGREG?");
    int8_t r = waitFor(1000, PSTR(",1\r"), PSTR(",5\r"), T_OK);
    reg = (r == 0 || r == 1);
    if (!reg) delayPet(2000);
  }
  if (!reg) return false;
  CMD("AT+CIPSHUT");
  waitFor(5000, PSTR("SHUT OK"), T_ERR);
  if (!AT("AT+CIPMUX=0", 1000)) return false;
  if (!AT("AT+CIPRXGET=1", 1000)) return false; /* keep received data in the modem */
  if (!AT("AT+CSTT=\"" APN "\"", 2000)) return false;
  if (!AT("AT+CIICR", 85000)) return false;
  CMD("AT+CIFSR"); /* returns our IP, no OK */
  waitFor(3000, PSTR("."));
  delayPet(300);
  CMD("AT+CIPSTART=\"TCP\",\"" SERVER_HOST "\",\"" SERVER_PORT "\"");
  if (waitFor(2000, T_OK, T_ERR) != 0) return false;
  if (waitFor(75000, PSTR("CONNECT OK"), PSTR("ALREADY CONNECT"), PSTR("CONNECT FAIL")) > 1) return false;
  linkDown = 0; rxlen = 0; haveMsg = 0;
  lastType = MSG_NONE;
  if (!tcpSendP(PSTR("HELLO " STR(DEVICE_ID) " " DEVICE_TOKEN "\n"))) return false;
  if (!waitReply(MSG_WELCOME, 0, 20000)) return false;
  AT("AT+CSCLK=2", 500); /* modem auto-sleeps whenever the UART is idle */
  connected = 1;
  return true;
}

/* ------------------------------------------------------------------ messages */
static uint16_t seq;

static void sendAck(uint16_t mid) {
  char a[12];
  strcpy_P(a, PSTR("ACK "));
  utoa(mid, a + 4, 10);
  strcat_P(a, PSTR("\n"));
  tcpSend(a);
}

static void handleIncoming() {
  while (haveMsg) {
    uint16_t mid = inmsg.id;
    if (mid != lastPlayed) { /* the server may resend if our ACK got lost */
      if (inmsg.type == MSG_BUZZ) playBuzz(); else playTaps(inmsg.taps, inmsg.n);
      lastPlayed = mid;
    }
    sendAck(mid); /* tcpSend never parses input, so inmsg stays intact until here */
    haveMsg = 0;
    delayPet(500); /* server sends the next queued message after our ACK */
    pollData();
  }
}

static uint8_t gest[PROTO_MAX_TAPS];

/* time the current button level; LOW = pressed. A gap longer than maxMs ends the gesture. */
static uint16_t measure(uint8_t level, uint16_t maxMs) {
  uint32_t t0 = millis();
  for (;;) {
    petDog();
    if (digitalRead(PIN_BTN) != level) {
      delay(DEBOUNCE_MS);
      if (digitalRead(PIN_BTN) != level) break;
    }
    if (level == HIGH && millis() - t0 >= maxMs) return maxMs;
  }
  uint32_t d = millis() - t0;
  return d > maxMs ? maxMs : (uint16_t)d;
}

static uint8_t to10ms(uint16_t ms) {
  uint16_t v = (ms + 5) / 10;
  return v < 1 ? 1 : (v > 255 ? 255 : v);
}

static void handleGesture() {
  uint8_t n = 0;
  for (;;) {
    gest[n++] = to10ms(measure(LOW, 2550));
    if (n >= PROTO_MAX_TAPS) break;
    uint16_t gap = measure(HIGH, GESTURE_END_MS);
    if (gap >= GESTURE_END_MS) break;
    gest[n++] = to10ms(gap);
  }
  if (denied) { blipError(); return; }
  if (++seq > PROTO_MAX_ID) seq = 1;
  for (uint8_t attempt = 0; attempt < 2; attempt++) {
    if (!connected && !modemConnect()) continue;
    rxlen = 0; /* lbuf becomes the outgoing line */
    if (proto_is_buzz(gest, n)) {
      strcpy_P(lbuf, PSTR("BUZZ "));
      utoa(seq, lbuf + 5, 10);
      strcat_P(lbuf, PSTR("\n"));
    } else if (!proto_format_tap(lbuf, sizeof lbuf, seq, gest, n)) {
      return;
    }
    lastType = MSG_NONE;
    if (tcpSend(lbuf) && waitReply(MSG_OK, seq, 20000)) {
      blip(2);
      handleIncoming();
      return;
    }
    connected = 0;
  }
  blipError();
}

/* ------------------------------------------------------------------ stack check */
/* Free RAM is painted at boot; PING reports how much was never touched, so the
 * real stack margin on hardware shows up in the server log. */
extern uint8_t __heap_start;
static void stackPaint() {
  uint8_t *p = &__heap_start;
  while (p < (uint8_t *)SP - 8) *p++ = 0xA5;
}
static uint16_t stackFree() {
  uint8_t *p = &__heap_start;
  uint16_t n = 0;
  while (p < (uint8_t *)RAMEND && *p++ == 0xA5) n++;
  return n;
}

/* ------------------------------------------------------------------ main */
static uint16_t hbTick, retryAt;
static uint8_t fails;

static void scheduleRetry() {
  static const uint8_t backoff[] PROGMEM = {1, 4, 8, 38, 75}; /* x ~8 s */
  if (fails < 255) fails++;
  if (fails % 3 == 0) modemHardReset();
  uint8_t k = fails > 5 ? 4 : fails - 1;
  retryAt = wdtTicks + pgm_read_byte(&backoff[k]);
}

static void connectNow() {
  if (modemConnect()) { fails = 0; hbTick = wdtTicks; }
  else if (!denied) scheduleRetry();
}

static void heartbeat() {
  char p[20];
  strcpy_P(p, PSTR("PING "));
  hbTick = wdtTicks;
  if (!modemWake()) { connected = 0; return; }
  utoa(batteryMv(), p + 5, 10);
  strcat_P(p, PSTR(" "));
  utoa(stackFree(), p + strlen(p), 10);
  strcat_P(p, PSTR("\n"));
  lastType = MSG_NONE;
  if (tcpSend(p) && waitReply(MSG_PONG, 0, 20000)) handleIncoming();
  else connected = 0;
}

static void sleepNow() {
  driveOff();
  uint16_t before = wdtTicks;
  set_sleep_mode(SLEEP_MODE_PWR_DOWN);
  cli();
  sleep_enable();
  sei();
  sleep_cpu();
  sleep_disable();
  /* woken by a pin change that wasn't the button -> the modem has something for us */
  if (wdtTicks == before && digitalRead(PIN_BTN) == HIGH) rxActivity = 1;
}

void setup() {
  stackPaint();
  pinMode(PIN_BTN, INPUT_PULLUP);
  digitalWrite(PIN_SRST, LOW);
  pinMode(PIN_SRST, INPUT);
  pinMode(PIN_DRV, OUTPUT);
  driveOff();
  ACSR |= _BV(ACD);       /* analog comparator off */
  ADCSRA &= ~_BV(ADEN);   /* ADC off */
  sim.begin(9600);
  PCMSK |= _BV(PCINT2);   /* the button shares SoftwareSerial's pin-change interrupt */
  GIMSK |= _BV(PCIE);
  wdtStart();
  blip(1);                /* alive */
  modemHardReset();
  connectNow();
}

void loop() {
  petDog();
  if (digitalRead(PIN_BTN) == LOW) handleGesture();

  if (connected && (rxActivity || dataPending)) {
    rxActivity = 0;
    simDrain();
    pollData();
    handleIncoming();
  }
  rxActivity = 0;
  if (connected && (linkDown || denied)) connected = 0;

  if (!connected && !denied && (int16_t)(wdtTicks - retryAt) >= 0) connectNow();
  if (connected && (uint16_t)(wdtTicks - hbTick) >= HEARTBEAT_TICKS) heartbeat();

  sleepNow();
}
