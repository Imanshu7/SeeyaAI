import sys
import os
import json
import queue
import threading
import time
import subprocess
import datetime
import webbrowser
import re
import random
import requests
import psutil
import pyautogui
import ctypes
import pyaudio
import vosk
import ollama
import pyttsx3
import vision_offline
import pythoncom
import pytesseract
import ollama
import pywhatkit

convo_history = []

#resource finder
def get_resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:        
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

tesseract_folder = get_resource_path('Tesseract-OCR')
tesseract_exe = os.path.join(tesseract_folder, 'tesseract.exe')

if os.path.exists(tesseract_exe):
    pytesseract.pytesseract.tesseract_cmd = tesseract_exe
else:
    print(f"WARNING: Tesseract not found at {tesseract_exe}")

MODEL_PATH = get_resource_path("model")

try:
    import pythoncom
except ImportError:
    print("CRITICAL: 'pywin32' not installed. Run: pip install pywin32")

def get_resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


MODEL_PATH = get_resource_path("model")
is_speaking = False
stop_flag = False
tts_lock = threading.Lock()
is_voice_muted = False 

def toggle_voice_mute():
    global is_voice_muted
    is_voice_muted = not is_voice_muted
    return is_voice_muted

APP_MAP = {
    "edge": "msedge.exe",
    "chrome": "chrome.exe",
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "code": "Code.exe",
    "vscode": "Code.exe",
    "word": "WINWORD.EXE",
    "excel": "EXCEL.EXE",
    "outlook": "OUTLOOK.EXE",
    "apple music": "applemusic.exe",
    "seeya": "SeeyaAI.exe",
    "paint": "mspaint.exe",
    "powerpoint": "POWERPNT.EXE",
    "file explorer": "explorer.exe",
    "vlc": "vlc.exe",
    "spotify": "Spotify.exe",
    "task manager": "Taskmgr.exe",
    "cmd": "cmd.exe",
    "settings": "SystemSettings.exe"
}

#to speak
def speak(text):
    global is_speaking, stop_flag, is_voice_muted   
    if not text: return
    
    if is_voice_muted:
        print(f"Seeya (Silent): {text}")
        return

    if is_speaking:
        stop_flag = True
        time.sleep(0.1)

    def safe_tts_thread():
        global is_speaking, stop_flag, is_voice_muted
        
        with tts_lock:
            stop_flag = False
            is_speaking = True
            
            import pythoncom
            pythoncom.CoInitialize()
            engine = None
            try:
                engine = pyttsx3.init()
                engine.setProperty('rate', 165)
                engine.setProperty('volume', 1.0)
                
                voices = engine.getProperty('voices')
                voice_found = False
                for v in voices:
                    if "zira" in v.name.lower():
                        engine.setProperty('voice', v.id)
                        voice_found = True
                        break
                if not voice_found and len(voices) > 1:
                    engine.setProperty('voice', voices[1].id)

                text_clean = text.encode("ascii", "ignore").decode()
                text_clean = text_clean.replace("*", "").replace("#", "").replace("`", "")

                def onWord(name, location, length):
                    global stop_flag, is_voice_muted

                    if stop_flag or is_voice_muted:
                        engine.stop()

                engine.connect('started-word', onWord)
                engine.say(text_clean)
                engine.runAndWait()

            except Exception as e:
                print(f"TTS Error: {e}")
            
            finally:
                is_speaking = False
                stop_flag = False
                if engine:
                    try:
                        engine.stop()
                        del engine
                    except: pass
                pythoncom.CoUninitialize()

    threading.Thread(target=safe_tts_thread, daemon=True).start()

#mic setup
def setup_mic():
    if not os.path.exists(MODEL_PATH):
        print(f"ERROR: Model not found at {MODEL_PATH}")
        return None, None
    try:
        vosk.SetLogLevel(-1)
        model = vosk.Model(MODEL_PATH)
        rec = vosk.KaldiRecognizer(model, 16000)
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=8000)
        return stream, rec
    except Exception as e:
        print(f"Mic Setup Error: {e}")
        return None, None

stream, rec = setup_mic()


def start_engine():
    global stream, rec
    if stream and rec:
        return
    print("Starting Engine in Background...")
    stream, rec = setup_mic()
    print("Engine Loaded & Ready!")

#listen
def listen():
    global is_speaking, stream, rec, stop_flag
    if not stream: return ""

    try:
        data = stream.read(4000, exception_on_overflow=False)
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            text = result.get("text", "")
        # else:
        #     partial= json.loads(rec.PartialResult())
        #     text = partial.get("partial", "")

            if text:
                print(f"User: {text}")
                if is_speaking:
                    stop_flag = True
                return text
    except:
        pass
    return ""

