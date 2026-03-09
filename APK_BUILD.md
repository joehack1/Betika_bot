# Build Android APK (Betika Mobile Remote)

## What this setup does
- `betika.py` still runs on your PC (where Selenium/Chrome works).
- Android app (`android_app/main.py`) controls that PC bot over HTTP.
- This is the reliable way to get a working `.apk` with your current bot architecture.

## 1. Start the bot service on your PC
From the project root:

```powershell
python betika_service.py --host 0.0.0.0 --port 8787
```

Keep this terminal open while using the mobile app.

## 2. Build APK (use Linux or WSL)
Buildozer does not build reliably on native Windows. Use Ubuntu/WSL.

Install dependencies:

```bash
sudo apt update
sudo apt install -y \
  git zip unzip openjdk-17-jdk \
  python3-pip python3-venv \
  autoconf automake libtool pkg-config \
  zlib1g-dev libncurses5-dev libncursesw5-dev \
  libtinfo6 cmake libffi-dev libssl-dev
python3 -m pip install --user --upgrade pip
python3 -m pip install --user buildozer "Cython<3"
```

Build:

```bash
cd android_app
buildozer android debug
```

APK output:
- `android_app/bin/*.apk`

## 3. Connect the app to your PC
- Make sure phone and PC are on the same Wi-Fi.
- Find PC IP:
  - Windows: `ipconfig`
- In the Android app, set **Server URL** to:
  - `http://<PC_IP>:8787`
  - Example: `http://192.168.1.10:8787`

## 4. Install APK on phone
- Copy the APK from `android_app/bin/` to your phone.
- Enable installing from unknown sources, then install.

## Notes
- If phone cannot connect, allow inbound TCP `8787` in Windows Firewall.
- The APK is a remote controller. The actual Selenium bot continues running on PC.
