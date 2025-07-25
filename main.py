import json
import time
import asyncio
import os

# Configuration
TEST_MODE = True  # Set to False on real Raspberry Pi
MOISTURE_THRESHOLD = 30  # 0–100%, adjust as needed
MOISTURE_PIN = 17
PUMP_PINS = {
    "N": 22,
    "P": 23,
    "K": 24
}
TANK_LEVEL_FILE = "tank_levels.json"
DEFAULT_LEVEL = 1000.0  # mL
PUMP_RATE_ML_PER_SEC = 1.0

# --- pigpio or mock ---
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

        def read(self, pin):
            print(f"[MOCK] read({pin}) → simulate moist")
            return 100  # Simulate moist

    pi = MockPi()

# --- Initialization ---
for pin in list(PUMP_PINS.values()) + [MOISTURE_PIN]:
    pi.set_mode(pin, 0 if pin in PUMP_PINS.values() else 1)  # Output for pumps, input for sensor

# --- Tank level logic ---
def load_tank_levels():
    if os.path.exists(TANK_LEVEL_FILE):
        with open(TANK_LEVEL_FILE, 'r') as f:
            return json.load(f)
    else:
        return {nutrient: DEFAULT_LEVEL for nutrient in PUMP_PINS}

def save_tank_levels():
    with open(TANK_LEVEL_FILE, 'w') as f:
        json.dump(tank_levels, f)

tank_levels = load_tank_levels()

# --- Functions ---
def read_moisture():
    value = pi.read(MOISTURE_PIN)
    print(f"Moisture sensor reads: {value}")
    return value

def activate_pump(nutrient, amount_ml):
    if nutrient not in PUMP_PINS:
        print(f"Invalid nutrient: {nutrient}")
        return

    duration = amount_ml / PUMP_RATE_ML_PER_SEC
    pin = PUMP_PINS[nutrient]

    print(f"Pumping {amount_ml:.1f} mL of {nutrient} for {duration:.2f} sec")
    pi.write(pin, 0)  # ON (assuming active low)
    time.sleep(duration)
    pi.write(pin, 1)  # OFF

    tank_levels[nutrient] -= amount_ml
    save_tank_levels()

def get_tank_status():
    return tank_levels

# --- Auto-watering loop (to run in bot) ---
async def auto_water_loop():
    while True:
        moisture = read_moisture()
        if moisture < MOISTURE_THRESHOLD:
            print("Dry soil detected — activating watering pump.")
            activate_pump("N", 2.0)
        else:
            print("Soil is moist, no watering needed.")
        await asyncio.sleep(600)  # Check every 10 mins

def compute_fertilizer(species, height, width, deficiencies):
    area = height * width
    result = []
    for d in deficiencies:
        d = d.upper()
        amount_ml = area * 10  # Simple formula: 10 mL per m²
        duration = amount_ml / PUMP_RATE_ML_PER_SEC
        result.append({
            "nutrient": d,
            "amount_ml": amount_ml,
            "pump_time_sec": duration
        })
    return result

