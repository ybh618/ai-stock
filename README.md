# Stock AI MVP

This repository contains:

- `backend/`: FastAPI service for watchlist sync, recommendation generation, and WebSocket push.
- `android/`: Native Kotlin Android app (Compose) with watchlist, settings, recommendation history, and online push.

## Quick Start

- Backend run:
  - `cd backend`
  - `python -m venv .venv`
  - `. .venv/bin/activate` (Linux/macOS) or `.venv\\Scripts\\activate` (Windows)
  - `pip install -e .[dev]`
  - `cp .env.example .env`
  - `chmod +x run_server.sh && ./run_server.sh` (Linux, 无需手动进入虚拟环境)
  - Debug mode: `chmod +x debug.sh && ./debug.sh`

- Project update (Linux):
  - `chmod +x update.sh && ./update.sh`

- Android build:
  - Open `android/` in Android Studio.
  - Use Android Studio embedded JDK (`.../Android Studio/jbr`) for Gradle sync/build.
  - Ensure Android SDK path is valid (`ANDROID_HOME`), typically `C:\Users\Administrator\AppData\Local\Android\Sdk` on Windows.
  - Command line build example:
    - `cd android`
    - `gradlew.bat :app:assembleDebug`

## Notes

- The backend is intentionally auth-free for MVP and uses `client_id` as anonymous identity.
- LLM calls are not quota-limited in business logic; concurrency is controlled at 20.
- The provided GraalVM JDK path `C:\Users\Administrator\Documents\code\graalvm-jdk-25.0.2+10.1` is kept for your environment reference, but current AGP/Android build validation was executed with Android Studio JBR.
