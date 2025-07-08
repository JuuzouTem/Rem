# tools.py (DEĞİŞİKLİK YOK, KONTROL İÇİN)

import requests
from bs4 import BeautifulSoup
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pygetwindow as gw

def search_and_summarize(query):
    print(f"Web'de aranıyor: {query}")
    try:
        search_url = f"https://html.duckduckgo.com/html/?q={query}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(search_url, headers=headers, timeout=5)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        snippets = [p.get_text() for p in soup.find_all('a', class_='result__a')]
        if not snippets:
            return "Üzgünüm efendim, bu konuda bir şey bulamadım."
        
        summary = " ".join(snippets[:3])
        return f"İnternette bulduklarıma göre: {summary}"
    except Exception as e:
        return f"İnternete bağlanırken bir sorun oluştu: {e}"

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