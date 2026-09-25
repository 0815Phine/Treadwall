# Treadwall Arduino firmware

Two Arduino sketches drive the rig hardware:

- [`wallsynchronizer/wallsynchronizer.ino`](wallsynchronizer/wallsynchronizer.ino) — reads the
  rotary encoder, drives the two Pololu Tic stepper controllers, and streams speed as an analog
  signal so the moving wall tracks the animal's running speed.
- [`lickport/lickport.ino`](lickport/lickport.ino) — detects licks with a capacitive sensor,
  measures running distance from the encoder, and dispenses reward via a pump.

### Why these parameters aren't in `treadwall_config.json`

Everything in the rest of the rig reads its tunable parameters from
[`../../parameters/treadwall_config.json`](../../parameters/treadwall_config.json) (via
`treadwall_config.m` in MATLAB and `json.load(...)` in Python). **The Arduino sketches cannot.**
They are compiled to C++ and flashed onto the microcontroller, which has no filesystem and never
reads the JSON at runtime. The constants below are therefore fixed in the `#define`s at the top of
each sketch by design.

**Changing any value here requires editing the sketch and re-flashing the board.**

The Bpod-side serial link to these boards *is* configured centrally — see the
`bpod.arduino` block (`com`, `baud`) in `treadwall_config.json`.

## `wallsynchronizer.ino` fixed parameters

| Constant | Value | Meaning |
|---|---|---|
| `tic_serial` pins | 10 (RX), 11 (TX) | SoftwareSerial to the Tic drivers (pin 10 ← Driver TX, pin 11 → Driver RX) |
| `tic1`, `tic2` device numbers | 14, 15 | Tic serial device IDs (left / right) |
| `ANALOG_DATA_STREAM_PIN` | `A0` | Analog speed output pin |
| `ENC_A_PIN`, `ENC_B_PIN` | 2, 4 | Rotary encoder channels A / B |
| `SPEED_PIN` | 3 | PWM speed output pin (not active) |
| `RUNNING_TIMEOUT` | 5000 µs (5 ms) | Idle time before the wall is treated as stopped (compared against a `micros()` delta, so the unit is microseconds) |
| `MAX_RUNNING_SPEED` | 1 m/s | Speed clamp (min = −1 m/s) |
| `MAX_PWM_VALUE` | 4095 | PWM count for 5 V (12-bit) |
| `PWM_BASELINE` | 2045 | Idle/neutral PWM value |
| `N_STEPS` | 1024 | Rotary encoder steps per rotation |
| `STEPS_PER_REVOLUTION` | 200 | Stepper motor steps per revolution |
| `MICROSTEPS_PER_STEP` | 2 | Stepper driver microstepping |
| `WALL_WHEEL_CIRCUMFERENCE` | 109 mm | Roller wheel circumference |
| `WHEEL_RADIUS` | 53 mm | Running wheel radius |
| Encoder interrupt edge | `RISING` | `attachInterrupt` trigger edge |
| `TIC_REARM_INTERVAL_MS` | 500 ms | How often both Tics are re-energized / taken out of safe start so hardware power-up order and mid-session driver power-cycles don't matter |
| `BAUD` | 115385 | Both the Tic link and the USB serial baud rate |
| `ANRES` | 12 | Analog resolution (only needed if speed is read out via analog pin) |

Pololu Tic controller register settings (current limit, accel, step mode, etc.) live separately in
[`../../parameters/tics/`](../../parameters/tics/) and are loaded onto the Tics with the Pololu Tic
utility, not by this sketch.

## `lickport.ino` fixed parameters

| Constant | Value | Meaning |
|---|---|---|
| `LICK_OUT` | 12 | TTL lick output pin |
| `ENC_A_PIN`, `ENC_B_PIN` | 2, 4 | Rotary encoder channels A / B |
| `PUMP` | 3 | Reward pump output pin |
| `CLEAN` | 13 | Pump-cleaning input pin |
| Capacitive sensor pins | 7, 8 | `CapacitiveSensor(7, 8)` (10 MΩ resistor; antenna on pin 8) |
| `MIN_DIST` | 150 mm | Minimum distance run before reward is eligible |
| `MIN_PROB` | 70 % | Minimum probability to deliver reward |
| `N_STEPS` | 1024 | Rotary encoder steps per rotation |
| `WHEEL_RADIUS` | 53 mm | Running wheel radius |
| `SENRES` | 80 | Sensor sample count |
| `LICKTH` | 1000 | Raw capacitance above which a lick sample counts |
| `CSTH` | 3800 | Cumulative capacitance that triggers a lick event |
| `LICKTTLOUT` | 1 ms | `LICK_OUT` HIGH duration |
| `PUMPONDUR` | 3 ms | `PUMP` HIGH duration per reward |
| Encoder interrupt edge | `RISING` | `attachInterrupt` trigger edge |
| `BAUD` | 9600 | USB serial baud rate |
