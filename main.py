import json
import time
import asyncio
import os
from gpiozero import OutputDevice, InputDevice

# Configuration
MOISTURE_PIN = 25  
WATER_PUMP_PIN = 27 
PUMP_PINS = {
    "N": 22,
    "P": 23,
    "K": 24
}
TANK_LEVEL_FILE = "tank_levels.json"
DEFAULT_LEVEL = 1000.0  # mL
PUMP_RATE_ML_PER_SEC = 8.5

# --- GPIOZero setup ---
moisture_sensor = InputDevice(MOISTURE_PIN)

# --- Extra Water Pump (for irrigation only) ---

water_pump = OutputDevice(WATER_PUMP_PIN, active_high=False, initial_value=False)

def activate_water(amount_ml: float):
    """Activate the water-only pump for irrigation (not fertilizer)."""
    duration = amount_ml / PUMP_RATE_ML_PER_SEC
    print(f"[WATER] Pumping {amount_ml:.1f} mL of water for {duration:.2f} sec")
    water_pump.on()
    time.sleep(duration)
    water_pump.off()


pumps = {
    nutrient: OutputDevice(pin, active_high=False, initial_value=False)
    for nutrient, pin in PUMP_PINS.items()
}

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

def initialize_tanks(level=DEFAULT_LEVEL):
    """Reset all tanks to a default level (e.g., 1000 ml each)."""
    global tank_levels
    tank_levels = {nutrient: level for nutrient in PUMP_PINS}
    save_tank_levels()
    print(f"[INFO] Tanks initialized to {level} ml each.")
    return tank_levels


def reset_tank(nutrient, level=DEFAULT_LEVEL):
    """Reset a single tank (e.g., only N)."""
    global tank_levels
    if nutrient in tank_levels:
        tank_levels[nutrient] = level
        save_tank_levels()
        print(f"[INFO] {nutrient} tank reset to {level} ml.")
        return True
    else:
        print(f"[ERROR] Unknown nutrient: {nutrient}")
        return False


# --- Functions ---
def read_moisture():
    """
    Reads digital moisture sensor.
    Returns 0 = dry, 1 = wet.
    """
    value = int(moisture_sensor.value)
    if value == 0:
        print("Soil is DRY")
    else:
        print("Soil is WET")
    return value

def activate_pump(nutrient, amount_ml):
    if nutrient not in pumps:
        print(f"Invalid nutrient: {nutrient}")
        return False

    if tank_levels.get(nutrient, 0) < amount_ml:
        print(f"[WARNING] Not enough {nutrient} in tank.")
        return False

    duration = amount_ml / PUMP_RATE_ML_PER_SEC
    print(f"Pumping {amount_ml:.1f} mL of {nutrient} for {duration:.2f} sec")
    pumps[nutrient].on()
    time.sleep(duration)
    pumps[nutrient].off()

    tank_levels[nutrient] -= amount_ml
    save_tank_levels()
    return True

def get_tank_status():
    return tank_levels

# --- Auto-watering loop ---
async def auto_water_loop():
    while True:
        moisture = read_moisture()
        if moisture == 0:  # 0 = dry
            print("Dry soil detected — activating water pump.")
            activate_water(50.0)  # Example: 50 mL water dose
        else:
            print("Soil is moist, no watering needed.")
        await asyncio.sleep(600)  # check every 10 minutes

def compute_fertilizer(species, height, width, deficiencies, growth_stage="vegetative"):
    try:
        height_m = float(height) / 50
        width_m = float(width) / 50
    except ValueError:
        print("[ERROR] Height/Width must be numeric.")
        return []

    area = height_m * width_m

    # Growth stage multipliers
    stage_multipliers = {
        "seedling": 0.5,
        "vegetative": 1.0,
        "flowering": 0.8,
        "fruiting": 1.2
    }
    multiplier = stage_multipliers.get(growth_stage.lower(), 1.0)

    base_rates = {"N": 12, "P": 8, "K": 10}  # ml/m²

    results = []
    for d in deficiencies:
        d = d.upper()
        rate = base_rates.get(d, 10)
        amount_ml = area * rate * multiplier
        amount_ml = min(amount_ml, 500)  # cap to avoid overdosing
        duration = amount_ml / PUMP_RATE_ML_PER_SEC
        results.append({
            "nutrient": d,
            "amount_ml": amount_ml,
            "pump_time_sec": duration
        })
    return results

