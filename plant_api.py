# gemini_plant_analyzer.py

import google.generativeai as genai
import mimetypes
import json
import re

# Configure Gemini
genai.configure(api_key="AIzaSyCTodJeVGo8BrVv8r6yRSOObyXDEoOC0fs")
model = genai.GenerativeModel("gemini-2.5-flash")

# Fertilizer Calculator
def compute_fertilizer_amount(deficiencies, species="unknown", height_cm=100, width_cm=100):
    """
    Calculates fertilizer amount based on deficiencies and plant size (height and width in cm).
    Returns a list of formatted strings like: 'Nitrogen: 48g urea'
    """
    base_rates = {
        "Nitrogen": 0.6,
        "Phosphorus": 0.4,
        "Potassium": 0.5
    }

    fertilizer_product = {
        "Nitrogen": "urea",
        "Phosphorus": "phosphate",
        "Potassium": "potash"
    }

    canopy_area_cm2 = 3.14 * (height_cm / 2) * (width_cm / 2)
    fert_lines = []

    for nutrient in deficiencies:
        rate = base_rates.get(nutrient, 0.5)
        amount_grams = round(canopy_area_cm2 * rate / 100, 1)  # convert cm² to usable grams
        product = fertilizer_product.get(nutrient, "fertilizer")
        fert_lines.append(f"{nutrient}: {amount_grams}g {product}")

    return fert_lines

# Image Analyzer
def identify_plant(image_path):
    """
    Analyze plant image using Gemini and return structured plant analysis.
    Returns a dict:
    {
        "species": str,
        "deficiencies": list[str],
        "height": float,
        "width": float,
        "diseases": list[str],
        "probabilities": dict,
        "auto": bool
    }
    """
    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type:
            mime_type = "image/jpeg"

        # Gemini prompt
        prompt = prompt = (
    "You are a plant pathologist AI. Analyze the provided image to detect plant species, any visible diseases, and nutrient deficiencies.\n"
    "Only focus on deficiencies in Nitrogen, Phosphorus, and Potassium (N, P, K). For each, give a probability percentage if present.\n"
    "Return your analysis in **strict** JSON format like this:\n"
    "{\n"
    "  \"species\": \"papaya\",\n"
    "  \"deficiencies\": [\"Nitrogen\"],\n"
    "  \"probabilities\": {\n"
    "    \"Nitrogen\": \"54%\"\n"
    "  },\n"
    "  \"diseases\": [\"Fungal Leaf Spot\"],\n"
    "  \"height\": 75,\n"
    "  \"width\": 50,\n"
    "  \"auto\": true\n"
    "}\n"
    "If no deficiencies or diseases are detected, return empty lists for them.\n"
)




        image_data = {"mime_type": mime_type, "data": image_bytes}
        response = model.generate_content([prompt, image_data])
        text = response.text.strip()

        # Clean Gemini's response from any markdown wrappers
        json_string = re.sub(r"^```json|```$", "", text, flags=re.MULTILINE).strip()
        json_string = re.sub(r"^json", "", json_string, flags=re.IGNORECASE).strip()

        result = json.loads(json_string)

        species = result.get("species", "Unknown")
        deficiencies = result.get("deficiencies", [])
        probabilities = result.get("probabilities", {})
        diseases = result.get("diseases", [])
        auto = result.get("auto", False)
        height_cm = result.get("height", 100)
        width_cm = result.get("width", 100)

        response_lines = [f"🪴 **Species:** {species}"]

        if diseases:
            response_lines.append("\n🦠 **Diseases Detected:**")
            for d in diseases:
                response_lines.append(f"• {d}")

        if deficiencies:
            response_lines.append("\n🧪 **Nutrient Deficiencies:**")
            for d in deficiencies:
                prob = probabilities.get(d, "Unknown")
                response_lines.append(f"• {d} – {prob}")

        if height_cm and width_cm:
            response_lines.append("\n📏 **Plant Size:**")
            response_lines.append(f"• Height: {height_cm} cm")
            response_lines.append(f"• Width: {width_cm} cm")

        if auto and deficiencies:
            ferts = compute_fertilizer_amount(deficiencies, height_cm, width_cm)
            response_lines.append("\n💧 **Auto Fertilizer Plan:**")
            for line in ferts:
                nutrient, plan = line.split(":", 1)
                response_lines.append(f"• {nutrient} → {plan.strip()}")

        formatted_display = "\n".join(response_lines)

        return {
            "display": formatted_display,
            "species": species,
            "deficiencies": deficiencies,
            "height": height_cm,
            "width": width_cm,
            "diseases": diseases,
            "probabilities": probabilities,
            "auto": auto,
}

    except json.JSONDecodeError:
        return {"display": "❌ Could not parse Gemini response as JSON."}
    except Exception as e:
        return {"display": f"❌ Error: {e}"}
