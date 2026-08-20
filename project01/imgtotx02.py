from transformers import AutoProcessor, AutoModelForImageTextToText
from PIL import Image
import torch

# 1. Load the model and processor
model_id = "zai-org/GLM-OCR"
processor = AutoProcessor.from_pretrained(model_id)
model = AutoModelForImageTextToText.from_pretrained(
    model_id, 
    torch_dtype=torch.bfloat16, # Optimized for performance
    device_map="auto"
)

# 2. Open your local image file
# Replace 'my_order_image.jpg' with your actual file name
image_path = "order.jpg"
image = Image.open(image_path).convert("RGB")

# 3. Format the request
# We use "Text Recognition:" as the trigger for the OCR task
messages = [
    {
        "role": "user",
        "content": [
            {"type": "image"}, 
            {"type": "text", "text": "Text Recognition:"} 
        ],
    }
]

# 4. Process and Generate
inputs = processor(text="Text Recognition:", images=image, return_tensors="pt").to(model.device)

with torch.no_grad():
    generated_ids = model.generate(
        **inputs, 
        max_new_tokens=1024,
        do_sample=False # Keeps output consistent
    )

# 5. Decode the output
output_text = processor.decode(generated_ids[0], skip_special_tokens=True)
print("--- Extracted Text ---")
print(output_text)