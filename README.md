# Rem - AI Desktop Companion

[![Latest Release](https://img.shields.io/github/v/release/JuuzouTem/Rem?style=for-the-badge&label=Latest%20Release)](https://github.com/JuuzouTem/Rem/releases/latest?cacheSeconds=1)
[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue?style=for-the-badge)](https://www.python.org/)

An interactive, AI-powered desktop assistant in the style of Rem from *Re:Zero*. This character lives on your desktop, visually analyzing your screen to interact with icons and windows, responding to your voice commands, and performing a wide range of tasks. She'll stay on your desktop, ready to assist with tasks, answer questions, or just keep you company.

---

## ✨ Features

*   **🧠 Selective Long-Term Memory**: Rem remembers important details about you (like your name, favorite color, or deadlines) and saves them to `memory.json`. She intelligently decides what to remember based on your relationship and the context, filtering out trivial chatter.
*   **👀 Dual-Core AI Vision**: Powered by **Gemini 2.5 Flash**, Rem has a dedicated "Vision Brain". She takes snapshots of your screen to identify icons, window corners, or the taskbar, and intelligently decides where to sit or walk—no more random wandering!
*   **🚀 Smart App Launcher**: Just say "Open [App Name]". Rem scans your Windows Start Menu shortcuts to find the correct application, even if you don't know the exact `.exe` name (e.g., finding "Honkai Impact" when the file is `launcher.exe`).
*   **🖱️ Interactive Physics**: Rem is not just a static image.
    *   **Drag & Drop**: Pick her up with your mouse! She will grab your cursor (`climb` animation).
    *   **Gravity**: Release her, and she will fall (`fall` animation) and land gracefully (`land` animation) on the taskbar or window.
    *   **Eye Contact**: When idle, she follows your mouse cursor with her eyes.
*   **🔍 Smart Web Search (RAG)**: Using the **Google Custom Search API**, Rem researches your questions. She reads the search results silently, filters out irrelevant data (like football scores when asking for history), and synthesizes a direct, intelligent answer for you.
*   **Voice Control**: Activate her by calling her wake word ("Rem" by default) and give commands in natural language.
*   **Core Assistant Tools**:
    *   🎵 **Spotify Control**: Play, pause, and skip tracks.
    *   🌦️ **Weather Information**: Get the current weather for any city with accurate status descriptions.
    *   💻 **Secure Code Execution**: Ask her to perform system tasks by generating Python scripts. She will always ask for your permission before running any code.
*   **Customizable**: Easily change the wake word, character animations, and configuration via a GUI menu.

---

## 🚀 Getting Started

There are two ways to get Rem running on your Windows machine.

### Method 1: Easy Installation (Recommended for Most Users)

This is the simplest way to get started. You just need to download the pre-built program.

1.  **Download the Latest Release**
    *   Go to the **[Releases Page](https://github.com/JuuzouTem/Rem/releases/latest)**.
    *   Under the "Assets" section, download the `RemAI_Assistant.exe` file.

2.  **Create the Configuration File**
    *   In the **same folder** where you saved `RemAI_Assistant.exe`, create a new text file and name it `config.ini`.
    *   Copy and paste the following template into your new `config.ini` file:
      ```ini
      [Gemini]
      api_key = YOUR_GEMINI_API_KEY_HERE

      [Assistant]
      wake_word = rem
      text_input_speak_response = true

      [Spotify]
      client_id = YOUR_CLIENT_ID_HERE
      client_secret = YOUR_CLIENT_SECRET_HERE
      redirect_uri = http://localhost:8888/callback

      [Google]
      api_key = YOUR_GOOGLE_CLOUD_API_KEY
      cse_id = YOUR_SEARCH_ENGINE_ID
      ```

3.  **Add Your API Keys**
    *   Follow the instructions in the **[Configuration (`config.ini`)](#-configuration-configini)** section below to get your API keys and add them to the file.

4.  **Run the Assistant**
    *   Double-click `RemAI_Assistant.exe`. Rem should now appear on your desktop!

### Method 2: Installation from Source (For Developers)

If you want to modify the code or run it directly with Python.

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/JuuzouTem/Rem.git
    ```

2.  **Navigate to the Project Directory**
    The project files are inside a sub-folder.
    ```bash
    cd Rem/Rem
    ```

3.  **Install Dependencies**
    It's highly recommended to use a virtual environment. Note: We now use the newer `google-genai` library.
    ```bash
    python -m venv venv
    venv\Scripts\activate
    pip install google-genai pygame gtts pyautogui Pillow SpeechRecognition spotipy requests PyQt5
    ```

4.  **Configure API Keys**
    *   In the `Rem/Rem` folder, create a `config.ini` file.
    *   Follow the instructions in the **[Configuration (`config.ini`)](#-configuration-configini)** section below to fill it with your keys.

5.  **Run the Assistant**
    ```bash
    python assistant.py
    ```

---

## 🔧 Configuration (`config.ini`)

To use the AI, Spotify, and Search features, you must get your own free API keys.

#### ♊ Gemini API Key (for AI Brain)

1.  Go to **[Google AI Studio](https://aistudio.google.com/app/apikey)**.
2.  Click the "**Create API key**" button.
3.  Copy the generated API key and paste it into the `api_key` field under `[Gemini]`.

#### 🔍 Google Search API (for Web Browsing)

1.  **API Key:** Go to **[Google Cloud Console](https://console.cloud.google.com/apis/credentials)**, create a project, and create an API Key. Paste it into `api_key` under `[Google]`.
2.  **Search Engine ID (CX):** Go to **[Programmable Search Engine](https://programmablesearchengine.google.com/controlpanel/create)**. Create a search engine that searches "The entire web". Copy the "Search engine ID" (CX) and paste it into `cse_id` under `[Google]`.

#### 🎵 Spotify API (for Music Control)

1.  Go to the **[Spotify Developer Dashboard](https://developer.spotify.com/dashboard)** and log in.
2.  Click "**Create app**", give it a name and description.
3.  Copy the **Client ID** and **Client Secret** into your `config.ini`.
4.  **Crucially**, click the "**Settings**" button for your app.
5.  In the "**Redirect URIs**" field, add **exactly** this URL: `http://localhost:8888/callback`. Click "Add", then "Save".

**First-Time Authorization**: The very first time you ask Rem to control Spotify, a browser window will open asking you to grant permission. Please accept it. This only needs to be done once.

---

## 🛠️ Customizing and Adding New Skills

The most powerful feature of this assistant is its ability to learn new tasks without changing the code. You can teach Rem new skills by editing the `special_commands.json` file.

This file acts as a "recipe book" for the AI. When you give a command that matches a recipe, the AI will generate and execute a Python script to complete the task.

**Example: Adding a "System Backup" Command**

1.  **Open `special_commands.json`** and add a new entry:

    ```json
    {
      "...": "...",
      "create_backup": "Creates a backup of the 'MyDocuments' folder by zipping it to the Desktop. Use python's 'shutil' library, specifically 'shutil.make_archive'. The backup should be named 'docs_backup'."
    }
    ```

2.  **Run the assistant and say**: "Rem, create a backup of my documents."

The AI will now understand this new recipe. It will generate the necessary `shutil` Python code to create the zip file and ask for your permission to run it.

## 🤝 Contributing

Contributions are welcome! If you have ideas for new features or improvements, feel free to open an issue or submit a pull request.
