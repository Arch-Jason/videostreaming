# 📡 VideoStreaming

**VideoStreaming** is a lightweight Android + Python project that streams real-time video (from desktop screen or webcam) to an Android device over UDP.

It contains:

- 📱 A native Android app (Kotlin) to receive and display image frames.

- 🖥️ Two Python scripts:
  
  - `screen_streaming.py`: captures and streams your Wayland desktop screen.
  
  - `camera_streaming.py`: streams webcam footage from your PC.

---

## ✨ Features

- UDP-based video transmission for simplicity and low-latency.

- Frame slicing + CRC32 verification to ensure integrity.

- Android-side real-time decoding and display via `ImageView`.

- Supports both screen casting and camera streaming with minimal setup.

---

## 🖥️ Python Side

### 1. `screen_streaming.py`

**Function:** Captures a Wayland screen (using xdg-desktop-portal + PipeWire) and streams it as JPEG frames via UDP.

#### 📦 Requirements

- Python ≥ 3.7

- Required Python packages:
  
  ```bash
  pip install opencv-python dbus-python PyGObject numpy
  ```

- GStreamer with PipeWire support (`gstreamer1.0-plugins-good`, `libpipewire`, etc.)

- Wayland + `xdg-desktop-portal`

#### 🔧 How it works

- Uses D-Bus to request a screen sharing session.

- PipeWire stream is read via GStreamer → converted to raw frame → encoded to JPEG.

- Each frame is sent over UDP:
  
  - Header: 12 bytes = `[indicator:int][length:int][crc32:int]`
  
  - Frame is split into 32KB chunks.
  
  - Receiver reassembles and validates via CRC.

#### ▶️ Run

```bash
python screen_streaming.py
```

> Make sure to allow screen sharing when prompted.

---

### 2. `camera_streaming.py`

**Function:** Captures webcam frames and streams them to Android.

#### 📦 Requirements

- OpenCV (Python bindings): `opencv-python`

#### ▶️ Run

```bash
python camera_streaming.py
```

> Modify `UDP_IP` inside the script to match your Android device's local IP address.

---

## 📱 Android App

### 🔍 Location

Found under:  
`app/src/main/java/com/example/videostreaming/MainActivity.kt`

### 🧠 How it works

- Listens on UDP port `5600`.

- Expects a custom protocol:
  
  - 12-byte header (`int32 indicator = -114514`, `int32 length`, `int32 crc32 // 100`)
  
  - Follows up with one or more chunks of image data (max 32KB per chunk)

- Reassembles, verifies, and decodes the image using `BitmapFactory`.

- Displays the image in an `ImageView` on the UI thread.

### ✅ Features

- CRC32 validation of frame integrity.

- Automatic chunk reassembly.

- Memory management via `Bitmap.recycle()`.

> The app listens automatically on startup; no config required.

---

## 📡 Protocol Overview

| Part   | Size (bytes) | Description                           |
| ------ | ------------ | ------------------------------------- |
| Header | 12           | `indicator`, `length`, `crc32 // 100` |
| Data   | Variable     | JPEG image split in 32KB chunks       |

- `indicator` must be `-114514` for a valid frame.

- `crc32` is computed over the full image data and divided by 100 (int).

- Frame is discarded if CRC check fails.

---

## 🛠 Configuration

To adapt for your environment:

- Set the correct IP address in:
  
  - `UDP_IP` field of `screen_streaming.py` or `camera_streaming.py`.

- Android app listens on port `5600` by default. Make sure this matches.

---

## 🔒 Known Limitations

- No NAT traversal / remote access — only works on local network.

- No audio streaming support.

- JPEG encoding may introduce latency; consider H.264 in the future.

## 📄 License

This project is open source under the MIT License.  
Feel free to fork and improve.
