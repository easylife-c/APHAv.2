import google.generativeai as genai
import mimetypes

genai.configure(api_key="AIzaSyCTodJeVGo8BrVv8r6yRSOObyXDEoOC0fs")

model = genai.GenerativeModel("gemini-2.5-flash")

def identify_plant(image_path):
    """Analyzes plant image using Gemini."""
    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type:
            mime_type = "image/jpeg"  # Fallback default

        prompt = ( 
            "You are a plant pathologist. Analyze this image for signs of disease or nutrient deficiency. "
            "if have nutrients defiency show only N,P,K and show possiblity and provide short answers only e.g Nitrogen defiency 54%possibility and provide possible dieases list ."
        )

        # 👇 Wrap image in the correct format
        image_data = {
            "mime_type": mime_type,
            "data": image_bytes
        }

        response = model.generate_content([prompt, image_data])
        return response.text

    except Exception as e:
        return f"❌ Error: {e}"
