# YouTube Video Summarizer & Q-A Tool 🚀

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

A cross-platform command-line tool that turns any public YouTube video into:

1.  An executive bullet-point **summary**.
2.  A rich **detailed description** with optional, interactive Gemini-powered Q-and-A.

The workflow is completely local—only the Google Gemini API is contacted for language-generation tasks. Captions are preferred; if none exist the tool falls back to automatic speech-to-text with Whisper.

---

## 📋 Table of Contents

- [🌟 Features](#-features)
- [🎬 Demo](#-demo)
- [🚀 Quick Start](#-quick-start)
- [💡 Usage](#-usage)
- [🔧 Configuration](#-configuration)
- [🧩 How It Works](#-how-it-works)
- [🛠️ Troubleshooting](#️-troubleshooting)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)

---

## 🌟 Features

-   **One-liner usage**: `yt <youtube-link>`
-   **Dual Modes**: Choose between a quick summary or a deep dive with interactive chat.
-   **Smart Transcript Handling**: Uses existing captions or falls back to local speech-to-text via Whisper.
-   **Robust Validation**: Checks for valid YouTube links and video availability.
-   **Modular & Clean Code**: Easy to understand and extend.

---

## 🎬 Demo

<img width="1920" height="601" alt="Screenshot from 2025-07-20 11-54-36" src="https://github.com/user-attachments/assets/dc02b16f-ef69-4e84-ae13-247b5a29b15f" />

---

## 🚀 Quick Start

```bash
# 1. Clone this repository
$ git clone https://github.com/your-username/your-repo-name.git
$ cd your-repo-name

# 2. Create and activate a virtual environment (recommended)
$ python3 -m venv venv
$ source venv/bin/activate

# 3. Install dependencies
$ pip install -r requirements.txt

# 4. Set your Gemini API key
$ export GEMINI_API_KEY='YOUR_API_KEY_HERE'
# Or add it to a .env file in the root directory.

# 5. Make the installer executable and run it
$ chmod +x sync_yt.sh
$ ./sync_yt.sh
```

<details>
  <summary><strong>Optional: Install FFmpeg for Audio Fallback</strong></summary>

  FFmpeg is only needed if a video has no captions and the tool must transcribe the audio locally.

  - **On Debian/Ubuntu:**
    ```bash
    sudo apt update && sudo apt install ffmpeg
    ```
  - **On macOS (using Homebrew):**
    ```bash
    brew install ffmpeg
    ```
  - **On Windows (using Chocolatey):**
    ```bash
    choco install ffmpeg
    ```

</details>

---

## 💡 Usage

Once installed, you can run the tool from anywhere:

```bash
# Get a summary for a video
$ yt https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

After running the command, you will see a menu:

1.  **Get a concise summary.**
2.  **Get a detailed description and start an interactive Q&A session.**

During a chat session, type `exit` or `quit` to end.

---

## 🔧 Configuration

Environment variables are used for API keys. They can be set in your shell or stored in a `.env` file in the project's root directory.

| Variable             | Purpose                                          | Required |
| -------------------- | ------------------------------------------------ | :------: |
| `GEMINI_API_KEY`     | Your Google Generative AI key.                   |   Yes    |
| `YOUTUBE_DATA_API_KEY` | Optional, but improves video validation.         |    No    |

---

## 🧩 How It Works

1.  **Input Handling**: The CLI validates the YouTube URL.
2.  **Transcript Retrieval**: It fetches captions using the YouTube Transcript API. If none are available, it downloads the audio and transcribes it locally using Whisper.
3.  **Content Generation**: The transcript is sent to the Gemini API to generate a summary or a detailed description.
4.  **Interactive Q&A**: For the Q&A mode, the chat context is seeded with the transcript, allowing Gemini to provide grounded answers to your questions.

---

## 🛠️ Troubleshooting

<details>
  <summary>Click to view common issues and solutions</summary>

  - **Error: `GEMINI_API_KEY environment variable is missing.`**
    - **Solution**: Ensure your API key is either exported in your shell (`export GEMINI_API_KEY=...`) or present in a `.env` file in the project directory.

  - **Error: `ffmpeg not found`**
    - **Solution**: This means a video without captions was processed. Install FFmpeg using your system's package manager (see the Quick Start section).

  - **400 errors from Gemini API**
    - **Solution**: This may indicate that your prompts are too long for the model or there's an issue with your API quota. Try a shorter video or check your Google AI Platform dashboard.

</details>

---

## 🤝 Contributing

Contributions are welcome! If you have suggestions or want to improve the tool, please feel free to open an issue or submit a pull request.

1.  Fork the repository.
2.  Create your feature branch (`git checkout -b feature/AmazingFeature`).
3.  Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4.  Push to the branch (`git push origin feature/AmazingFeature`).
5.  Open a Pull Request.

---

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
