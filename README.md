# Treadwall

<p align="center">
  <img src="./images/Aufbau.png" width="800">
</p>

### Components
- [Treadmill-Main](https://github.com/0815Phine/Treadwall/tree/main/Hardware/Treadmill%20Main)
- [Treadwall-Main](https://github.com/0815Phine/Treadwall/tree/main/Hardware/Treadwall%20Main)
- [Wall Synchronizer](https://github.com/0815Phine/Treadwall/tree/main/Hardware/Wall%20Synchronizer)
- [Wall Mover](https://github.com/0815Phine/Treadwall/tree/main/Hardware/Wall%20Mover)

### Wiring Overview
<p align="center">
  <img src="./images/Treadwall_Connections_Overview.png" width="800">
</p>

## Lasercutting
We used a Trotec Speedy Flex lasercutter with a 100W CO2 laser with the following settings:

| Parameter | Cutting Quality | Engraving Quality |
| :---: | :---: | :---: |
| Power | 70 % | 70 % |
| Speed | 0.2 % | 3.5 % |
| Laser Source | CO2 | CO2 |
| Frequency | 20'000 Hz | 1'000 Hz |
| Passes | 1 | 1 |
| Power Correction | 10 | 10 |
| z-Offset | -2 | 0 |
| Resolution | N.A. | 500 DPI |

Red lines -> cut; black lines -> engrave; blue lines -> not assigned

## 3D Printing

## Bpod System
Control of the system is done with the Bpod System. All used modules are controlled by a 'state machine' ([sanworks.io](https://sanworks.io/shop/viewproduct?productID=1036)).

Modules used for scrambled and predictable experiments:
| Module | Link | Functionality |
| :---: | :---: | :---: |
| Analog Output Module | [sanworks.io](https://sanworks.io/shop/viewproduct?productID=1038) | loaded with Waveplayer Firmware, can play certain analog signals, controls lateral movement of walls |
| Analog Input Module | [sanworks.io](https://sanworks.io/shop/viewproduct?productID=1037) | reads analog signals, used for zone transition in predictable paradigm |
| Rotary Encoder Module V2 | [sanworks.io](https://sanworks.io/shop/viewproduct?productID=1034) | connected directly to the rotary encoder, provides power and sends speed information to analog input module, loaded with modified firmware ([github.com](https://github.com/0815Phine/Bpod_RotaryEncoder_Firmware)) |

For further modules see [sanworks.io/products](https://sanworks.io/shop/products.php).
