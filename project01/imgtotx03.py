from transformers import AutoProcessor, AutoModelForImageTextToText
from PIL import Image
import torch

# 1. Load the model and processor
model_id = "zai-org/GLM-OCR"
processor = AutoProcessor.from_pretrained(model_id)

# Changed torch_dtype to dtype to address the deprecation warning
model = AutoModelForImageTextToText.from_pretrained(
    model_id, 
    dtype=torch.bfloat16, 
    device_map="auto",
    trust_remote_code=True
)

# 2. Open your local image file
image_path = "order.jpg"
image = Image.open(image_path).convert("RGB")

# 3. Format the request
# The chat template will use this structure to insert the required image tokens
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
# apply_chat_template is critical: it converts the messages list into a string 
# that includes the special image placeholder tokens the model requires.
prompt = processor.apply_chat_template(messages, add_generation_prompt=True)

inputs = processor(
    text=prompt, 
    images=image, 
    return_tensors="pt"
).to(model.device)

with torch.no_grad():
    generated_ids = model.generate(
        **inputs, 
        max_new_tokens=1024,
        do_sample=False
    )

# 5. Decode the output
# We slice generated_ids to remove the input tokens from the printed output
generated_ids = [
    output_ids[len(input_ids):] for input_ids, output_ids in zip(inputs.input_ids, generated_ids)
]

output_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

print("\n--- Extracted Text ---")
print(output_text.strip())