import google.generativeai as genai
from PIL import Image
import json

# 1. Setup API
genai.configure(api_key="AIzaSyDsY1cmnkw6RqIbYkVzWb1wffZgM3ZbVAk")
model = genai.GenerativeModel('gemini-1.5-flash')

# 2. Define the structural prompt
prompt = """
Scan this handwritten order and return a JSON object. 
Format it like this:
{
  "order_id": "string",
  "customer_name": "string",
  "items": [
    {"item": "string", "quantity": integer, "price": float}
  ],
  "total_amount": float
}
Only return the JSON, nothing else.
"""

# 3. Process the image
img = Image.open('order.jpg')
response = model.generate_content([prompt, img])

# 4. Clean and save the JSON
# Gemini sometimes wraps the response in ```json code blocks; we strip those.
json_data = response.text.strip().replace('```json', '').replace('```', '').strip()
structured_order = json.loads(json_data)

with open('order_data.json', 'w') as f:
    json.dump(structured_order, f, indent=4)

print("Pipeline complete! Check order_data.json")