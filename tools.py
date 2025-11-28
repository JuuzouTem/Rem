# tools.py (DEĞİŞİKLİK YOK, KONTROL İÇİN)

import requests
import requests
import configparser
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pygetwindow as gw
import os
import difflib # İsim benzerliği bulmak için

def search_and_summarize(query):
    print(f"Google'da aranıyor: {query}")
    
    # Ayarları oku
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    api_key = config.get('Google', 'api_key', fallback=None)
    cse_id = config.get('Google', 'cse_id', fallback=None)
    
    if not api_key or not cse_id:
        return "Hata: Google API anahtarları config.ini dosyasında eksik."

    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'q': query,
            'key': api_key,
            'cx': cse_id,
            'num': 3,        # İlk 3 sonuç yeterli
            'gl': 'tr',      # Bölge: Türkiye
            'hl': 'tr'       # Dil: Türkçe
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if 'items' not in data:
            return "Google'da bununla ilgili bir sonuç bulamadım."
            
        raw_data = ""
        for item in data['items']:
            title = item.get('title', '')
            snippet = item.get('snippet', '') # Google'ın özeti
            raw_data += f"KAYNAK: {title} - {snippet}\n"
            
        return raw_data

    except Exception as e:
        print(f"Google Arama hatası: {e}")
        return None

def get_weather(city):
    print(f"{city} için hava durumu alınıyor...")
    try:
        weather_url = f"https://wttr.in/{city}?format=j1&lang=tr"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(weather_url, headers=headers, timeout=10)
        response.raise_for_status() 
        
        weather_data = response.json()
        
        current_condition = weather_data.get('current_condition', [{}])[0]
        nearest_area = weather_data.get('nearest_area', [{}])[0]
        
        city_name = nearest_area.get('areaName', [{}])[0].get('value', city)
        country = nearest_area.get('country', [{}])[0].get('value', '')
        
        temp_c = current_condition.get('temp_C', 'N/A')
        feels_like_c = current_condition.get('FeelsLikeC', 'N/A')
        wind_kmph = current_condition.get('windspeedKmph', 'N/A')
        description_tr = current_condition.get('lang_tr', [{}])[0].get('value', 'Açıklama mevcut değil')

        return (f"{city_name}, {country} için hava durumu: "
                f"Sıcaklık {temp_c}°C, hissedilen sıcaklık {feels_like_c}°C. "
                f"Hava '{description_tr}' ve rüzgar hızı saatte {wind_kmph} kilometre.")

    except requests.exceptions.HTTPError:
        return f"Üzgünüm, '{city}' için hava durumu bilgisi bulunamadı. Lütfen şehir adını kontrol edin."
    except Exception as e:
        print(f"wttr.in'den veri alınırken hata oluştu: {e}")
        return f"Hava durumu bilgisi alınırken bir sorun oluştu: {e}"

def control_spotify(command, config):
    try:
        client_id = config.get('Spotify', 'client_id', fallback=None)
        client_secret = config.get('Spotify', 'client_secret', fallback=None)
        redirect_uri = config.get('Spotify', 'redirect_uri', fallback=None)
        if not all([client_id, client_secret, redirect_uri]) or 'YOUR_CLIENT_ID_HERE' in client_id:
            return "Spotify ayarları 'config.ini' dosyasında eksik. Lütfen Ayarlar'dan kontrol edin."

        auth_manager = SpotifyOAuth(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri,
                                    scope="user-modify-playback-state user-read-playback-state", open_browser=False)
        sp = spotipy.Spotify(auth_manager=auth_manager)
        devices = sp.devices()
        if not devices or not devices['devices']:
            return "Spotify'da aktif bir cihaz bulunamadı. Lütfen Spotify'ı bir cihazda açın."
            
        command = command.lower()
        if "çal" in command or "oynat" in command: sp.start_playback(); return "Spotify'da müzik çalmaya devam ediyor."
        elif "dur" in command or "duraklat" in command: sp.pause_playback(); return "Müzik duraklatıldı."
        elif "sonraki" in command or "geç" in command: sp.next_track(); return "Sonraki şarkıya geçildi."
        elif "önceki" in command: sp.previous_track(); return "Önceki şarkıya geçildi."
        else: return f"Anlayamadığım bir Spotify komutu: {command}"
    except spotipy.oauth2.SpotifyOauthError:
        return "Spotify yetkilendirmesi gerekli. Ayarlar'dan tekrar kaydedip tarayıcıdaki adımları izleyin."
    except Exception as e: return f"Spotify kontrol edilirken hata oluştu: {e}"

def get_screen_layout():
    # Bu fonksiyon artık hareket sistemi tarafından kullanılmıyor,
    # ancak gelecekte başka bir amaçla gerekebilir diye burada kalabilir.
    windows_info = []
    try:
        all_windows = gw.getAllWindows()
        for window in all_windows:
            is_window_visible = False
            try:
                if window.visible: is_window_visible = True
            except AttributeError:
                try:
                    if window.isVisible: is_window_visible = True
                except AttributeError: pass
            if is_window_visible and window.title and window.width > 100 and window.height > 100:
                windows_info.append(f"- Pencere: '{window.title[:30]}', Konum: ({window.left}, {window.top}), Boyut: {window.width}x{window.height}")
        
        if not windows_info:
            return "Ekranda kayda değer bir pencere bulunmuyor."
        return "\n".join(windows_info)
        
    except Exception as e:
        print(f"Pencereler alınırken hata oluştu: {e}")
        return "Ekran düzeni bilgisi alınamadı."

def open_application(app_name):
    print(f"Uygulama aranıyor: {app_name}")
    
    # Windows Başlat Menüsü Yolları (Genel ve Kullanıcıya Özel)
    start_menu_paths = [
        os.path.join(os.environ["ProgramData"], "Microsoft", "Windows", "Start Menu", "Programs"),
        os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs")
    ]
    
    found_shortcuts = {}
    
    # Tüm kısayolları topla
    for path in start_menu_paths:
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith(".lnk"):
                    # Kısayol adını temizle (uzantıyı at, küçült)
                    shortcut_name = file.lower().replace(".lnk", "")
                    full_path = os.path.join(root, file)
                    found_shortcuts[shortcut_name] = full_path

    # 1. Tam Eşleşme Arama
    search_query = app_name.lower()
    if search_query in found_shortcuts:
        try:
            os.startfile(found_shortcuts[search_query])
            return f"Tam isabet! {app_name} başlatılıyor."
        except Exception as e:
            return f"Uygulama bulundu ama açılamadı: {e}"

    # 2. İçerik Eşleşmesi (Örn: "honkai" yazınca "honkai impact 3rd" bulsun)
    matches = [name for name in found_shortcuts.keys() if search_query in name]
    
    if matches:
        # En kısa ismi seç (Genelde en doğrusudur) veya ilkini al
        best_match = matches[0] 
        try:
            os.startfile(found_shortcuts[best_match])
            return f"Bunu mu kastettiniz: '{best_match}'? Başlatıyorum."
        except Exception as e:
            return f"Hata: {e}"
            
    return f"Üzgünüm, '{app_name}' adında veya buna benzer bir uygulama Başlat menüsünde bulunamadı."