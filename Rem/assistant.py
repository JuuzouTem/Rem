# ... (Tüm importlar aynı) ...
import sys, os, random, threading, json, webbrowser, subprocess, io, configparser
import google.generativeai as genai
import speech_recognition as sr
import pygame
from gtts import gTTS
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QInputDialog, QVBoxLayout, 
                             QMessageBox, QAction, QMenu, QDialog, QLineEdit,
                             QPushButton, QFormLayout, QCheckBox)
from PyQt5.QtGui import QPixmap, QCursor # <-- QCursor eklendi
from PyQt5.QtCore import Qt, QTimer, QPoint

# ... (SettingsDialog sınıfı tamamen aynı, değişiklik yok) ...
class SettingsDialog(QDialog):
    def __init__(self, config_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ayarlar"); self.config_path = config_path; self.config = configparser.ConfigParser(); self.config.read(self.config_path)
        layout = QFormLayout(self); self.api_key_input = QLineEdit(self); self.api_key_input.setText(self.config.get('Gemini', 'api_key', fallback='')); layout.addRow("Gemini API Anahtarı:", self.api_key_input)
        self.wake_word_input = QLineEdit(self); self.wake_word_input.setText(self.config.get('Assistant', 'wake_word', fallback='rem')); layout.addRow("Uyandırma Kelimesi:", self.wake_word_input)
        self.speak_response_checkbox = QCheckBox(self); is_checked = self.config.getboolean('Assistant', 'text_input_speak_response', fallback=True); self.speak_response_checkbox.setChecked(is_checked); layout.addRow("Metin Girişinde Sesli Yanıt:", self.speak_response_checkbox)
        self.save_button = QPushButton("Kaydet ve Kapat", self); self.save_button.clicked.connect(self.save_settings); layout.addRow(self.save_button)
    def save_settings(self):
        if not self.config.has_section('Gemini'): self.config.add_section('Gemini')
        self.config.set('Gemini', 'api_key', self.api_key_input.text())
        if not self.config.has_section('Assistant'): self.config.add_section('Assistant')
        self.config.set('Assistant', 'wake_word', self.wake_word_input.text())
        speak_response_value = 'true' if self.speak_response_checkbox.isChecked() else 'false'
        self.config.set('Assistant', 'text_input_speak_response', speak_response_value)
        with open(self.config_path, 'w') as configfile: self.config.write(configfile)
        QMessageBox.information(self, "Ayarlar Kaydedildi", "Ayarlar başarıyla kaydedildi. Değişikliklerin etkili olması için lütfen uygulamayı yeniden başlatın.")
        self.accept()

# -------------------------------------------------------------------
# --- Ana Asistan Sınıfı ---
# -------------------------------------------------------------------
class DesktopAssistant(QWidget):
    def __init__(self):
        # ... (init fonksiyonunun başı tamamen aynı) ...
        super().__init__()
        self.config_path = 'config.ini'; self.config = self.load_or_create_config()
        try: pygame.mixer.init(); print("Pygame mixer başarıyla başlatıldı.")
        except Exception as e: print(f"Hata: Pygame mixer başlatılamadı. Hata: {e}")
        api_key = self.config.get('Gemini', 'api_key', fallback=None)
        if not api_key or api_key == 'YOUR_GEMINI_API_KEY_HERE': print("UYARI: Gemini API anahtarı 'config.ini' dosyasında ayarlanmamış."); self.model = None
        else:
            try: genai.configure(api_key=api_key); self.model = genai.GenerativeModel('gemini-2.5-flash'); print("Gemini API başarıyla yapılandırıldı.")
            except Exception as e: print(f"Hata: Gemini API yapılandırılamadı. Hata: {e}"); self.model = None
        self.recognizer = sr.Recognizer(); self.is_listening = False; self.wake_word = self.config.get('Assistant', 'wake_word', fallback='rem').lower()
        self.text_input_speak_response = self.config.getboolean('Assistant', 'text_input_speak_response', fallback=True)
        self.last_input_was_voice = False
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool); self.setAttribute(Qt.WA_TranslucentBackground)
        self.main_layout = QVBoxLayout(); self.main_layout.setContentsMargins(0, 0, 0, 0); self.setLayout(self.main_layout)
        self.speech_bubble = QLabel(self); self.speech_bubble.setStyleSheet("background-color: white; color: black; border-radius: 10px; padding: 10px; font-size: 14px;"); self.speech_bubble.setWordWrap(True); self.speech_bubble.hide()
        self.character_label = QLabel(self); self.main_layout.addWidget(self.speech_bubble); self.main_layout.addWidget(self.character_label, alignment=Qt.AlignCenter)
        self.animations = {}; self.load_animations() 
        self.current_state = 'idle'; self.animation_frame = 0; self.drag_position = QPoint()
        self.is_moving = False; self.target_pos = self.pos()
        self.animation_timer = QTimer(self); self.animation_timer.timeout.connect(self.update_animation); self.animation_timer.start(150) 
        self.action_timer = QTimer(self); self.action_timer.timeout.connect(self.decide_new_action); self.action_timer.start(5000)
        self.set_character_image(); self.show()
        print("Asistan hazır. Etkileşim için sağ tıklayın veya Ctrl+Sağ Tık yapın.")

    # --- DEĞİŞTİRİLDİ: load_animations fonksiyonuna yeni durumlar eklendi ---
    def load_animations(self):
        animation_files = {
            'idle': ['idle.png'],
            'idle_left': ['idle_left.png'],   # <-- YENİ
            'idle_right': ['idle_right.png'], # <-- YENİ
            'talking': ['talking.png'],
            'thinking': ['thinking.png'],
            'sleeping': ['sleeping.png'],
            'walk_right': ['walk_right_1.png', 'walk_right_2.png'],
            'walk_left': ['walk_left_1.png', 'walk_left_2.png'],
            'happy': ['talking.png']
        }
        for state, files in animation_files.items():
            pixmaps = []
            for file in files:
                if os.path.exists(file):
                    pixmaps.append(QPixmap(file))
                else: # Eğer dosya bulunamazsa uyarı ver ama çökme
                    print(f"Uyarı: Animasyon dosyası bulunamadı: {file}")
            if pixmaps:
                self.animations[state] = pixmaps
        if not self.animations.get('idle'):
            sys.exit(print("Hata: Temel 'idle.png' animasyon dosyası bulunamadı!"))

    # --- DEĞİŞTİRİLDİ: update_animation fonksiyonu artık fareyi takip ediyor ---
    def update_animation(self):
        # Sadece boşta duruyorken ve hareket etmiyorken fareyi takip et
        if self.current_state.startswith('idle') and not self.is_moving:
            self.follow_mouse()

        # Animasyon karesini ilerlet (standart işlem)
        if self.animations.get(self.current_state):
            self.animation_frame = (self.animation_frame + 1) % len(self.animations.get(self.current_state))
        
        # Hareketi güncelle (standart işlem)
        if self.is_moving:
            self.move_towards_target()
        
        self.set_character_image()

    # --- YENİ: Fareyi takip etme mantığı ---
    def follow_mouse(self):
        # Farenin global X koordinatını al
        cursor_x = QCursor.pos().x()
        # Karakterin penceresinin ortasının X koordinatını al
        character_center_x = self.pos().x() + self.width() / 2
        
        # Fare karakterin solundaysa
        if cursor_x < character_center_x - 50: # 50 piksellik bir tampon bölge
            self.set_state('idle_left')
        # Fare karakterin sağındaysa
        elif cursor_x > character_center_x + 50: # 50 piksellik bir tampon bölge
            self.set_state('idle_right')
        # Fare karakterin ortasındaysa
        else:
            self.set_state('idle')

    # --- DEĞİŞTİRİLDİ: Diğer fonksiyonlar, durum idle'a döndüğünde fare takibini bozmasın ---
    # Örneğin, konuşma bitince direkt 'idle' durumuna dönmeli.
    def hide_speech_bubble(self):
        self.speech_bubble.hide()
        self.adjustSize()
        self.set_state('idle') # <-- Burası önemli, direkt 'idle' a dönüyor

    # Yürüme bittiğinde de direkt 'idle' a dönmeli
    def move_towards_target(self):
        if not self.is_moving: return
        current_pos = self.pos(); direction_x = self.target_pos.x() - current_pos.x()
        if abs(direction_x) < 5:
            self.is_moving = False
            self.set_state('idle') # <-- Burası da önemli
            return
        step = 5 if direction_x > 0 else -5
        self.move(current_pos.x() + step, current_pos.y())


    # ... (Geri kalan tüm fonksiyonlar tamamen aynı, değişiklik yok) ...
    def load_or_create_config(self):
        config = configparser.ConfigParser()
        if not os.path.exists(self.config_path):
            print(f"'{self.config_path}' bulunamadı, varsayılan ayarlar oluşturuluyor.")
            config['Gemini'] = {'api_key': 'YOUR_GEMINI_API_KEY_HERE'}
            config['Assistant'] = {'wake_word': 'rem', 'text_input_speak_response': 'true'}
            with open(self.config_path, 'w') as configfile: config.write(configfile)
        config.read(self.config_path); return config
    def open_settings_dialog(self):
        dialog = SettingsDialog(self.config_path, self); dialog.exec_()
        self.config = self.load_or_create_config()
        self.wake_word = self.config.get('Assistant', 'wake_word', fallback='rem').lower()
        self.text_input_speak_response = self.config.getboolean('Assistant', 'text_input_speak_response', fallback=True)
        print("Ayarlar güncellendi. API anahtarı değişikliği için yeniden başlatma gerekebilir.")
    def show_speech_bubble(self, text, force_speak=False):
        self.speech_bubble.setText(text); self.speech_bubble.show(); self.speech_bubble.adjustSize(); self.adjustSize()
        if (self.last_input_was_voice or self.text_input_speak_response or force_speak):
            prepared_text = self.prepare_text_for_tts(text)
            threading.Thread(target=self.speak, args=(prepared_text,), daemon=True).start()
        QTimer.singleShot(10000, self.hide_speech_bubble)
    def contextMenuEvent(self, event):
        if QApplication.keyboardModifiers() == Qt.ControlModifier:
            self.last_input_was_voice = False; text, ok = QInputDialog.getText(self, 'Rem\'e Metinle Sor', 'Bana ne sormak istersiniz, efendim?')
            if ok and text: self.process_user_input(text)
            return
        menu = QMenu(self); toggle_listen_action = QAction('Dinlemeyi Başlat' if not self.is_listening else 'Dinlemeyi Durdur', self); toggle_listen_action.triggered.connect(self.toggle_listening); menu.addAction(toggle_listen_action)
        settings_action = QAction('Ayarlar', self); settings_action.triggered.connect(self.open_settings_dialog); menu.addAction(settings_action)
        menu.addSeparator(); quit_action = QAction('Çıkış', self); quit_action.triggered.connect(self.close); menu.addAction(quit_action)
        menu.exec_(self.mapToGlobal(event.pos()))
    def listen_for_command(self):
        with sr.Microphone() as source:
            self.set_state('thinking')
            try:
                self.last_input_was_voice = True; audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5); command = self.recognizer.recognize_google(audio, language="tr-TR")
                print(f"Komut algılandı: {command}"); self.process_user_input(command)
            except (sr.UnknownValueError, sr.WaitTimeoutError): self.show_speech_bubble("Üzgünüm efendim, anlayamadım.", force_speak=True); self.set_state('idle')
            except Exception as e: self.show_speech_bubble(f"Bir hata oluştu: {e}", force_speak=True); self.set_state('idle')
    def toggle_listening(self):
        self.is_listening = not self.is_listening
        if self.is_listening: self.show_speech_bubble("Dinlemeye başlıyorum...", force_speak=True); self.start_listening_thread()
        else: self.show_speech_bubble("Dinleme durduruldu.", force_speak=True); print("Dinleme durduruldu.")
    def prepare_text_for_tts(self, text): text = text.replace(',', ', ... '); text = text.replace('.', '. ... '); return text
    def speak(self, text):
        if not text or not pygame.mixer.get_init(): return
        try:
            print(f"gTTS ile konuşma üretiliyor..."); tts = gTTS(text=text, lang='tr'); audio_stream = io.BytesIO()
            tts.write_to_fp(audio_stream); audio_stream.seek(0)
            pygame.mixer.music.load(audio_stream, 'mp3'); pygame.mixer.music.play()
        except Exception as e: print(f"gTTS ile seslendirme sırasında hata: {e}")
    def process_user_input(self, user_prompt):
        if not self.model: self.show_speech_bubble("API anahtarınız 'config.ini' dosyasında ayarlanmamış. Lütfen sağ tıklayıp Ayarlar menüsünden girin.", force_speak=True); return
        system_prompt = f"""
            Sen, Re:Zero animesindeki Rem karakterisin. Cevapların nazik, hizmet odaklı ve biraz resmi olmalı.
            Cevaplarını kısa ve net tut. Konuşmanın daha doğal akması için cümlelerinde virgül kullanarak kısa duraksamalar yap.
            Ayrıca bir AI asistanısın ve kullanıcının bilgisayarında Python kodu çalıştırabilirsin. İŞ AKIŞI:
            1. Kullanıcının isteği normal bir sohbet mi ('nasılsın?', 'bana bir şaka anlat')? Eğer öyleyse, karakterine uygun normal bir metinle cevap ver.
            2. Kullanıcının isteği bir eylem mi gerektiriyor ('google'ı aç', 'dosyaları listele')? Eğer öyleyse, SADECE ve SADECE aşağıdaki JSON formatında bir cevap üret:
                {{"eylem": "execute_python", "kod": "buraya_çalıştırılacak_python_kodu_gelecek"}}
            PYTHON KODU İÇİN KURALLAR:
            - Windows'ta bir klasörü veya programı `start` komutuyla açarken, MUTLAKA şu formatı kullan: `start "" "açılacak_yol"`.
            - Çıktı üretmesi gereken kodlar için `print()` kullan. ÖRNEKLER:
            Kullanıcı: 'şu anki klasördeki dosyalar neler?' -> Cevap: {{"eylem": "execute_python", "kod": "import os; print(os.listdir('.'))"}}
            Kullanıcı: 'masaüstündeki notlar klasörünü aç' -> Cevap: {{"eylem": "execute_python", "kod": "import os; path = os.path.join(os.path.expanduser('~'), 'Desktop', 'notlar'); os.system(f'start \\"\\" \\"{{path}}\\"')"}}
            Kullanıcı: 'nasılsın rem?' -> Cevap: Size hizmet edebildiğim için çok mutluyum, efendim.
            Şimdi kullanıcının isteğini işle. Kullanıcı İsteği: '{user_prompt}'
        """
        try:
            self.set_state('thinking'); QApplication.processEvents()
            response = self.model.generate_content(system_prompt)
            response_text = response.text.strip()
            if response_text.startswith("```json"): response_text = response_text[7:-3].strip()
            data = json.loads(response_text)
            if data.get("eylem") == "execute_python": self.show_speech_bubble(self.execute_python_code(data.get("kod")))
            else: self.show_speech_bubble("Anlayamadığım bir eylem formatı döndü.")
        except (json.JSONDecodeError, AttributeError): self.show_speech_bubble(response_text); self.set_state('talking')
        except Exception as e: self.set_state('idle'); self.show_speech_bubble(f"Çok üzgünüm efendim, bir sorunla karşılaştım: {e}", force_speak=True)
    def execute_python_code(self, code_string):
        reply = QMessageBox.question(self, 'Onay', f"Efendim, aşağıdaki kodu çalıştırmak istediğimden emin misiniz?\n\n---\n{code_string}\n---", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                result = subprocess.run(['python', '-c', code_string], capture_output=True, text=True, check=True, timeout=15)
                output = result.stdout or "Komutu başarıyla çalıştırdım efendim. Herhangi bir çıktı üretmedi."
                return f"İşte komutun çıktısı:\n{output}"
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
                    if self.wake_word in text: print("Uyandırma kelimesi algılandı!"); self.show_speech_bubble("Evet efendim, sizi dinliyorum.", force_speak=True); self.listen_for_command()
                except sr.UnknownValueError: pass
                except sr.RequestError as e: print(f"Ses tanıma servisi hatası; {e}"); self.is_listening = False
    def closeEvent(self, event): pygame.quit(); event.accept()
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton: self.drag_position = event.globalPos() - self.frameGeometry().topLeft(); event.accept()
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton: self.move(event.globalPos() - self.drag_position); event.accept()
    def set_character_image(self):
        pixmap_list = self.animations.get(self.current_state)
        if pixmap_list: pixmap = pixmap_list[self.animation_frame % len(pixmap_list)]; self.character_label.setPixmap(pixmap); self.character_label.adjustSize(); self.adjustSize()
    def decide_new_action(self):
        if self.is_moving or self.speech_bubble.isVisible(): return
        if random.random() < 0.7: self.start_moving()
        else: self.set_state('idle')
    def start_moving(self):
        screen_width = QApplication.desktop().screenGeometry().width(); target_x = random.randint(0, screen_width - self.width()); self.target_pos = QPoint(target_x, self.y())
        self.set_state('walk_right' if self.target_pos.x() > self.x() else 'walk_left'); self.is_moving = True
    def set_state(self, state):
        if self.current_state != state: # Sadece durum değişirse frame'i sıfırla
            self.current_state = state; self.animation_frame = 0

if __name__ == '__main__':
    app = QApplication(sys.argv)
    assistant = DesktopAssistant()
    sys.exit(app.exec_())