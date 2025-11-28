import sys
import os
import random
import threading
import json
import io
import configparser
import time
import subprocess

from google import genai
from google.genai import types

import speech_recognition as sr
import pygame
from gtts import gTTS
import pyautogui
from PIL import Image

from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QInputDialog, QVBoxLayout, 
                             QMessageBox, QAction, QMenu, QDialog, QLineEdit,
                             QPushButton, QFormLayout, QCheckBox)
from PyQt5.QtGui import QPixmap, QCursor
from PyQt5.QtCore import Qt, QTimer, QPoint, pyqtSignal

import tools

class SettingsDialog(QDialog):
    def __init__(self, config_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ayarlar")
        self.config_path = config_path
        self.config = configparser.ConfigParser()
        self.config.read(self.config_path)

        layout = QFormLayout(self)
        
        self.api_key_input = QLineEdit(self)
        self.api_key_input.setText(self.config.get('Gemini', 'api_key', fallback=''))
        self.api_key_input.setEchoMode(QLineEdit.Password)
        layout.addRow("Gemini API Anahtarı:", self.api_key_input)
        
        self.wake_word_input = QLineEdit(self)
        self.wake_word_input.setText(self.config.get('Assistant', 'wake_word', fallback='rem'))
        layout.addRow("Uyandırma Kelimesi:", self.wake_word_input)
        
        self.speak_response_checkbox = QCheckBox(self)
        is_checked = self.config.getboolean('Assistant', 'text_input_speak_response', fallback=True)
        self.speak_response_checkbox.setChecked(is_checked)
        layout.addRow("Metin Girişinde Sesli Yanıt:", self.speak_response_checkbox)
        
        self.spotify_id_input = QLineEdit(self)
        self.spotify_id_input.setText(self.config.get('Spotify', 'client_id', fallback=''))
        layout.addRow("Spotify Client ID:", self.spotify_id_input)
        
        self.spotify_secret_input = QLineEdit(self)
        self.spotify_secret_input.setText(self.config.get('Spotify', 'client_secret', fallback=''))
        self.spotify_secret_input.setEchoMode(QLineEdit.Password)
        layout.addRow("Spotify Client Secret:", self.spotify_secret_input)
        
        self.save_button = QPushButton("Kaydet ve Kapat", self)
        self.save_button.clicked.connect(self.save_settings)
        layout.addRow(self.save_button)

    def save_settings(self):
        if not self.config.has_section('Gemini'): self.config.add_section('Gemini')
        self.config.set('Gemini', 'api_key', self.api_key_input.text())
        if not self.config.has_section('Assistant'): self.config.add_section('Assistant')
        self.config.set('Assistant', 'wake_word', self.wake_word_input.text())
        self.config.set('Assistant', 'text_input_speak_response', 'true' if self.speak_response_checkbox.isChecked() else 'false')
        if not self.config.has_section('Spotify'): self.config.add_section('Spotify')
        self.config.set('Spotify', 'client_id', self.spotify_id_input.text())
        self.config.set('Spotify', 'client_secret', self.spotify_secret_input.text())
        self.config.set('Spotify', 'redirect_uri', 'http://localhost:8888/callback')
        
        with open(self.config_path, 'w') as configfile:
            self.config.write(configfile)
        QMessageBox.information(self, "Ayarlar Kaydedildi", "Değişikliklerin geçerli olması için uygulamayı yeniden başlatın.")
        self.accept()

class DesktopAssistant(QWidget):
    response_ready = pyqtSignal(str)
    move_decision_ready = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        
        self.response_ready.connect(self.handle_ai_response)
        self.move_decision_ready.connect(self.handle_move_decision)
        
        self.config_path = 'config.ini'
        self.config = self.load_or_create_config()

        self.long_term_memory = self.load_long_term_memory()
        memory_text = "\n".join([f"- {m}" for m in self.long_term_memory])
        
        self.command_map = {
            "uyku_modu": self.enter_sleep_mode,
            "uygulamayi_kapat": self.shutdown_assistant,
            "dans_et": self.do_a_dance,
            "rastgele_yuruyus": self.perform_random_walk
        }
        self.special_commands_text = self.load_special_commands()
        
        try: pygame.mixer.init()
        except Exception as e: print(f"Ses sistemi hatası: {e}")
            
        self.main_system_prompt = f"""
            Sen Re:Zero'dan Rem karakterisin. Sadık, yetenekli ve biraz esprili bir masaüstü asistanısın.
            Normal sohbetlerde Re:Zero edebi serisindeki sevecen herkesin sevdiği Rem gibi davran.
            
            ŞU ANA KADAR SENİN HAKKINDA VE KULLANICI HAKKINDA BİLDİKLERİM (UZUN SÜRELİ HAFIZA): 
            {memory_text}

            KULLANABİLECEĞİN ARAÇLAR:
            1. `save_memory`: ÖNEMLİ bilgileri kalıcı hafızana kaydetmek için.
                - Parametre: Kaydedilecek bilgi (Örn: "Kullanıcı çileği sever", "Projenin son teslim tarihi Cuma").
                - KURAL: Her şeyi kaydetme! Kullanıcı ile arandaki ilişkiye bak:
                  * Eğer ilişki RESMİ ise: Sadece projeleri, görevleri ve tarihleri kaydet.
                  * Eğer ilişki SAMİMİ ise: Kullanıcının sevdiklerini, hobilerini ve kişisel detayları da kaydet.
                  * Gereksiz "nasılsın", "günaydın" gibi sohbetleri ASLA kaydetme. (Eğer özel bir an değilse örneğin sana yazılmış bir şiir.)
	    2. `open_app`: Bilgisayardaki yüklü uygulama veya oyunları açmak için bunu kullan.
		- Parametre: Uygulamanın veya oyunun bilinen adı (örn: "Honkai", "Chrome", "Valorant").
		- Asla `execute_python` ile .exe yolu tahmin etmeye çalışma, `open_app` kullan.
            3. `execute_python`: Sadece hesaplama yapmak, dosya oluşturmak veya sistem ayarları için kullan.
            4. `search_and_summarize`: İnternetten bilgi aramak için.
            5. `get_weather`: Hava durumu için.
            6. `control_spotify`: Müzik kontrolü için.
            
            ÖZEL KOMUTLAR:
            {self.special_commands_text}

            ÇOK ÖNEMLİ KURALLAR:
            1. Kullanıcı nazik bir dil ile sana kendini kapatmanı istediğinde kendi programını kapat. Bu bir veda değil, bir daha buluşmak üzere daha iyi anılar biriktirmek için bir ücret!
            2. Eğer bir araç (tool) kullanacaksan, SADECE JSON çıktısı ver. Ekstra metin yazma. Söylemek istediğin şeyi JSON içindeki "yanit" kısmına yaz.
            
            YANIT FORMATI (JSON ŞABLONLARI):
            
            Durum 1 Örnek: Hafızaya Kayıt
            {{
                "eylem": "save_memory", 
                "parametre": "Kullanıcının adı Behlül", 
                "yanit": "Memnun oldum Behlül-sama, isminizi hafızama kazıdım."
            }}
            
            Durum 2 Örnek: Hava Durumu / Arama / Uygulama Açma vb.
            {{
                "eylem": "tool_name", 
                "parametre": "değer", 
                "yanit": "Kullanıcıya o an söylenecek tatlı/bilgilendirici cümle."
            }}

            Durum 3 Örnek: Özel Komut (Kapanma, Dans vb.)
            {{
                "eylem": "special_command", 
                "komut": "komut_adi"
            }}

            Durum 4: Sadece Sohbet (Araç yoksa)
            JSON kullanma, doğrudan samimi bir şekilde cevap ver.
        """
        
        self.vision_system_prompt = """
            Sen masaüstü karakterinin Gözlerisin.
            Görevin ekran görüntüsünü analiz edip karakterin gidebileceği mantıklı bir nokta bulmak.
            YANIT FORMATI (Sadece JSON): {"hedef_x": 100, "hedef_y": 100, "dusunce": "..."}
        """

        self.client = None
        self.chat_session = None
        
        api_key = self.config.get('Gemini', 'api_key', fallback=None)
        
        if not api_key or 'YOUR_KEY' in api_key:
            print("UYARI: API Anahtarı eksik!")
        else:
            try:
                self.client = genai.Client(api_key=api_key)
                self.chat_session = self.client.chats.create(
                    model="gemini-2.5-flash",
                    config=types.GenerateContentConfig(
                        system_instruction=self.main_system_prompt
                    )
                )
                print("Gemini 2.5 Sistemleri Çevrimiçi.")
            except Exception as e:
                print(f"Yapay Zeka Bağlantı Hatası: {e}")

        self.recognizer = sr.Recognizer()
        self.is_listening = False
        self.wake_word = self.config.get('Assistant', 'wake_word', fallback='rem').lower()
        self.text_input_speak_response = self.config.getboolean('Assistant', 'text_input_speak_response', fallback=True)
        self.last_input_was_voice = False
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_layout)
        
        self.speech_bubble = QLabel(self)
        self.speech_bubble.setStyleSheet("background-color: white; color: black; border-radius: 10px; padding: 10px; font-size: 14px; border: 1px solid gray;")
        self.speech_bubble.setWordWrap(True)
        self.speech_bubble.hide()
        
        self.character_label = QLabel(self)
        self.main_layout.addWidget(self.speech_bubble)
        self.main_layout.addWidget(self.character_label, alignment=Qt.AlignCenter)
        
        self.animations = {}
        self.load_animations()
        self.current_state = 'idle'
        self.animation_frame = 0
        self.drag_position = QPoint()
        self.is_moving = False
        self.target_pos = self.pos()
        
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_timer.start(150)
        
        self.action_timer = QTimer(self)
        self.action_timer.timeout.connect(self.decide_new_action)
        self.action_timer.start(30000)
        
        self.set_character_image()
        self.show()
        print("Rem masaüstüne indi.")

    def load_long_term_memory(self):
        """Hafıza dosyasını yükler, yoksa boş liste döner."""
        if os.path.exists('memory.json'):
            try:
                with open('memory.json', 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: return []
        return []

    def save_to_memory(self, knowledge):
        """Yeni bilgiyi hafızaya ekler."""
        if knowledge not in self.long_term_memory:
            self.long_term_memory.append(knowledge)
            with open('memory.json', 'w', encoding='utf-8') as f:
                json.dump(self.long_term_memory, f, ensure_ascii=False, indent=4)
            return f"Kaydedildi: '{knowledge}'"
        return "Zaten biliyorum."

    def enter_sleep_mode(self):
        self.set_state('sleeping')
        return "İyi geceler efendim..."
    
    def shutdown_assistant(self):
        self.show_speech_bubble("Görüşmek üzere efendim.", force_speak=True)
        QTimer.singleShot(2000, self.close)
        return ""
        
    def do_a_dance(self):
        self.set_state('happy')
        return "Mutluluk dansı!"
        
    def perform_random_walk(self):
        self.start_random_walk()
        return "Biraz etrafı gezeyim."
        
    def load_special_commands(self):
        try:
            with open('special_commands.json', 'r', encoding='utf-8') as f:
                commands = json.load(f)
                return "\n".join([f"- `{k}`: {v}" for k, v in commands.items()])
        except: return "Özel komutlar yüklenemedi."

    def load_or_create_config(self):
        config = configparser.ConfigParser()
        if not os.path.exists(self.config_path):
            config['Gemini'] = {'api_key': 'YOUR_KEY'}
            config['Assistant'] = {'wake_word': 'rem', 'text_input_speak_response': 'true'}
            config['Spotify'] = {'client_id': '', 'client_secret': '', 'redirect_uri': ''}
            with open(self.config_path, 'w') as f: config.write(f)
        config.read(self.config_path)
        return config

    def decide_new_action(self):
        if self.is_moving or self.speech_bubble.isVisible() or self.is_listening or not self.client:
            return
        threading.Thread(target=self._capture_and_analyze_screen, daemon=True).start()

    def _capture_and_analyze_screen(self):
        try:
            screenshot = pyautogui.screenshot()
            base_width = 1024
            w_percent = (base_width / float(screenshot.size[0]))
            h_size = int((float(screenshot.size[1]) * float(w_percent)))
            screenshot = screenshot.resize((base_width, h_size), Image.Resampling.LANCZOS)
            
            prompt = "Ekran görüntüsüne bak ve karakterin gitmesi için mantıklı bir yer seç. Koordinatları JSON ver."
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[prompt, screenshot],
                config=types.GenerateContentConfig(
                    system_instruction=self.vision_system_prompt
                )
            )
            self.move_decision_ready.emit(response.text.strip())
        except Exception as e:
            print(f"Görsel analiz hatası: {e}")

    def handle_move_decision(self, response_text):
        try:
            if response_text.startswith("```json"): response_text = response_text.strip()[7:-3].strip()
            elif response_text.startswith("```"): response_text = response_text.split("```")[1].strip()
            
            data = json.loads(response_text)
            target_x = data.get("hedef_x")
            target_y = data.get("hedef_y")
            
            if target_x is not None:
                screen_w, screen_h = pyautogui.size()
                target_x = max(0, min(target_x, screen_w - 100))
                target_y = max(0, min(target_y, screen_h - 100))
                self.start_moving(QPoint(target_x, target_y))
        except: pass

    def handle_ai_response(self, response_text):
        if not response_text: return
        print(f"AI Ham Yanıtı: {response_text}")

        try:
            clean_text = response_text
            if "```json" in clean_text: clean_text = clean_text.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_text: clean_text = clean_text.split("```")[1].strip()
            
            if clean_text.startswith("{"):
                data = json.loads(clean_text)
                eylem = data.get("eylem")
                param = data.get("parametre")
                
                # SAMİMİ CEVAP KONTROLÜ
                ai_samimi_cevap = data.get("yanit") 
                
                result_text = "..."
                
                if eylem == "execute_python": 
                    kod = param or data.get("kod")
                    if ai_samimi_cevap: self.show_speech_bubble(ai_samimi_cevap)
                    result_text = self.execute_python_code(kod)

                elif eylem == "open_app":
                    isim = param or data.get("isim")
                    if ai_samimi_cevap: self.show_speech_bubble(ai_samimi_cevap)
                    result_text = tools.open_application(isim)

                elif eylem == "save_memory":
                    bilgi = param or data.get("bilgi")
                    log = self.save_to_memory(bilgi)
                    print(f"SİSTEM LOGU: {log}")
                    # Samimi cevabı göster, yoksa varsayılanı göster
                    if ai_samimi_cevap: result_text = ai_samimi_cevap
                    else: result_text = "Bunu not ettim efendim."

                elif eylem == "search_and_summarize": 
                    sorgu = param or data.get("sorgu")
                    if ai_samimi_cevap: self.show_speech_bubble(ai_samimi_cevap)
                    
                    sonuclar = tools.search_and_summarize(sorgu)
                    if sonuclar:
                        prompt = f"Soru: {sorgu}\nArama Sonuçları: {sonuclar}\nGörevin: Sonuçları oku ve cevabı söyle."
                        try:
                            resp = self.client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                            result_text = resp.text.strip()
                        except: result_text = "Bulamadım."
                    else: result_text = "Sonuç yok."
                    
                elif eylem == "get_weather": 
                    sehir = param or data.get("sehir")
                    if ai_samimi_cevap: self.show_speech_bubble(ai_samimi_cevap)
                    result_text = tools.get_weather(sehir)
                    
                elif eylem == "control_spotify": 
                    komut = param or data.get("komut")
                    result_text = tools.control_spotify(komut, self.config)
                    
                elif eylem == "special_command":
                    cmd = param or data.get("komut")
                    if cmd in self.command_map: result_text = self.command_map[cmd]()
                
                # Eğer result_text doluysa ve ekranda henüz bir baloncuk yoksa göster
                if result_text and not self.speech_bubble.isVisible(): 
                    self.show_speech_bubble(result_text)
                elif result_text and eylem not in ["save_memory", "open_app", "execute_python"]: 
                    self.show_speech_bubble(result_text)
            else:
                self.show_speech_bubble(response_text)
        except Exception as e:
            print(f"Hata: {e}")
            self.show_speech_bubble(response_text)

    def process_ai_request(self, prompt, is_user_request=True):
        if is_user_request: 
            self.is_moving = False
            self.set_state('thinking')
        threading.Thread(target=self._process_in_thread, args=(prompt,), daemon=True).start()

    def _process_in_thread(self, prompt):
        if not self.chat_session: 
            self.response_ready.emit("Hata: AI bağlantısı yok.")
            return
        try:
            response = self.chat_session.send_message(prompt)
            self.response_ready.emit(response.text.strip())
        except Exception as e:
            self.response_ready.emit(f"Hata: {e}")

    def execute_python_code(self, code_string):
        if not code_string: return "Kod boş."
        reply = QMessageBox.question(self, 'Onay', f"Kod çalıştırılsın mı?\n\n{code_string}", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                result = subprocess.run([sys.executable, '-c', code_string], capture_output=True, text=True, timeout=10)
                return f"Sonuç:\n{result.stdout}\n{result.stderr}"
            except Exception as e: return f"Hata: {e}"
        return "İptal."

    def open_settings_dialog(self):
        dialog = SettingsDialog(self.config_path, self)
        dialog.exec_()
        self.config = self.load_or_create_config()

    def speak(self, text):
        if not text: return
        try:
            tts = gTTS(text=text, lang='tr')
            audio_stream = io.BytesIO()
            tts.write_to_fp(audio_stream)
            audio_stream.seek(0)
            pygame.mixer.music.load(audio_stream, 'mp3')
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy(): pygame.time.Clock().tick(10)
        except: pass

    def show_speech_bubble(self, text, force_speak=False):
        if self.current_state != 'sleeping':
            self.set_state('talking')
        self.speech_bubble.setText(text)
        self.speech_bubble.show()
        self.speech_bubble.adjustSize()
        self.adjustSize()
        should_speak = self.last_input_was_voice or self.text_input_speak_response or force_speak
        if should_speak: threading.Thread(target=self._speak_and_hide, args=(text,), daemon=True).start()
        else: QTimer.singleShot(5000 + len(text)*50, self.hide_speech_bubble)

    def _speak_and_hide(self, text):
        clean_text = text.replace('*', '')
        self.speak(clean_text)
        self.hide_speech_bubble()

    def hide_speech_bubble(self):
        self.speech_bubble.hide()
        self.adjustSize()
        if self.current_state == 'talking': self.set_state('idle')

    def contextMenuEvent(self, event):
        if QApplication.keyboardModifiers() == Qt.ControlModifier:
            self.last_input_was_voice = False
            text, ok = QInputDialog.getText(self, 'Soru Sor', 'Rem dinliyor:')
            if ok and text: self.process_ai_request(text)
            return
        menu = QMenu(self)
        menu.addAction('Dinlemeyi Aç/Kapa', self.toggle_listening)
        menu.addAction('Ayarlar', self.open_settings_dialog)
        menu.addAction('Çıkış', self.close)
        menu.exec_(self.mapToGlobal(event.pos()))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Tıklama anındaki fare konumunu ve pencere pozisyonunu al
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            self.is_moving = False
            self.last_mouse_x = event.globalPos().x()
            
            if event.pos().x() < self.width() / 2:
                self.set_state('climb_left')
            else:
                self.set_state('climb_right')
                
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            # Farenin anlık global konumunu al
            current_mouse_pos = event.globalPos()
            current_x = current_mouse_pos.x()
            current_y = current_mouse_pos.y()
            

            if current_x - self.last_mouse_x > 5:
                if self.current_state != 'climb_right':
                    self.set_state('climb_right')
                self.last_mouse_x = current_x
                
            elif self.last_mouse_x - current_x > 5:
                if self.current_state != 'climb_left':
                    self.set_state('climb_left')
                self.last_mouse_x = current_x

            
            target_y = current_y - 15 

            if self.current_state == 'climb_right':
                target_x = current_x - self.width() + 25 
            else:
                target_x = current_x - 25

            self.move(target_x, target_y)
            
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.set_state('fall')
            
            QTimer.singleShot(600, self.landing_animation)
            
    def landing_animation(self):
        if self.current_state == 'fall':
            self.set_state('land')
            QTimer.singleShot(600, lambda: self.set_state('idle'))

    def toggle_listening(self):
        self.is_listening = not self.is_listening
        if self.is_listening:
            self.show_speech_bubble("Dinliyorum...", force_speak=True)
            threading.Thread(target=self.listen_loop, daemon=True).start()
        else: self.show_speech_bubble("Dinleme kapalı.", force_speak=True)

    def listen_loop(self):
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source)
            while self.is_listening:
                try:
                    audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
                    text = self.recognizer.recognize_google(audio, language="tr-TR").lower()
                    if self.wake_word in text:
                        self.process_ai_request("Kullanıcı 'Rem' dedi.", is_user_request=True)
                except: pass

    def load_animations(self):
        files = {
            'idle': ['idle.png'], 
            'idle_left': ['idle_left.png'], 
            'idle_right': ['idle_right.png'],
            'talking': ['talking.png'], 
            'thinking': ['thinking.png'], 
            'sleeping': ['sleeping.png'],
            'walk_right': ['walk_right_1.png', 'walk_right_2.png'], 
            'walk_left': ['walk_left_1.png', 'walk_left_2.png'],
            'happy': ['talking.png'],
            'climb_left': ['climb_left_1.png', 'climb_left_2.png'],
            'climb_right': ['climb_right_1.png', 'climb_right_2.png'],
            'fall': ['fall_down.png'],
            'land': ['land.png']
        }
        for state, filenames in files.items():
            pixs = [QPixmap(f) for f in filenames if os.path.exists(f)]
            if pixs: self.animations[state] = pixs

    def update_animation(self):
        if self.current_state.startswith('idle') and not self.is_moving and 'climb' not in self.current_state:
            self.follow_mouse()

        pixs = self.animations.get(self.current_state, self.animations.get('idle', []))
        if pixs:
            self.animation_frame = (self.animation_frame + 1) % len(pixs)
            self.character_label.setPixmap(pixs[self.animation_frame])
            self.character_label.adjustSize(); self.adjustSize()

        if self.is_moving: self.move_towards_target()

    def follow_mouse(self):
        mx = QCursor.pos().x(); cx = self.x() + self.width() / 2
        if mx < cx - 100: self.set_state('idle_left')
        elif mx > cx + 100: self.set_state('idle_right')
        else: self.set_state('idle')

    def start_moving(self, target_pos):
        self.target_pos = target_pos; self.is_moving = True
        if target_pos.x() > self.x(): self.set_state('walk_right')
        else: self.set_state('walk_left')

    def move_towards_target(self):
        step = 5; cx, cy = self.x(), self.y()
        tx, ty = self.target_pos.x(), self.target_pos.y()
        dx, dy = tx - cx, ty - cy
        if abs(dx) < step and abs(dy) < step: self.is_moving = False; self.set_state('idle'); return
        self.move(cx + (step if dx > 0 else -step) if abs(dx) >= step else cx, cy + (step if dy > 0 else -step) if abs(dy) >= step else cy)

    def start_random_walk(self):
        screen = QApplication.primaryScreen().geometry()
        self.start_moving(QPoint(random.randint(0, screen.width()-100), random.randint(0, screen.height()-100)))

    def set_state(self, state):
        if self.current_state != state: self.current_state = state; self.animation_frame = 0; self.update_animation()
    def set_character_image(self): self.update_animation()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    assistant = DesktopAssistant()
    sys.exit(app.exec_())