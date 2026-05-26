import cv2
import numpy as np

def clean_and_extract_text(image_bytes: bytes) -> str:
    # 1. Convert to OpenCV Image
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 2. LOCAL IMPORT: Only loads when the worker executes this specific function
    from paddleocr import PaddleOCR
    
    # In production, you might want to cache this inside the worker process
    # but local initialization guarantees it stays out of FastAPI.
    model = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
    
    # 3. Extract Text
    result = model.ocr(gray, cls=True)
    if not result or not result[0]:
        return ""
        
    extracted_text = " ".join([line[1][0] for line in result[0]])
    return extracted_text