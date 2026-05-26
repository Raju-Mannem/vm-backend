import json
from huggingface_hub import InferenceClient
from app.core.config import settings

client = InferenceClient(api_key=settings.HF_TOKEN)

def structure_ocr_text(raw_text: str) -> str:
    """
    Takes the messy PaddleOCR text and uses a free HF model to extract fields.
    Returns a JSON string.
    """
    if not raw_text.strip():
        return "{}"

    prompt = f"""
    You are an expert data extractor. Extract the following details from this OCR text:
    Supplier Name, Total Amount, Date, and Tax Amount.
    Return ONLY a valid JSON object with keys: "supplier", "total", "date", "tax". 
    If a value is missing, use null. Do not include markdown formatting.
    
    OCR TEXT:
    {raw_text}
    """

    try:
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.2-3B-Instruct", 
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.1
        )
        
        content = response.choices[0].message.content
        
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "").strip()
            
        return content
        
    except Exception as e:
        print(f"LLM Extraction failed: {e}")
        return "{}"