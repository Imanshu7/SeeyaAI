import datetime
import sys
import os
import psutil
import threading
import ctypes
import re
import webbrowser
import pyautogui
import time
import pywhatkit
import subprocess
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QScrollArea, 
                             QProgressBar, QFrame, QGraphicsDropShadowEffect, 
                             QStackedWidget, QTextBrowser, QLineEdit, QSizePolicy, 
                             QSizeGrip, QSystemTrayIcon, QMenu, QAction, QSlider)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QEvent
from PyQt5.QtGui import QColor, QFont, QIcon, QCursor
from PyQt5.QtCore import pyqtSignal, QObject

#backend
import assistant_offline as logic


WDA_NONE = 0x00000000
WDA_EXCLUDEFROMCAPTURE = 0x00000011
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080     
WS_EX_APPWINDOW = 0x00040000      
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_FRAMECHANGED = 0x0020

#dpi
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
if hasattr(Qt, 'AA_EnableHighDpiScaling'):
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

def execute_smart_command(reply):
    try:
        match = re.search(r"\[(\w+):\s*(.*?)\]", reply, re.IGNORECASE)

        if match:
            cmd_type = match.group(1).upper() 
            arg = match.group(2).strip()        
            print(f"ACTION DETECTED: {cmd_type} -> {arg}")

            if cmd_type == "PLAY":
                try:
                    logic.speak(f"Playing {arg} on YouTube")
                    pywhatkit.playonyt(arg)
                    return True
                except Exception as e:
                    print(f"PyWhatKit Error: {e}")
                    webbrowser.open(f"https://www.youtube.com/results?search_query={arg}")
                    return True
            
            elif cmd_type == "OPEN":
                pyautogui.press("win")
                time.sleep(0.5)
                pyautogui.write(arg)
                time.sleep(1)
                pyautogui.press("enter")
                return True
            
            elif cmd_type == "SEARCH":
                webbrowser.open(f"https://www.google.com/search?q={arg}")
                return True
            
            elif cmd_type == "CLOSE":
                logic.close_app_logic(arg)
                return True

            elif cmd_type == "TIME":
                t = datetime.datetime.now().strftime("%I:%M %p")
                logic.speak(f"It is {t}")
                return True

    except Exception as e:
        print(f"ACTION ERROR: {e}")
    
    return False

class SeeyaThread(QThread):
    chat_signal = pyqtSignal(str, str)
    status_signal = pyqtSignal(str)
    glow_signal = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.is_running = True
        self.is_mic_muted = True
        self.greeted = False

    def run(self):
        self.msleep(1000)
        
        if not self.greeted:
            self.chat_signal.emit("Seeya", "Seeya Online.")
            try: logic.speak("Seeya Online")
            except: pass
            self.greeted = True

        print("🟢")

        while self.is_running:
            try: 
                speaking_state = logic.is_speaking
            except: 
                speaking_state = False
            self.glow_signal.emit(speaking_state)

            if self.is_mic_muted or speaking_state:
                self.msleep(100); continue
            
            try:
                text = logic.listen() 
            except: text = ""

            if text:
                print(f"User: {text}")
                self.chat_signal.emit("You", text)

                ai_reply = logic.ask_brain(text)
                print(f"Seeya: {ai_reply}")

                if execute_smart_command(ai_reply):
                    self.chat_signal.emit("Seeya", f"Executed: {ai_reply}")
                    self.speak(f"Executed: {ai_reply}")
                else:
                    self.chat_signal.emit("Seeya", ai_reply)
                    logic.speak(ai_reply)

            self.msleep(50)

    def process_command(self, text):
        self.chat_signal.emit("Thinking", "Thinking...")
        self.status_signal.emit("Processing...")
        
        command = text.lower()
        pc_reply = logic.system_commands(command)
        if pc_reply:
            self.chat_signal.emit("Seeya", pc_reply)
            logic.speak(pc_reply)
        else:
            ai_reply = logic.ask_brain(text)

            if execute_smart_command(ai_reply):
                 self.chat_signal.emit("Seeya", f"Executed: {ai_reply}")
                 #self.speak(f"Executed: {ai_reply}")
            else:
                 self.chat_signal.emit("Seeya", ai_reply)
                 logic.speak(ai_reply)
                 
        self.status_signal.emit("Active")
        
