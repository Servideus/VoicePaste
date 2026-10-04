[Инструкция на русском языке здесь](README.ru.md).

# VoicePaste

Windows push-to-talk dictation with Gemini transcription and automatic paste. Hold a shortcut, speak and release it. VoicePaste records microphone audio, sends a WAV file to Gemini and inserts the processed text into the active window. The application interface is in Russian.

## Status and download

Windows beta 1.1.5. [Download v1.1.5-beta](https://github.com/Servideus/VoicePaste/releases/tag/v1.1.5-beta). The archive includes the executable and dependency license texts.

Requires Windows 10/11 x64. Python is not required for the packaged executable. Run `release/1.1.5/VoicePaste.exe`; the app appears in the system tray without a main window. The executable is not Authenticode-signed. Do not disable Windows protection to run it.

## Quick start

1. Open the tray menu and select Settings. Enter your own Gemini API key and save it.
2. Choose a model. The Check button makes an API request to check availability; success does not guarantee transcription quota.
3. Open Notepad, hold Ctrl+Shift and speak for two or three seconds. Release the keys and wait for the text.

Internet access and an available Gemini API are required. Audio is sent to Google; requests may consume API quota. The app edits Russian speech into written text, correcting punctuation and removing repetitions and fillers. Transcribe verbatim preserves spoken repetitions and fillers.

## Settings and data

- Default shortcut: Ctrl+Shift. You can choose a letter or function-key combination. If Ctrl+Shift switches your Windows keyboard layout, choose another shortcut.
- New installations select `gemini-3.5-flash-lite`. The menu contains four models with measured median latency below five seconds, ordered from fastest to slowest. Transcribe uses verbatim mode. A saved model removed from the menu is replaced with Flash Lite 3.5. See [model settings and measurements](docs/models.md).
- Errors and empty responses trigger the next model, wrapping to the beginning of the list. Each model gets one attempt per recording. The first successful result is used; the selected setting is retained. If all fail, the app reports an error.
- Configuration: `%APPDATA%/VoicePaste/config.json`. The API key is stored separately through keyring in Windows Credential Manager.
- Log: `%LOCALAPPDATA%/VoicePaste/logs/voicepaste.log`. WAV files and transcript text are not saved in the log; timing, recording sizes and errors are recorded. Review logs before sharing them.
- Left-click the tray icon to toggle pause; right-click for the menu. Exit unregisters the shortcut.

Model availability may change. See Google's [model documentation](https://ai.google.dev/gemini-api/docs/models) and [deprecations](https://ai.google.dev/gemini-api/docs/deprecations).

## Run from source

Verified with Python 3.12 x64. From the repository root:

```powershell
py -3.12 -m venv voicepaste/.venv
./voicepaste/.venv/Scripts/python.exe -m pip install -r requirements-lock.txt
./run.ps1
```

`requirements-lock.txt` records the tested environment, including test/build tools. For runtime-only dependencies, use `voicepaste/requirements.txt`.

## Tests and build

```powershell
./voicepaste/.venv/Scripts/python.exe -m pytest voicepaste/tests -q
./build.ps1 -DistPath release/1.1.5
```

`build.ps1` runs tests, collects dependency license texts, builds the executable and prints SHA-256. `VoicePaste.spec` is canonical; `voicepaste/build.spec` redirects to it. The build script is independent of the invoking working directory. Set `$env:VOICEPASTE_DEBUG_CONSOLE='1'` before building to include a diagnostic console; normal builds have none.

The old `dist/VoicePaste.exe` is retained as a recovery option and is not updated. Use `release/1.1.5/VoicePaste.exe` for this version.

## Beta limitations

The [benchmark of all fifteen model choices](benchmark/2026-10-04/report.md) documents speed and quality. After testing the user's recording, the menu retained Transcribe verbatim, Flash Lite 3.5, Flash 3.6 and Flash Lite Latest. Saved selections remain if the model is still available in the menu.

Insertion uses the text clipboard and Ctrl+V, then restores the previous clipboard text. Unicode SendInput is the fallback. The app cannot guarantee that a third-party window accepted the text; Windows may block insertion into elevated or protected windows. Start with ordinary Notepad.

API checks and mocked tests do not replace manual voice and insertion checks in the target application. The [verification report](docs/verification.md) separates automated checks from the remaining user scenario.

## License

VoicePaste code: [MIT](LICENSE). Qt/PySide6 and other dependencies retain their respective licenses. Texts and versions are in `third_party_licenses`; Qt details are in [THIRD_PARTY.md](THIRD_PARTY.md). Personal keys, databases and settings must not be included in distributed archives.