#brain setup
def check_and_setup_ollama():
    try:
        subprocess.run(["ollama", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except:
        print("Ollama not installed.")
        return False

    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        if "llama3.2" not in result.stdout:
            print("Downloading AI Model...")
            subprocess.run(["ollama", "pull", "llama3.2"], check=True)
    except:
        return False
    return True

is_ai_ready = check_and_setup_ollama()



def execute_smart_command(reply):
    """
    Advanced Command: Handles variations like:
    - [OPEN: chrome]
    - [Open: notepad]
    - Sure! [PLAY: song]
    """
    print(f"DEBUG: Checking logic for -> '{reply}'")
    match = re.search(r"\[(\w+):\s*(.*?)\]", reply, re.IGNORECASE)

    if match:
        command_type = match.group(1).upper()  
        argument = match.group(2).strip()     
        
        print(f"DEBUG: Found Command -> Type: {command_type}, Arg: {argument}")

        if command_type == "OPEN":
            speak(f"Opening {argument}...")
            if not open_any_app(argument):
                pyautogui.press("win")
                time.sleep(0.5)
                pyautogui.write(argument)
                time.sleep(1)
                pyautogui.press("enter")
            return True

        elif command_type == "PLAY":
                try:
                    speak(f"Playing {argument} on YouTube")
                    pywhatkit.playonyt(argument)
                    return True
                except Exception as e:
                    print(f"PyWhatKit Error: {e}")
                    webbrowser.open(f"https://www.youtube.com/results?search_query={argument}")
                    return True

        elif command_type == "SEARCH":
            speak(f"Searching Google for {argument}...")
            webbrowser.open(f"https://www.google.com/search?q={argument}")
            return True

        elif command_type == "CLOSE":
            speak(f"Closing {argument}...")
            close_app_logic(argument)
            return True
        
        elif command_type == "TIME":
            t = datetime.datetime.now().strftime("%I:%M %p")
            speak(f"Current time is {t}")
            return True
            
        elif command_type == "DATE":
            d = datetime.datetime.now().strftime("%d %B %Y")
            speak(f"Today is {d}")
            return True

    print("DEBUG: No valid command found in text.")
    return False
    

def ask_brain(text):
    global convo_history
    if not is_ai_ready:
        return "Brain not connected."

    system_instruction = """
    You are Seeya, an AI Assistant. You can control the user's PC.
    
    🛑 IMPORTANT RULES (Follow Strictly):
    1. If user asks to OPEN an app, reply ONLY: [OPEN: app_name]
    2. If user asks to PLAY video/song, reply ONLY: [PLAY: song_name]
    3. If user asks to SEARCH Google, reply ONLY: [SEARCH: query]
    4. If user asks for TIME/DATE, reply ONLY: [TIME] or [DATE]
    5. If user asks to CLOSE an app, reply ONLY: [CLOSE: app_name]
    6. For normal talk, just reply normally (short & sweet).
    
    Example:
    User: "Run chrome browser" -> You: "OPEN: chrome"
    User: "Who created you?" -> You: "I was created by Founder of Seeya AI."
    """

    messages = [{'role': 'system', 'content': system_instruction}] + convo_history + [{'role': 'user', 'content': text}]

    try:
        response = ollama.chat(model='llama3.2', messages=messages)
        reply = response['message']['content'].strip()
        if "[" not in reply:
            convo_history.append({'role': 'user', 'content': text})
            convo_history.append({'role': 'assistant', 'content': reply})
    
        return reply

    except Exception as e:
        return f"Brain Error: {e}"

#reset memory
def reset_memory():
    global convo_history
    convo_history = []
    print("Memory Wiped")

#open apps
def open_any_app(target):
    target = target.lower().strip()
    
    if target in APP_MAP:
        try:
            os.startfile(APP_MAP[target]) if ".exe" not in APP_MAP[target] else subprocess.Popen(APP_MAP[target])
            return True
        except: pass

    settings_map = {
        "wifi": "ms-settings:network-wifi",
        "bluetooth": "ms-settings:bluetooth",
        "display": "ms-settings:display",
        "sound": "ms-settings:sound",
        "apps": "ms-settings:appsfeatures"
    }
    for key, uri in settings_map.items():
        if key in target:
            os.system(f"start {uri}")
            return True

    try:
        pyautogui.press("win")
        time.sleep(0.5)
        pyautogui.write(target)
        time.sleep(1)
        pyautogui.press("enter")
        return True
    except:
        return False

#close apps
def close_app_logic(app_name):
    target = APP_MAP.get(app_name.lower(), app_name).lower()
    if target.endswith(".exe"): target = target.replace(".exe", "")
    
    closed = False
    for proc in psutil.process_iter(['name']):
        try:
            if target in proc.info['name'].lower():
                proc.terminate()
                closed = True
        except: pass
    return closed

#automate
def automation_engine(command):
    pyautogui.FAILSAFE = True 
    command = command.lower()

    if command.startswith("type"):
        text_to_type = command.replace("type", "").strip()
        if text_to_type:
            pyautogui.write(text_to_type, interval=0.05)
            return f"Typed: {text_to_type}"

    elif "select down" in command or "drag down" in command:
        screen_w, screen_h = pyautogui.size()
        x, y = pyautogui.position()
        
        speak("Selecting down...")
        pyautogui.mouseDown()
        pyautogui.moveTo(x, screen_h - 10, duration=0.5)

        time.sleep(2) 
        
        pyautogui.mouseUp()
        return "Selection Complete"

    elif "select up" in command or "drag up" in command:
        x, y = pyautogui.position()
        
        speak("Selecting up...")
        pyautogui.mouseDown()
        pyautogui.moveTo(x, 10, duration=0.5) 
        
        time.sleep(2) 
        
        pyautogui.mouseUp()
        return "Selection Complete"

    elif "select full page" in command or "select everything" in command:
        pyautogui.hotkey('ctrl', 'a')
        return "Selected everything"

    if "select down" in command or "drag down" in command:
        screen_w, screen_h = pyautogui.size() 
        current_x, current_y = pyautogui.position() 

        pyautogui.mouseDown()
        pyautogui.moveTo(current_x, screen_h - 10, duration=0.5)

        time.sleep(3) 

        pyautogui.mouseUp()
        return "Selected down."

    elif "select up" in command or "drag up" in command:
        current_x, current_y = pyautogui.position()

        pyautogui.mouseDown()       
        pyautogui.moveTo(current_x, 10, duration=0.5)
        
        time.sleep(3)

        pyautogui.mouseUp()
        return "Selected up."

    elif "press enter" in command: pyautogui.press('enter'); return "Pressed Enter."
    elif "press space" in command: pyautogui.press('space'); return "Pressed Space."
    elif "delete this" in command: pyautogui.press('backspace'); return "Backspace pressed."
    elif "save this" in command: pyautogui.hotkey('ctrl', 's'); return "Saved."
    elif "select all" in command: pyautogui.hotkey('ctrl', 'a'); return "Selected everything."
    elif "copy" in command: pyautogui.hotkey('ctrl', 'c'); return "Copied."
    elif "paste here" in command: pyautogui.hotkey('ctrl', 'v'); return "Pasted."
    elif "undo" in command: pyautogui.hotkey('ctrl', 'z'); return "Undone."
    elif "left click" in command: pyautogui.click(); return "Clicked."
    elif "double click" in command: pyautogui.doubleClick(); return "Double clicked."
    elif "right click" in command: pyautogui.rightClick(); return "Right clicked."
    elif "scroll down" in command: pyautogui.scroll(-500); return "Scrolled down."
    elif "scroll up" in command: pyautogui.scroll(500); return "Scrolled up."
    elif "minimize" in command: pyautogui.hotkey('win', 'd'); return "Minimized."
    elif "switch window" in command: pyautogui.hotkey('alt', 'tab'); return "Window switched."
    elif "close window" in command: pyautogui.hotkey('alt', 'f4'); return "Closed."

    return None

#mouse control
def mouse_engine(command):
    pyautogui.PAUSE = 0.1 
    if "move up" in command: pyautogui.moveRel(0, -50); return "Moved Up."
    elif "move down" in command: pyautogui.moveRel(0, 50); return "Moved Down."
    elif "move left" in command: pyautogui.moveRel(-50, 0); return "Moved Left."
    elif "move right" in command: pyautogui.moveRel(50, 0); return "Moved Right."
    elif "click this" in command: pyautogui.click(); return "Clicked."
    return None

#system commands
def system_commands(command):
    command = command.lower()

    if command.startswith("open"):
        app = command.replace("open", "").strip()
        if "c drive" in app: os.startfile("C:\\"); return "Opening C Drive"
        if "d drive" in app: os.startfile("D:\\"); return "Opening D Drive"
        if "downloads" in app: os.startfile(os.path.join(os.environ["USERPROFILE"], "Downloads")); return "Opening Downloads"
        if open_any_app(app): return f"Opening {app}"
        return f"Could not find {app}"

    if command.startswith("close"):
        app = command.replace("close", "").strip()
        if close_app_logic(app): return f"Closed {app}"
        return f"Could not close {app}"

    auto_reply = automation_engine(command)
    if auto_reply: return auto_reply
    mouse_reply = mouse_engine(command)
    if mouse_reply: return mouse_reply

    if "wifi" in command: os.system("start ms-settings:network-wifi"); return "Opening WiFi Settings"
    if "bluetooth" in command: os.system("start ms-settings:bluetooth"); return "Opening Bluetooth Settings"
    if "shutdown" in command: speak("Shutting down"); os.system("shutdown /s /t 5"); return "Shutting down"
    if "restart" in command: speak("Restarting"); os.system("shutdown /r /t 5"); return "Restarting"
    if "sleep" in command: speak("Sleeping"); ctypes.windll.powrprof.SetSuspendState(0, 1, 0); return "Sleeping"
    if "lock pc" in command: ctypes.windll.user32.LockWorkStation(); return "Computer Locked"

    if "search" in command or "google" in command:
        query = command.replace("search", "").replace("google", "").strip()
        webbrowser.open(f"https://www.google.com/search?q={query}")
        return f"Searching Google for {query}"

    if "play" in command and "youtube" in command:
        query = command.replace("play", "").replace("on youtube", "").strip()
        webbrowser.open(f"https://www.youtube.com/results?search_query={query}")
        threading.Thread(target=lambda: (time.sleep(5), pyautogui.click(640, 360))).start()
        return f"Playing {query} on YouTube"

    if command.startswith("type on notepad"):
        text = command.replace("type on notepad", "").strip()
        if text:
            open_any_app("notepad")
            time.sleep(1)
            pyautogui.write(text, interval=0.05)
            return "Typed successfully"

    if "take screenshot" in command and "delete" not in command:
        try:
            path = os.path.join(os.environ['USERPROFILE'], 'Desktop', f"Seeya_Screen_{int(time.time())}.png")
            pyautogui.screenshot(path)
            os.startfile(path)
            return "Screenshot saved on Desktop."
        except: return "Error taking screenshot."

    if "delete screenshot" in command:
        try:
            desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')
            files = [os.path.join(desktop, f) for f in os.listdir(desktop) if f.startswith("Seeya_Screen_")]
            if files:
                latest = max(files, key=os.path.getctime)
                os.remove(latest)
                return "Latest screenshot deleted."
            return "No screenshots found."
        except: return "Delete failed."

    if "time" in command: return datetime.datetime.now().strftime("The time is %I:%M %p")
    if "date" in command: return datetime.datetime.now().strftime("Today is %d %B %Y")
    if "battery" in command:
        try: return f"Battery is at {psutil.sensors_battery().percent}%"
        except: return "Cannot read battery"

    if "volume up" in command:
        for _ in range(5): pyautogui.press("volumeup")
        return "Volume Increased"
    if "volume down" in command:
        for _ in range(5): pyautogui.press("volumedown")
        return "Volume Decreased"
    if "mute" in command or "unmute" in command:
        pyautogui.press("volumemute")
        return "Volume Toggled"

    if "joke" in command:
        jokes = ["Why do programmers prefer dark mode? Because light attracts bugs.", "I told my computer I needed a break, and now it won't stop sending me Kit-Kats."]
        return random.choice(jokes)
    
    if "empty recycle bin" in command:
        try:
            ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 7)
            return "Recycle Bin Emptied"
        except: return "Failed to empty bin"

    if "click on" in command:
        target = command.replace("click on", "").strip()
        speak(f"Finding {target}...")
        if vision_offline.click_on_text(target): return f"Clicked on {target}"
        else:
            speak(f"I cannot see {target}.")
            return "Vision failed."

    return None

#loop
def loop(gui_signals=None):
    def update_gui(msg):
        if gui_signals:
            gui_signals.update_chat.emit("Seeya", msg)
        else:
            print(f"Seeya: {msg}")

    greeting = "Seeya online. Ready for commands."
    update_gui(greeting)
    speak(greeting)

    while True:
        try:
            text = listen()
            if not text:
                time.sleep(0.05)
                continue

            if gui_signals:
                gui_signals.update_chat.emit("You", text)
            else:
                print(f"You: {text}")

            command = text.lower()

            if "exit" in command or "bye" in command:
                speak("Goodbye!")
                break

            if system_commands(command):
                continue

            ai_reply = ask_brain(command) 
            if execute_smart_command(ai_reply): 
                if gui_signals:
                    gui_signals.update_chat.emit("Seeya", f"Executed: {ai_reply}")
                    #speak(f"Executed: {ai_reply}")
                else:
                    print(f"Executed: {ai_reply}")
                    #speak(f"Executed: {ai_reply}")
                    

            else:
                update_gui(ai_reply)
                speak(ai_reply)

        except Exception as e:
            print(f"Loop Error: {e}")

if __name__ == "__main__":
    loop()