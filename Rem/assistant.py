import sys
import os
import random
import threading
import json
import webbrowser
import subprocess
import io
import configparser

import google.generativeai as genai
import speech_recognition as sr
import pygame
from gtts import gTTS
import pygetwindow as gw
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
        QMessageBox.information(self, "Ayarlar Kaydedildi", "Ayarlar başarıyla kaydedildi. Lütfen uygulamayı yeniden başlatın.")
        self.accept()

class DesktopAssistant(QWidget):
    response_ready = pyqtSignal(str)
    move_decision_ready = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.response_ready.connect(self.handle_ai_response)
        self.move_decision_ready.connect(self.handle_ai_response)
        self.config_path = 'config.ini'
        self.config = self.load_or_create_config()
        
        self.command_map = {
            "uyku_modu": self.enter_sleep_mode,
            "uygulamayi_kapat": self.shutdown_assistant,
            "dans_et": self.do_a_dance,
            "rastgele_yuruyus": self.perform_random_walk
        }
        
        self.special_commands_text = self.load_special_commands()
        try:
            pygame.mixer.init()
            print("Pygame mixer başarıyla başlatıldı.")
        except Exception as e:
            print(f"Hata: Pygame mixer başlatılamadı. Hata: {e}")
        
        self.main_system_prompt = f"""
            Sen, Re:Zero animesindeki Rem karakteri gibi davranan, çok yetenekli bir AI masaüstü asistanısın.
            Kullanıcının isteklerini analiz eder ve bu istekleri yerine getirmek için elindeki araçları ve özel komutları kullanırsın.
            
            DIŞ ARAÇLAR (Bilgi almak veya dış dünyayı etkilemek için):
            1. `execute_python`, 2. `search_and_summarize`, 3. `get_weather`, 4. `control_spotify`

            İÇSEL ÖZEL KOMUTLAR (Karakterin kendi eylemleri için):
            {self.special_commands_text}
            
            KARAR VERME SÜRECİN:
            Kullanıcının isteğini dikkatlice oku ve hangi DIŞ ARACA veya İÇSEL ÖZEL KOMUTA uyduğuna karar ver.
            Ardından, ilgili formatta bir JSON çıktısı üret.
            
            JSON FORMATLARI:
            - Dış Araçlar: {{"eylem": "tool_name", "parametre": "değer"}} (Örn: {{"eylem": "get_weather", "sehir": "istanbul"}})
            - Özel Komut: {{"eylem": "special_command", "komut": "uyku_modu"}}
            
            Eğer istek hiçbirine uymuyorsa, JSON üretme, sadece normal sohbet et.
        """
        
        # ... Geri kalan __init__ kodları aynı ...
        self.move_system_prompt = """
            Sen, bir bilgisayar ekranını analiz eden uzman bir "Görsel Analiz Yapay Zekası"sın.
            Görevin, sana verilen ekran görüntüsünü inceleyip karakterin ilgisini çekebilecek bir nesne (ikon, klasör, pencere köşesi, buton vb.) bulmaktır.
            Kararını aşağıdaki JSON formatlarından BİRİ ile bildir. ASLA bu formatların dışında bir metin yazma.
            - Bir Nesne Bulduysan: {"eylem": "move_character", "hedef_x": 850, "hedef_y": 400, "dusunce": "Masaüstündeki bir klasör ikonunu gördüm. Oraya gidiyorum."}
            - Ekranda ilginç bir şey bulamadıysan: {"eylem": "do_nothing", "dusunce": "Ekran şu an sakin, biraz burada bekleyeceğim."}
        """
        self.main_model = None; self.move_model = None; self.chat_session = None
        api_key = self.config.get('Gemini', 'api_key', fallback=None)
        if not api_key or 'YOUR_GEMINI_API_KEY' in api_key: print("UYARI: Gemini API anahtarı 'config.ini' dosyasında ayarlanmamış.")
        else:
            try:
                genai.configure(api_key=api_key)
                self.main_model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=self.main_system_prompt)
                self.chat_session = self.main_model.start_chat(history=[])
                self.move_model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=self.move_system_prompt)
                print("İki Gemini modeli de başarıyla yapılandırıldı.")
            except Exception as e: print(f"Hata: Gemini modelleri yapılandırılamadı. Hata: {e}")
        self.recognizer = sr.Recognizer(); self.is_listening = False
        self.wake_word = self.config.get('Assistant', 'wake_word', fallback='rem').lower()
        self.text_input_speak_response = self.config.getboolean('Assistant', 'text_input_speak_response', fallback=True)
        self.last_input_was_voice = False
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.main_layout = QVBoxLayout(); self.main_layout.setContentsMargins(0, 0, 0, 0); self.setLayout(self.main_layout)
        self.speech_bubble = QLabel(self); self.speech_bubble.setStyleSheet("background-color: white; color: black; border-radius: 10px; padding: 10px; font-size: 14px;"); self.speech_bubble.setWordWrap(True); self.speech_bubble.hide()
        self.character_label = QLabel(self); self.main_layout.addWidget(self.speech_bubble); self.main_layout.addWidget(self.character_label, alignment=Qt.AlignCenter)
        self.animations = {}; self.load_animations(); self.current_state = 'idle'; self.animation_frame = 0
        self.drag_position = QPoint(); self.is_moving = False; self.target_pos = self.pos()
        self.animation_timer = QTimer(self); self.animation_timer.timeout.connect(self.update_animation); self.animation_timer.start(150)
        self.action_timer = QTimer(self); self.action_timer.timeout.connect(self.decide_new_action); self.action_timer.start(20000)
        self.set_character_image(); self.show(); print("Asistan hazır. Etkileşim için sağ tıklayın veya Ctrl+Sağ Tık yapın.")

    def enter_sleep_mode(self):
        self.set_state('sleeping')
        return "Tatlı rüyalar, efendim."

    def shutdown_assistant(self):
        self.show_speech_bubble("Görüşmek üzere, efendim.", force_speak=True)
        QTimer.singleShot(2000, self.close) # 2 saniye sonra kapan
        return ""

    def do_a_dance(self):
        self.set_state('happy')
        return "İşte böyle! Dans zamanı!"

    def perform_random_walk(self):
        self.start_random_walk()
        return "Hemen bir keşfe çıkıyorum!"
    
    def load_special_commands(self):
        try:
            with open('special_commands.json', 'r', encoding='utf-8') as f:
                commands = json.load(f)
                text_format = "\n".join([f"- `{key}`: {desc}" for key, desc in commands.items()])
                print("Özel komutlar başarıyla yüklendi.")
                return text_format
        except Exception as e:
            print(f"UYARI: `special_commands.json` dosyası okunamadı. Hata: {e}")
            return "Özel komutlar yüklenemedi."

    def load_or_create_config(self):
        config = configparser.ConfigParser()
        if not os.path.exists(self.config_path):
            config['Gemini'] = {'api_key': 'YOUR_GEMINI_API_KEY_HERE'}
            config['Assistant'] = {'wake_word': 'rem', 'text_input_speak_response': 'true'}
            config['Spotify'] = {'client_id': 'YOUR_CLIENT_ID_HERE', 'client_secret': 'YOUR_CLIENT_SECRET_HERE', 'redirect_uri': 'http://localhost:8888/callback'}
            with open(self.config_path, 'w') as configfile: config.write(configfile)
        config.read(self.config_path)
        return config

    def handle_ai_response(self, response_text):
        if not response_text:
            self.set_state('idle'); return
        try:
            if response_text.startswith("```json"): response_text = response_text.strip()[7:-3].strip()
            data = json.loads(response_text)
            eylem = data.get("eylem")
            result_text = "Anlayamadığım bir eylem formatı döndü."
            
            if eylem == "execute_python": result_text = self.execute_python_code(data.get("kod"))
            elif eylem == "search_and_summarize": result_text = tools.search_and_summarize(data.get("sorgu"))
            elif eylem == "get_weather": result_text = tools.get_weather(data.get("sehir"))
            elif eylem == "control_spotify": result_text = tools.control_spotify(data.get("komut"), self.config)
            
            elif eylem == "special_command":
                command_key = data.get("komut")
                # Haritada komut var mı diye kontrol et
                if command_key in self.command_map:
                    # Varsa, haritadan ilgili fonksiyonu bul ve çalıştır.
                    action_function = self.command_map[command_key]
                    result_text = action_function()
                else:
                    result_text = f"Böyle bir özel komut ('{command_key}') bilmiyorum efendim."
            
            elif eylem in ["move_character", "do_nothing"]:
                if eylem == "move_character":
                    screen_size = pyautogui.size(); hedef_x = min(max(0, data.get("hedef_x", self.x())), screen_size.width - self.width()); hedef_y = min(max(0, data.get("hedef_y", self.y())), screen_size.height - self.height())
                    print(f"AI GÖZÜ Kararı: Hareket et. Hedef: ({hedef_x}, {hedef_y}). Düşünce: {data.get('dusunce')}")
                    self.start_moving(QPoint(hedef_x, hedef_y))
                else:
                    print(f"AI GÖZÜ Kararı: Bekle. Düşünce: {data.get('dusunce')}")
                    if random.random() < 0.5: self.start_random_walk()
                    else: self.set_state('idle')
                return

            if result_text:
                self.show_speech_bubble(result_text)

        except (json.JSONDecodeError, AttributeError, ValueError):
            self.show_speech_bubble(response_text)
            
    def decide_new_action(self):
        if self.is_moving or self.speech_bubble.isVisible() or self.is_listening or not self.move_model: return
        print("Karaktere gözleri veriliyor... Ekran görüntüsü analiz ediliyor...")
        try:
            screenshot = pyautogui.screenshot()
            threading.Thread(target=self._get_move_decision_in_thread, args=(screenshot,), daemon=True).start()
        except Exception as e: print(f"Ekran görüntüsü alınırken hata oluştu: {e}")

    def _get_move_decision_in_thread(self, screenshot_img):
        try:
            prompt_parts = ["Bu ekran görüntüsünü analiz et ve bir sonraki hareketin için karar ver. JSON formatında cevap ver.", screenshot_img]
            response = self.move_model.generate_content(prompt_parts)
            self.move_decision_ready.emit(response.text.strip())
        except Exception as e:
            print(f"Görsel hareket kararı alınırken hata: {e}")
            self.move_decision_ready.emit('{"eylem": "do_nothing", "dusunce": "Görüşümde bir sorun oldu, rastgele yürüyeceğim."}')

    def process_ai_request(self, prompt, is_user_request=True):
        if is_user_request: self.is_moving = False; self.set_state('thinking')
        threading.Thread(target=self._process_in_thread, args=(prompt,), daemon=True).start()

    def _process_in_thread(self, prompt):
        if not self.chat_session: self.response_ready.emit("Sohbet oturumu başlatılamadı."); return
        try:
            response = self.chat_session.send_message(prompt)
            self.response_ready.emit(response.text.strip())
        except Exception as e: self.response_ready.emit(f"AI isteği sırasında hata: {e}")

    def open_settings_dialog(self):
        dialog = SettingsDialog(self.config_path, self); dialog.exec_()
        self.config = self.load_or_create_config()
        self.wake_word = self.config.get('Assistant', 'wake_word', fallback='rem').lower()
        self.text_input_speak_response = self.config.getboolean('Assistant', 'text_input_speak_response', fallback=True)
        print("Ayarlar güncellendi. Uygulamayı yeniden başlatmanız tavsiye edilir.")

    def hide_speech_bubble(self):
        self.speech_bubble.hide(); self.adjustSize()
        if self.current_state == 'talking': self.set_state('idle')

    def speak(self, text):
        if not text or not pygame.mixer.get_init(): return
        try:
            tts = gTTS(text=text, lang='tr'); audio_stream = io.BytesIO()
            tts.write_to_fp(audio_stream); audio_stream.seek(0)
            pygame.mixer.music.load(audio_stream, 'mp3'); pygame.mixer.music.play()
            while pygame.mixer.music.get_busy(): pygame.time.Clock().tick(10)
        except Exception as e: print(f"gTTS ile seslendirme sırasında hata: {e}")

    def show_speech_bubble(self, text, force_speak=False):
        self.set_state('talking'); self.speech_bubble.setText(text); self.speech_bubble.show(); self.speech_bubble.adjustSize(); self.adjustSize()
        should_speak = self.last_input_was_voice or self.text_input_speak_response or force_speak
        if should_speak: threading.Thread(target=self._speak_and_hide, args=(text,), daemon=True).start()
        else: QTimer.singleShot(8000, self.hide_speech_bubble)

    def _speak_and_hide(self, text):
        self.speak(self.prepare_text_for_tts(text)); self.hide_speech_bubble()
    
    def contextMenuEvent(self, event):
        if QApplication.keyboardModifiers() == Qt.ControlModifier:
            self.last_input_was_voice = False; text, ok = QInputDialog.getText(self, 'Rem\'e Metinle Sor', 'Bana ne sormak istersiniz, efendim?'); 
            if ok and text: self.process_ai_request(f"Kullanıcı şunu dedi: '{text}'")
            return
        menu = QMenu(self); toggle_listen_action = QAction('Dinlemeyi Başlat' if not self.is_listening else 'Dinlemeyi Durdur', self); toggle_listen_action.triggered.connect(self.toggle_listening); menu.addAction(toggle_listen_action)
        settings_action = QAction('Ayarlar', self); settings_action.triggered.connect(self.open_settings_dialog); menu.addAction(settings_action)
        menu.addSeparator(); quit_action = QAction('Çıkış', self); quit_action.triggered.connect(self.close); menu.addAction(quit_action)
        menu.exec_(self.mapToGlobal(event.pos()))
        
    def listen_for_command(self):
        self.last_input_was_voice = True; 
        with sr.Microphone() as source:
            self.process_ai_request("Kullanıcı konuşmaya başladı, dinliyorum...", is_user_request=True)
            try:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5); command = self.recognizer.recognize_google(audio, language="tr-TR")
                print(f"Komut algılandı: {command}"); self._process_in_thread(f"Kullanıcı şunu dedi: '{command}'")
            except (sr.UnknownValueError, sr.WaitTimeoutError): self.response_ready.emit("Üzgünüm efendim, anlayamadım.")
            except Exception as e: self.response_ready.emit(f"Bir hata oluştu: {e}")
            
    def toggle_listening(self):
        self.is_listening = not self.is_listening
        if self.is_listening: self.show_speech_bubble("Dinlemeye başlıyorum...", force_speak=True); self.start_listening_thread()
        else: self.show_speech_bubble("Dinleme durduruldu.", force_speak=True); print("Dinleme durduruldu.")
        
    def prepare_text_for_tts(self, text): return text.replace(',', ', ... ').replace('.', '. ... ')
    
    def execute_python_code(self, code_string):
        reply = QMessageBox.question(self, 'Onay', f"Efendim, aşağıdaki kodu çalıştırmak istediğimden emin misiniz?\n\n---\n{code_string}\n---", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                result = subprocess.run(['python', '-c', code_string], capture_output=True, text=True, check=True, timeout=15)
                return f"İşte komutun çıktısı:\n{result.stdout or 'Komutu başarıyla çalıştırdım efendim.'}"
            except subprocess.CalledProcessError as e: return f"Kodu çalıştırırken bir hata oluştu:\n{e.stderr}"
            except subprocess.TimeoutExpired: return "Komutun çalışması çok uzun sürdü, bu yüzden iptal ettim."
            except Exception as e: return f"Beklenmedik bir hata oluştu: {e}"
        else: return "Anlaşıldı efendim, isteğiniz iptal edildi."
        
    def start_listening_thread(self): threading.Thread(target=self.listen_for_wake_word, daemon=True).start()
    
    def listen_for_wake_word(self):
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            print(f"Uyandırma kelimesi '{self.wake_word}' bekleniyor...")
            while self.is_listening:
                try:
                    audio = self.recognizer.listen(source); text = self.recognizer.recognize_google(audio, language="tr-TR").lower()
                    if self.wake_word in text: print("Uyandırma kelimesi algılandı!"); self.listen_for_command()
                except sr.UnknownValueError: pass
                except sr.RequestError as e: print(f"Ses tanıma servisi hatası; {e}"); self.is_listening = False
                
    def closeEvent(self, event): pygame.quit(); event.accept()
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton: self.drag_position = event.globalPos() - self.frameGeometry().topLeft(); event.accept()
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton: self.move(event.globalPos() - self.drag_position); event.accept()
        
    def load_animations(self):
        animation_files = { 'idle': ['idle.png'], 'idle_left': ['idle_left.png'], 'idle_right': ['idle_right.png'], 'talking': ['talking.png'], 'thinking': ['thinking.png'], 'sleeping': ['sleeping.png'], 'walk_right': ['walk_right_1.png', 'walk_right_2.png'], 'walk_left': ['walk_left_1.png', 'walk_left_2.png'], 'happy': ['talking.png']}
        for state, files in animation_files.items():
            pixmaps = [QPixmap(file) for file in files if os.path.exists(file)]
            if not pixmaps and state == 'idle': sys.exit(print("Hata: Temel 'idle.png' animasyon dosyası bulunamadı!"))
            if pixmaps: self.animations[state] = pixmaps
        
    def update_animation(self):
        if self.current_state.startswith('idle') and not self.is_moving: self.follow_mouse()
        if self.animations.get(self.current_state): self.animation_frame = (self.animation_frame + 1) % len(self.animations.get(self.current_state))
        if self.is_moving: self.move_towards_target()
        self.set_character_image()
        
    def follow_mouse(self):
        cursor_x = QCursor.pos().x(); character_center_x = self.pos().x() + self.width() / 2
        if cursor_x < character_center_x - 50: self.set_state('idle_left')
        elif cursor_x > character_center_x + 50: self.set_state('idle_right')
        else: self.set_state('idle')
        
    def set_character_image(self):
        pixmap_list = self.animations.get(self.current_state)
        if pixmap_list: pixmap = pixmap_list[self.animation_frame % len(pixmap_list)]; self.character_label.setPixmap(pixmap); self.character_label.adjustSize(); self.adjustSize()
        
    def start_moving(self, target_pos):
        if self.is_moving: return
        self.target_pos = target_pos; self.is_moving = True
        if self.target_pos.x() > self.x(): self.set_state('walk_right')
        else: self.set_state('walk_left')
        
    def move_towards_target(self):
        if not self.is_moving: return
        current_pos = self.pos(); direction_x = self.target_pos.x() - current_pos.x(); direction_y = self.target_pos.y() - current_pos.y()
        if abs(direction_x) < 5 and abs(direction_y) < 5: self.is_moving = False; self.set_state('idle'); return
        step = 5; new_x = current_pos.x(); new_y = current_pos.y()
        if direction_x != 0: new_x += step if direction_x > 0 else -step
        if direction_y != 0: new_y += step if direction_y > 0 else -step
        self.move(new_x, new_y)

    def start_random_walk(self):
        if self.is_moving: return
        screen_geom = QApplication.desktop().screenGeometry()
        target_x = random.randint(0, screen_geom.width() - self.width())
        target_y = random.randint(0, screen_geom.height() - self.height())
        print(f"Kod Kararı: Rastgele keşif yürüyüşü. Hedef: ({target_x}, {target_y})")
        self.start_moving(QPoint(target_x, target_y))

    def set_state(self, state):
        if self.current_state != state: self.current_state = state; self.animation_frame = 0

if __name__ == '__main__':
    app = QApplication(sys.argv)
    assistant = DesktopAssistant()

    sys.exit(app.exec_())
