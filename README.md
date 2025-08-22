# APHAv.2
🌱 Smart Plant Care Bot

An automated Discord-connected smart plant system for monitoring and managing irrigation, fertilization, and plant growth stages using a Raspberry Pi + sensors.

🚀 Features

Discord Bot Integration

Upload plant photos → analyzed by Google Gemini.

Detects species, size (height/width), and nutrient deficiencies.

Interactive growth stage selection (🌱 Seedling, 🌿 Vegetative, 🌸 Flowering, 🍇 Fruiting).

Calculates fertilizer requirements automatically.

Fertilizer Management

Controls pumps for N, P, K tanks via Raspberry Pi GPIO.

Per-nutrient cooldown system to prevent overdosing.

Tank levels stored in tank_levels.json and updated after every use.

Commands to refill or reset tanks.

Watering System

Digital soil moisture sensor → automatically waters when soil is dry.

Independent pump control for irrigation.

Safety & Debugging

Anti-spam cooldown for fertilizer application.

Debug logs with colored console output.

Normalizes nutrient names (NITROGEN → N) for compatibility.

🛠️ Hardware Requirements

Raspberry Pi (any model with GPIO + internet).

Fertilizer pumps (ideally peristaltic to prevent siphon).

Optional check valve / solenoid valve to stop siphoning effect.

Soil moisture sensor (digital output mode).

Relay board or MOSFET drivers for pumps/valves.

Tanks for N, P, K solutions.

📂 Project Structure
