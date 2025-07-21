import pigpio
import time
from pathlib import Path
import json
from typing import List, Dict

TEST_MODE = True  # Set to False on Raspberry Pi with pigpio

if not TEST_MODE:
    import pigpio
    pi = pigpio.pi()
    if not pi.connected:
        raise RuntimeError("Run 'sudo pigpiod' first.")
else:
    class MockPi:
        def set_mode(self, pin, mode):
            print(f"[MOCK] set_mode({pin}, {mode})")
        def write(self, pin, value):
            print(f"[MOCK] write({pin}, {value})")
    pi = MockPi()

# Configuration
PUMP_PINS = {"N": 17, "P": 27, "K": 22}  # GPIO pins
for pin in PUMP_PINS.values():
    pi.set_mode(pin, 1)  # OUTPUT

pump_rate_ml_per_sec = 1.0  # 1 ml/sec
TANK_LEVEL_FILE = "tank_levels.json"
DEFAULT_LEVEL = 1000.0  # ml

def load_tank_levels():
    try:
        with open(TANK_LEVEL_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {n: DEFAULT_LEVEL for n in PUMP_PINS}

def save_tank_levels():
    with open(TANK_LEVEL_FILE, "w") as f:
        json.dump(tank_levels, f, indent=2)

tank_levels = load_tank_levels()

def activate_pump(nutrient: str, duration_sec: float):
    nutrient = nutrient.upper()
    if nutrient not in PUMP_PINS:
        print(f"[ERROR] Unknown nutrient '{nutrient}'")
        return False

    used_ml = duration_sec * pump_rate_ml_per_sec
    if tank_levels.get(nutrient, 0) < used_ml:
        print(f"[WARNING] Not enough {nutrient} in tank. Needed: {used_ml} ml")
        return False

    pin = PUMP_PINS[nutrient]
    print(f"[PUMP] Activating {nutrient} for {duration_sec} sec")
    pi.write(pin, 1)
    if not TEST_MODE:
        time.sleep(duration_sec)
    else:
        print(f"[MOCK] Sleeping {duration_sec}s")
    pi.write(pin, 0)

    tank_levels[nutrient] -= used_ml
    save_tank_levels()
    return True

def compute_fertilizer(species: str, height: float, width: float, deficiencies: List[str]):
    area = height * width
    base_rate = 10  # ml/m² per deficiency
    results = []

    for deficiency in deficiencies:
        nutrient = deficiency.upper()
        amount_ml = base_rate * area
        pump_time = amount_ml / pump_rate_ml_per_sec
        results.append({
            "nutrient": nutrient,
            "amount_ml": amount_ml,
            "pump_time_sec": pump_time
        })

    return results

def get_tank_status():
    return {n: round(amt, 2) for n, amt in tank_levels.items()}