#main
class SeeyaDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Seeya AI")
        self.resize(550, 250)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowSystemMenuHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.is_maximized_custom = False 
        self.old_pos = None 
        self.current_thinking_widget = None
        self.is_dark_mode = True
        self.is_stealth_mode = False
        self.active_btn = None 
        self.voice_enabled = True
        
        self.init_ui()
        self.init_tray()
        self.init_logic()
        self.apply_theme()
           

    def init_ui(self):
        self.pages = QStackedWidget()

        #main box
        self.shadow_box = QWidget()
        self.setCentralWidget(self.shadow_box)
        self.layout_main = QHBoxLayout(self.shadow_box)
        self.layout_main.setContentsMargins(10, 10, 10, 10)
        self.layout_main.setSpacing(5)

        
        self.sidebar = QFrame()
        self.sidebar.setObjectName("SidebarFrame")
        self.sidebar.setFixedWidth(200)
        
        sb_shadow = QGraphicsDropShadowEffect(self)
        sb_shadow.setBlurRadius(15); sb_shadow.setColor(QColor(0,0,0,80)); sb_shadow.setYOffset(2)
        self.sidebar.setGraphicsEffect(sb_shadow)

        self.side_layout = QVBoxLayout(self.sidebar)
        self.side_layout.setContentsMargins(15, 20, 15, 20)
        self.side_layout.setSpacing(8)

        
        self.win_ctrls = QHBoxLayout()
        self.win_ctrls.setSpacing(6)
        self.btn_close = QPushButton(); self.btn_min = QPushButton(); self.btn_max = QPushButton()
        
        for btn, col in [(self.btn_close, "#FF5F57"), (self.btn_min, "#FEBC2E"), (self.btn_max, "#28C840")]:
            btn.setFixedSize(12, 12)
            btn.setStyleSheet(f"background-color: {col}; border-radius: 6px; border: none;")
        
        self.btn_close.clicked.connect(self.hide_to_tray) 
        self.btn_min.clicked.connect(self.showMinimized)
        self.btn_max.clicked.connect(self.toggle_maximize)
        
        self.win_ctrls.addWidget(self.btn_close)
        self.win_ctrls.addWidget(self.btn_min)
        self.win_ctrls.addWidget(self.btn_max)
        self.win_ctrls.addStretch()
        self.side_layout.addLayout(self.win_ctrls)
        self.side_layout.addSpacing(10)

        self.logo_box = QLabel("SEEYA AI")
        self.logo_box.setAlignment(Qt.AlignCenter)
        self.logo_box.setFixedHeight(30)
        self.side_layout.addWidget(self.logo_box)
        self.side_layout.addSpacing(10)

        self.btn_chat = self.create_nav_btn("💬 Chat", 0, True)
        self.btn_cmds = self.create_nav_btn("⚡ Capabilities", 1, False)
        
        self.side_layout.addStretch()

        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(8)

        self.btn_stealth = QPushButton("🔍︎")
        self.btn_stealth.setToolTip("Toggle Stealth Mode")
        self.btn_stealth.setCursor(Qt.PointingHandCursor)
        self.btn_stealth.setFixedHeight(38) 
        self.btn_stealth.clicked.connect(self.toggle_stealth)

        self.btn_theme = QPushButton("⏾/☀︎")
        self.btn_theme.setToolTip("Switch Theme")
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.setFixedHeight(38)
        self.btn_theme.clicked.connect(self.toggle_theme)
        

        toggle_row.addWidget(self.btn_stealth)
        toggle_row.addWidget(self.btn_theme)
        
        self.side_layout.addLayout(toggle_row)

        audio_row = QHBoxLayout()
        audio_row.setSpacing(8)
        
        self.btn_voice = QPushButton("🔊")
        self.btn_voice.setCheckable(True); self.btn_voice.setChecked(True)
        self.btn_voice.setFixedHeight(38)
        self.btn_voice.clicked.connect(self.toggle_voice_output)
        
        self.btn_mic = QPushButton("🎙️")
        self.btn_mic.setCheckable(True); self.btn_mic.setChecked(False)
        self.btn_mic.setFixedHeight(38)
        self.btn_mic.clicked.connect(self.toggle_mic_input)

        audio_row.addWidget(self.btn_voice)
        audio_row.addWidget(self.btn_mic)
        self.side_layout.addLayout(audio_row)

        self.side_layout.addSpacing(5)

        self.lbl_cpu = QLabel("CPU Usage")
        self.lbl_cpu.setStyleSheet("font-size: 8px; font-weight: bold; color: #238271;")
        self.side_layout.addWidget(self.lbl_cpu)
        
        self.cpu_bar = QProgressBar()
        self.cpu_bar.setFixedHeight(4)
        self.cpu_bar.setTextVisible(False)
        self.side_layout.addWidget(self.cpu_bar)

        self.layout_main.addWidget(self.sidebar)

        self.lbl_opacity = QLabel("OPACITY")
        self.lbl_opacity.setStyleSheet("font-size: 8px; font-weight: bold; color: #238271; margin-top: 10px;")
        self.side_layout.addWidget(self.lbl_opacity)

        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(30, 100) 
        self.opacity_slider.setValue(100)
        self.opacity_slider.setCursor(Qt.PointingHandCursor)
        self.opacity_slider.valueChanged.connect(self.change_opacity)
        self.side_layout.addWidget(self.opacity_slider)

        self.main_content = QFrame()
        self.main_content.setObjectName("MainContentFrame")
        
        main_shadow = QGraphicsDropShadowEffect(self)
        main_shadow.setBlurRadius(20); main_shadow.setColor(QColor(0,0,0,80)); main_shadow.setYOffset(4)
        self.main_content.setGraphicsEffect(main_shadow)

        self.content_layout = QVBoxLayout(self.main_content)
        self.content_layout.setContentsMargins(15, 15, 15, 15)

        header = QHBoxLayout()
        self.lbl_status = QLabel("● Active")
        header.addWidget(self.lbl_status)
        header.addStretch()
        
        self.btn_refresh = QPushButton("⟳ Clear")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setFixedSize(60, 26)
        self.btn_refresh.clicked.connect(self.refresh_chat)
        header.addWidget(self.btn_refresh)
        
        self.content_layout.addLayout(header)

        self.page_chat = QWidget()
        chat_layout = QVBoxLayout(self.page_chat)
        chat_layout.setContentsMargins(0,0,0,0)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.chat_container = QWidget()
        self.chat_container.setObjectName("ChatContainer")
        self.msg_layout = QVBoxLayout(self.chat_container)
        self.msg_layout.setSpacing(10)
        self.msg_layout.setAlignment(Qt.AlignTop)
        self.msg_layout.setContentsMargins(5, 5, 10, 5)
        
        self.scroll.setWidget(self.chat_container)
        chat_layout.addWidget(self.scroll)

        self.input_frame = QFrame()
        self.input_frame.setObjectName("InputFrame")
        self.input_frame.setFixedHeight(45)
        
        inp_layout = QHBoxLayout(self.input_frame)
        inp_layout.setContentsMargins(15, 0, 5, 0)
        
        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("Mic Muted. Unmute or type Here...")
        self.input_box.setFrame(False)
        self.input_box.returnPressed.connect(self.process_text)
        
        self.btn_send = QPushButton("➤")
        self.btn_send.setFixedSize(32, 32)
        self.btn_send.setCursor(Qt.PointingHandCursor)
        self.btn_send.clicked.connect(self.process_text)
        
        inp_layout.addWidget(self.input_box)
        inp_layout.addWidget(self.btn_send)
        
        chat_layout.addWidget(self.input_frame)
        self.pages.addWidget(self.page_chat)

        self.page_cmd = QTextBrowser()
        self.page_cmd.setFrameShape(QFrame.NoFrame)
        self.pages.addWidget(self.page_cmd)
        
        self.content_layout.addWidget(self.pages)

        self.sizegrip = QSizeGrip(self) 
        self.sizegrip.setFixedSize(20, 20)
        self.sizegrip.raise_()
        #self.setMinimumSize(400, 200)
        
        self.layout_main.addWidget(self.main_content)

    def init_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(3)) 

        self.tray_menu = QMenu()
        
        action_show = QAction("Open Seeya", self)
        action_show.triggered.connect(self.show_from_tray)
        
        action_quit = QAction("Exit App", self)
        action_quit.triggered.connect(self.force_quit)
        
        self.tray_menu.addAction(action_show)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(action_quit)
        
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.show()
        
        self.tray_icon.activated.connect(self.on_tray_activate)

    def on_tray_activate(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_from_tray()

    def show_from_tray(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        self.activateWindow()

        if not self.is_stealth_mode:
            hwnd = int(self.winId())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style & ~WS_EX_TOOLWINDOW)
            ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)

    def hide_to_tray(self):
        self.hide()
        self.tray_icon.showMessage("Seeya", "I am running in the background.", QSystemTrayIcon.Information, 2000)

    def force_quit(self):
        self.tray_icon.hide()
        QApplication.quit()

    def init_logic(self):
        self.worker = SeeyaThread()
        self.worker.chat_signal.connect(self.add_message)
        self.worker.status_signal.connect(self.update_status)
        self.worker.glow_signal.connect(self.update_glow)
        self.worker.start()
        
        self.timer = QTimer()
        self.timer.timeout.connect(lambda: self.cpu_bar.setValue(int(psutil.cpu_percent())))
        self.timer.start(2000)

    def toggle_stealth(self):
        self.is_stealth_mode = not self.is_stealth_mode
        hwnd = int(self.winId())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        
        if self.is_stealth_mode:
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_TOOLWINDOW)
            self.btn_stealth.setText("Stealth: ON")
        else:
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_NONE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style & ~WS_EX_TOOLWINDOW)
            self.btn_stealth.setText("Stealth: OFF")

        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
        self.apply_theme()

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.apply_theme()

    def apply_theme(self):
        if self.is_dark_mode:
            bg_cont = "#181818"; bg_side = "#202020"; text = "#E0E0E0"
            border = "1px solid #333"; inp_bg = "#252525"; btn_bg = "#2D2D2D"; btn_hover = "#353535"
            cmd_bg = "#181818" 
        else:
            bg_cont = "#FFF"; bg_side = "#F7F7F9"; text = "#222"
            border = "1px solid #DDD"; inp_bg = "#F2F2F5"; btn_bg = "#FFF"; btn_hover = "#E5E5EA"
            cmd_bg = "#FFF"

        self.main_content.setStyleSheet(f"QFrame#MainContentFrame {{ background: {bg_cont}; border-radius: 20px; border: {border}; }} QLabel {{ color: {text}; font-family: 'Segoe UI'; }}")
        self.sidebar.setStyleSheet(f"QFrame#SidebarFrame {{ background: {bg_side}; border-radius: 20px; border: {border}; }} QLabel {{ color: {text}; font-family: 'Segoe UI'; }}")
        self.logo_box.setStyleSheet(f"background: {btn_bg}; border-radius: 8px; font-weight: 800; font-size: 14px; letter-spacing: 2px;")

        self.page_cmd.setStyleSheet(f"background-color: {cmd_bg}; border: none;")

        self.scroll.setStyleSheet(f"QScrollArea {{ border: none; background: transparent; }} QScrollBar:vertical {{ border: none; background: transparent; width: 0px; }} QScrollBar::handle:vertical {{ background: transparent; }}")
        self.chat_container.setStyleSheet("QWidget#ChatContainer { background: transparent; }")

        btn_base = f"QPushButton {{ background: {btn_bg}; color: {text}; border: {border}; border-radius: 12px; font-weight: 600; text-align: left; padding-left: 15px; font-size: 12px; }} QPushButton:hover {{ background: {btn_hover}; }}"
        active = f"background: {btn_hover}; color: #007AFF; border-left: 3px solid #007AFF;"
        
        self.btn_chat.setStyleSheet(btn_base + (active if self.active_btn == self.btn_chat else ""))
        self.btn_cmds.setStyleSheet(btn_base + (active if self.active_btn == self.btn_cmds else ""))
        
        util_btn = f"QPushButton {{ background: {btn_bg}; color: {text}; border: {border}; border-radius: 10px; font-weight: 600; font-size: 11px; }} QPushButton:hover {{ background: {btn_hover}; }}"

        square_btn_style = f"""
            QPushButton {{ 
                background: {btn_bg}; 
                color: {text}; 
                border: {border}; 
                border-radius: 12px; 
                font-size: 10px; 
                font-weight: bold;
            }} 
            QPushButton:hover {{ background: {btn_hover}; }}
        """
        self.btn_theme.setStyleSheet(square_btn_style)

        if self.is_stealth_mode:
            self.btn_stealth.setStyleSheet(f"""
                QPushButton {{ 
                    background: #4A148C; 
                    color: #E1BEE7; 
                    border: 1px solid #9C27B0; 
                    border-radius: 12px; 
                    font-size: 10px; 
                    font-weight: bold;
                }} 
                QPushButton:hover {{ 
                    background: #6A21CA; 
                }}
            """)
        else:
            self.btn_stealth.setStyleSheet(square_btn_style)

        if self.voice_enabled: self.btn_voice.setStyleSheet(util_btn)
        else: self.btn_voice.setStyleSheet(f"QPushButton {{ background: #444; color: #AAA; border-radius: 10px; border: {border}; }}")

        if self.worker.is_mic_muted: self.btn_mic.setStyleSheet(f"QPushButton {{ background: {'#3E2020' if self.is_dark_mode else '#FFEBEE'}; color: #D32F2F; border: 1px solid #E57373; border-radius: 10px; }}")
        else: self.btn_mic.setStyleSheet(f"QPushButton {{ background: {'#152C15' if self.is_dark_mode else '#E8F5E9'}; color: #388E3C; border: 1px solid #81C784; border-radius: 10px; }}")

        self.input_frame.setStyleSheet(f"QFrame#InputFrame {{ background: {inp_bg}; border-radius: 22px; border: {border}; }}")
        self.input_box.setStyleSheet(f"background: transparent; color: {text}; font-size: 13px;")
        self.btn_send.setStyleSheet("QPushButton { background: #22BF93; color: white; border-radius: 16px; border: none; font-size: 14px; } QPushButton:hover { background: #1a9e75; }")
        self.btn_refresh.setStyleSheet(f"QPushButton {{ background: {btn_bg}; color: {text}; border: {border}; border-radius: 8px; font-size: 11px; font-weight: bold; }} QPushButton:hover {{ background: {btn_hover}; }}")
        self.cpu_bar.setStyleSheet(f"QProgressBar {{ background: {btn_bg}; border-radius: 2px; }} QProgressBar::chunk {{ background: #007AFF; border-radius: 2px; }}")

        self.update_commands_html(text, inp_bg, border)
        self.refresh_bubbles()

    def update_commands_html(self, text_color, card_bg, border_color):
        # Clean, Minimalist Colors
        if self.is_dark_mode:
            text_main = "#FFFFFF"
            text_dim = "#B0B0B0"
            accent = "#1A8F6E" # Soft Blue
            divider = "1px solid #333"
        else:
            text_main = "#222222"
            text_dim = "#555555"
            accent = "#1A8F6E" # Soft Blue
            divider = "1px solid #EEE"

        html_content = f"""
        <style>
            body {{ 
                font-family: 'Segoe UI', sans-serif; 
                margin: 20px; 
                background: transparent; 
                line-height: 1.5;
            }}
            
            /* Main Title */
            h2 {{ 
                color: {text_main}; 
                font-size: 16px; 
                font-weight: 700; 
                margin-bottom: 20px; 
                text-transform: uppercase; 
                letter-spacing: 1px;
                border-bottom: {divider};
                padding-bottom: 10px;
            }}

            /* List Layout */
            .cmd-row {{
                margin-bottom: 14px;
                display: flex;
                align-items: baseline;
            }}

            /* Category Label (Left) */
            .cat {{
                width: 110px;
                min-width: 110px;
                color: {accent};
                font-size: 11px;
                font-weight: 800;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}

            /* Description (Right) */
            .desc {{
                color: {text_dim};
                font-size: 12px;
                font-weight: 500;
            }}

            /* Highlight keywords */
            .hl {{
                color: {text_main};
                font-weight: 600;
            }}
        </style>
        
        <h2>Command References</h2>
        
        <div class="cmd-row">
            <div class="cat">❔ ASK SEEYA</div>
            <div class="desc">Ask Questions, Get Answers from Seeya.</div>
        </div>
        <br>
        <div class="cmd-row">
            <div class="cat">👁 VISION</div>
            <div class="desc">
                <div class="desc">It can Read Screen, Find Button. Just say "Click on [Button/Screen Text]"</div>
            </div>
        </div>
        <br>
        <div class="cmd-row">
            <div class="cat">🔴 POWER/PRIVACY</div>
            <div class="desc">
                <div class="desc">Stealth Mode for You, Opacity Control of Seeya, "Shutdown", "Restart", "Lock PC"</div>
            </div>
        </div>
        <br>
        <div class="cmd-row">
            <div class="cat">🟦 WINDOWS</div>
            <div class="desc">"Minimize All", "Show Desktop", "Alt Tab"</div>
        </div>
        <br>
        <div class="cmd-row">
            <div class="cat">🚀 APPS</div>
            <div class="desc">"Open [App Name]", "Close [App Name]", "Open Task Manager", "Open Settings"</div>
        </div>
        <br>
        <div class="cmd-row">
            <div class="cat">🛠 TOOLS</div>
            <div class="desc">"Battery", "Take Screenshot", "Delete Screenshot", "Type [Text]", Control Key Functions of Keyboard/Mouse</div>
        </div>
        <br>
        <div class="cmd-row">
            <div class="cat">🎵 MEDIA</div>
            <div class="desc">"Play [Song]", "Mute", "Unmute", "Volume Up", "Volume Down"</div>
        </div>
        <br>
        <div class="cmd-row">
            <div class="cat">📂 FILES</div>
            <div class="desc">"Open C Drive", "Open Downloads"</div>
        </div>
        <br>
        <div class="cmd-row">
            <div class="cat">🌐 WEB</div>
            <div class="desc">"Search [Query]", "Open YouTube", "Open Google"</div>
        </div>
        <br>
        <div class="cmd-row">
            <div class="cat">📅 MISC</div>
            <div class="desc">"Date", "Time", "Tell me a Joke" and many more...</div><br><br>
            <br><br><pre>For Information/Support: seeya.ai.help@gmail.com</pre><p>© 2026 Seeya AI. All rights reserved.</p>
        </div>
        """
        self.page_cmd.setHtml(html_content)
    
    def toggle_voice_output(self):
        self.voice_enabled = not self.voice_enabled
        logic.toggle_voice_mute()
        self.btn_voice.setText("🔊" if self.voice_enabled else "🔇")
        self.apply_theme()

    def toggle_mic_input(self):
        try:
            self.worker.is_mic_muted = not self.worker.is_mic_muted

            if self.worker.is_mic_muted:
                self.btn_mic.setText("🎙️") 
                self.input_box.setPlaceholderText("Mic Muted. Unmute or type Here...")
            else:
                self.btn_mic.setText("🟢")
                self.input_box.setPlaceholderText("Speak or type here...")

            self.apply_theme()
            
        except Exception as e:
            print(f"Error toggling mic: {e}")

    def change_opacity(self, value):
        self.setWindowOpacity(value / 100.0)

    def add_message(self, sender, text):
        if sender == "Seeya" and self.current_thinking_widget:
            self.current_thinking_widget.deleteLater(); self.current_thinking_widget = None
        
        row = QWidget(); ly = QHBoxLayout(row); ly.setContentsMargins(0,0,0,0)
        text = text.replace('\n', '<br>')
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        
        lbl = QLabel(text); lbl.setWordWrap(True); lbl.setFont(QFont("Segoe UI", 11)); lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        
        u_bg = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1ec9ad, stop:1 #19b3a1)"
        s_bg = "#252525" if self.is_dark_mode else "#F0F0F5"
        txt = "#FFF" if self.is_dark_mode else "#222"

        if sender == "You":
            lbl.setStyleSheet(f"background: {u_bg}; color: white; padding: 8px 14px; border-radius: 16px; border-bottom-right-radius: 2px;")
            ly.addStretch(); ly.addWidget(lbl)
        elif sender == "Thinking":
            lbl.setText("Thinking..."); lbl.setStyleSheet("color: #888; font-style: italic; font-size: 11px;")
            ly.addWidget(lbl); ly.addStretch(); self.current_thinking_widget = row
        else:
            lbl.setStyleSheet(f"background: {s_bg}; color: {txt}; padding: 8px 14px; border-radius: 16px; border-bottom-left-radius: 2px;")
            ly.addWidget(lbl); ly.addStretch()
        
        self.msg_layout.addWidget(row)
        QTimer.singleShot(10, lambda: self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum()))

    def refresh_bubbles(self):
        for i in range(self.msg_layout.count()):
            item = self.msg_layout.itemAt(i)
            if item.widget():
                lbl = item.widget().findChild(QLabel)
                if lbl and "Thinking" not in lbl.text() and item.widget().layout().alignment() != Qt.AlignRight:
                     bg = "#252525" if self.is_dark_mode else "#F0F0F5"
                     txt = "#FFF" if self.is_dark_mode else "#222"
                     lbl.setStyleSheet(f"background: {bg}; color: {txt}; padding: 8px 14px; border-radius: 16px; border-bottom-left-radius: 2px;")

    def process_text(self):
        text = self.input_box.text().strip()
        if not text: return
        self.input_box.clear(); self.add_message("You", text)
        threading.Thread(target=self.worker.process_command, args=(text,)).start()

    def update_status(self, text):
        if not self.worker.is_mic_muted: self.lbl_status.setText("● " + text)
    
    def update_glow(self, is_speaking):
        self.lbl_status.setStyleSheet(f"color: {"#1A9F9A" if is_speaking else "#16AD80"}; font-weight: bold;")

    def refresh_chat(self):
        while self.msg_layout.count():
            item = self.msg_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        
        self.add_message("Seeya", "Chat cleared.")

        QTimer.singleShot(2000, self.remove_last_message)

    def remove_last_message(self):
        if self.msg_layout.count() > 0:
            item = self.msg_layout.itemAt(self.msg_layout.count() - 1)
            if item.widget():
                item.widget().deleteLater()

    def create_nav_btn(self, text, idx, active=False):
        btn = QPushButton(text); btn.setCursor(Qt.PointingHandCursor); btn.setFixedHeight(34)
        btn.clicked.connect(lambda: self.set_page(idx, btn))
        self.side_layout.addWidget(btn)
        if active: self.active_btn = btn; self.pages.setCurrentIndex(idx)
        return btn

    def set_page(self, idx, btn):
        self.pages.setCurrentIndex(idx); self.active_btn = btn; self.apply_theme()

    def toggle_maximize(self):
        if self.is_maximized_custom: self.setGeometry(self.old_pos); self.is_maximized_custom = False
        else: self.old_pos = self.geometry(); self.setGeometry(QApplication.primaryScreen().availableGeometry()); self.is_maximized_custom = True
        
    def resizeEvent(self, event):
        rect = self.rect()
        self.sizegrip.move(rect.right() - self.sizegrip.width(), rect.bottom() - self.sizegrip.height())
        super().resizeEvent(event)

    def mousePressEvent(self, e):
        if e.pos().x() > self.width() - 20 and e.pos().y() > self.height() - 20:
            return 

        if not self.is_maximized_custom and e.button() == Qt.LeftButton: 
            self.drag_pos = e.globalPos()
    def mouseMoveEvent(self, e):
        if hasattr(self, 'drag_pos'): self.move(self.x()+(e.globalPos()-self.drag_pos).x(), self.y()+(e.globalPos()-self.drag_pos).y()); self.drag_pos = e.globalPos()
    def mouseReleaseEvent(self, e): delattr(self, 'drag_pos') if hasattr(self, 'drag_pos') else None

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI"))
    window = SeeyaDashboard()
    window.show()
    sys.exit(app.exec_())
