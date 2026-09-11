# AquaReserve Tabletop Demonstrator - Code
Runnable code for the toy-scale rig described in [`docs/DEMO_BUILD_GUIDE.md`](../docs/DEMO_BUILD_GUIDE.md).
It shows the AquaReserve loop in real life and, in Tier 2, is driven by the same decision family as the simulated controllers, with the finite reserve tracked in software.

## Pieces
- `../scripts/demo_bridge.py` - the FastAPI companion service the rig posts to. It runs a soil-moisture threshold with a critical-stage boost and a finite-reserve guard (mirroring the `aquareserve` ThresholdController / SmartCriticalStageController) and returns a pump command.

- `../scripts/demo_sim_client.py` - a software-only ESP32 emulator: a patch of soil that dries over time, so you can run and test the whole loop with no hardware.
- `esp32/aquareserve_demo.ino` - the real ESP32 firmware (reads the sensor, asks the bridge, runs the pump; falls back to a local threshold if offline).

## Run with No Hardware (Software-in-the-Loop)

```bash
# 1. start the bridge (needs the api extra: fastapi + uvicorn)
# serves on http://localhost:8500
python scripts/demo_bridge.py               

# 2. in another terminal, run the emulator against it
python scripts/demo_sim_client.py --url http://localhost:8500 --steps 40
```

You will see the soil dry out, the bridge decide to water while the reserve lasts, protect harder during the critical growth window and finally stop once the reserve is exhausted - the finite reserve story in miniature.

## Run it with Real Hardware
1. Start the bridge on a laptop or Raspberry Pi on the same network.
2. Open `esp32/aquareserve_demo.ino` in the Arduino IDE, install the "ArduinoJson" library, set `WIFI_SSID`, `WIFI_PASS` and `BRIDGE_URL` (the machine running the bridge) and flash an ESP32.
3. Calibrate: note the sensor's raw reading in dry and in wet mix and set `RAW_DRY` / `RAW_WET`.
4. Measure your pump (millilitres per second) and set `DEMO_PUMP_ML_PER_S` for the bridge.

## Tuning the Bridge
Environment variables (all optional): 
`DEMO_TRIGGER_PCT`, 
`DEMO_CRITICAL_TRIGGER_PCT`, 
`DEMO_PUMP_ML_PER_S`, 
`DEMO_PULSE_S`, 
`DEMO_INITIAL_RESERVE_ML`, 
`PORT`. 

Endpoints: 
`POST /demo/decide`, 
`POST /demo/reset`, 
`GET /demo/state`, 
`GET /`.
