# Treadwall Arduino firmware

Two Arduino sketches drive the rig hardware:

- [`wallsynchronizer/wallsynchronizer.ino`](wallsynchronizer/wallsynchronizer.ino) — reads the
  rotary encoder, drives the two Pololu Tic stepper controllers, and streams speed as an analog
  signal so the moving wall tracks the animal's running speed.
- [`lickport/lickport.ino`](lickport/lickport.ino) — detects licks with a capacitive sensor,
  measures running distance from the encoder, and dispenses reward via a pump.

## Why these parameters aren't in `treadwall_config.json`

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
| `ticSerial` pins | 10 (TX), 11 (RX) | SoftwareSerial to the Tic drivers |
| `tic1`, `tic2` device numbers | 14, 15 | Tic serial device IDs (left / right) |
| `AnalogDataStreamPin` | `A0` | Analog speed output pin |
| `encAPin`, `encBPin` | 2, 4 | Rotary encoder channels A / B |
| `SpeedPin` | 3 | PWM speed output pin |
| `RunningTimeout` | 5000 ms | Idle time before the wall is treated as stopped |
| `MaxRunningSpeed` | 1 m/s | Speed clamp (min = −1 m/s) |
| `MaxPWMValue` | 4095 | PWM count for 5 V (12-bit) |
| `pwmBaseline` | 2045 | Idle/neutral PWM value |
| `nSteps` | 1024 | Rotary encoder steps per rotation |
| `StepsperRevolution` | 200 | Stepper motor steps per revolution |
| `MicrostepsPerStep` | 2 | Stepper driver microstepping |
| `WallWheelCircumference` | 109 mm | Roller wheel circumference |
| `wheelRadius` | 53 mm | Running wheel radius |
| Encoder interrupt edge | `RISING` | `attachInterrupt` trigger edge |
| Tic startup delay | 20 ms | Delay after energizing the Tics |
| Serial baud | 115385 | Both the Tic link and the USB serial |

Pololu Tic controller register settings (current limit, accel, step mode, etc.) live separately in
[`../../parameters/tics/`](../../parameters/tics/) and are loaded onto the Tics with the Pololu Tic
utility, not by this sketch.

## `lickport.ino` fixed parameters

| Constant | Value | Meaning |
|---|---|---|
| `lickOut` | 12 | TTL lick output pin |
| `encAPin`, `encBPin` | 2, 4 | Rotary encoder channels A / B |
| `Pump` | 3 | Reward pump output pin |
| `Clean` | 13 | Pump-cleaning input pin |
| Capacitive sensor pins | 7, 8 | `CapacitiveSensor(7, 8)` (10 MΩ resistor; antenna on pin 8) |
| `RunningTimeout` | 1000 ms | Idle time before running is treated as stopped |
| `minDist` | 150 mm | Minimum distance run before reward is eligible |
| `minProb` | 70 % | Minimum probability to deliver reward |
| `nSteps` | 1024 | Rotary encoder steps per rotation |
| `wheelRadius` | 53 mm | Running wheel radius |
| Capacitive sensor resolution | 80 | `capacitiveSensor(80)` sample count |
| Lick threshold | 1000 | Raw capacitance above which a lick sample counts |
| `csSum` threshold | 3800 | Cumulative capacitance that triggers a lick event |
| Lick TTL pulse | 1 ms | `lickOut` HIGH duration |
| Pump-on duration | 3 ms | `Pump` HIGH duration per reward |
| Encoder interrupt edge | `RISING` | `attachInterrupt` trigger edge |
| Serial baud | 9600 | USB serial |
