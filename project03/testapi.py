from google import genai

# It's best practice to set your key as an environment variable (GEMINI_API_KEY),
# but you can pass it explicitly for a quick test:
client = genai.Client(api_key="")

try:
    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents="Hi there!",
    )
    print("Success! Response:")
    print(response.text)
except Exception as e:
    print(f"Authentication or API Error: {e}")