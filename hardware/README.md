# Treadwall Hardware

Build files and fabrication notes for every Treadwall component. See the
[main README](../README.md) for setup and running the rig.

## Hardware Components
- [Treadmill-Main](treadmillmain)
- [Treadwall-Main](treadwallmain)
- [Wall Synchronizer](wallsynchronizer)
- [Wall Mover](wallmover)
- [Circuit Box](circuitbox)

## Wiring Overview
<p align="center">
  <img src="./connections_overview.png" width="800">
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
All 3D-printed parts are provided as `.stl` files inside the individual
component folders, and each component's README lists them
with production amount and material (see the **File List** tables in
[Treadwall-Main](treadwallmain), [Treadmill-Main](treadmillmain),
[Wall Synchronizer](wallsynchronizer), [Wall Mover](wallmover)
and [Circuit Box](circuitbox)).

<!-- TODO: add printer model, filament/material and slicer settings once confirmed -->
