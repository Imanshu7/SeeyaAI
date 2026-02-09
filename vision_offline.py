import pytesseract
from pytesseract import Output
import pyautogui
import cv2
import numpy as np
import difflib
import time

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def preprocess_image(img):   
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)   
    return thresh

def click_on_text(target_text):
    print(f"\nOptimizing Vision for: '{target_text}'...")
    try:
        screen = pyautogui.screenshot()
        img = np.array(screen)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)        
        processed_img = preprocess_image(img)
        data = pytesseract.image_to_data(processed_img, output_type=Output.DICT, config='--psm 11')        
        target_text = target_text.lower().strip()
        n_boxes = len(data['text'])
        
        for i in range(n_boxes):
            detected_word = data['text'][i].lower().strip()            
            if len(detected_word) < 2: continue
            similarity = difflib.SequenceMatcher(None, target_text, detected_word).ratio()
            
            if similarity > 0.8 or target_text in detected_word:
                
                x = data['left'][i] // 2
                y = data['top'][i] // 2
                w = data['width'][i] // 2
                h = data['height'][i] // 2               
                center_x = x + w // 2
                center_y = y + h // 2                
                print(f"Found '{detected_word}' (Match: {int(similarity*100)}%)! Clicking...")               
                pyautogui.moveTo(center_x, center_y, duration=0.3)
                pyautogui.click()
                return True
        print(f"Could not find '{target_text}' on screen.")
        return False
    
    except Exception as e:
        print(f"Vision Error: {e}")
        return False

if __name__ == "__main__":
    time.sleep(2)
    click_on_text("Recycle")