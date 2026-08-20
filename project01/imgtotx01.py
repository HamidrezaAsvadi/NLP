from google import genai
from PIL import Image

# Initialize the client
client = genai.Client(api_key="AIzaSyDsY1cmnkw6RqIbYkVzWb1wffZgM3ZbVAk")

# Load your image
img = Image.open("order.jpg")
prompt = "Describe this image in detail."

# Generate content using the correct model ID
response = client.models.generate_content(
    model="gemini-2.0-flash", # Or "gemini-1.5-flash"
    contents=[prompt, img]
)

print(response.text)