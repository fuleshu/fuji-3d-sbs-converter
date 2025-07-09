# Fuji 3D SBS Video Converter

This is a simple offline tool for Windows, Mac, or Linux that converts rare **Fuji 3D AVI video files** into standard **Side-By-Side (SBS) MP4 videos** with audio. It supports both single video conversion and batch processing of entire folders.

The converter extracts both left and right eye streams, merges them into SBS images, preserves the original audio, and outputs a clean MP4 file that works in modern 3D players, VR headsets, or YouTube.

---

## 🚀 Features

* Converts Fuji 3D `.avi` video files to SBS `.mp4` videos.
* Preserves original audio and exact video frame rate.
* Fully offline—no data leaves your machine.
* Easy-to-use web browser interface.
* Supports **single video conversion** and **batch folder processing**.

---

## 📦 Installation

1. Install **Miniconda** or **Anaconda** from:
   [https://docs.conda.io/en/latest/miniconda.html](https://docs.conda.io/en/latest/miniconda.html)

2. Create a new environment:

```bash
conda create -n fuji3d python=3.10
conda activate fuji3d
```

3. Install required Python packages:

```bash
pip install gradio
```

4. Download and install **ffmpeg** and **ffprobe**:

* [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)

Make sure either:

* The ffmpeg/ffprobe executables are in your **system PATH**, or
* You copy them into the **same folder as `main.py`**.

---

## ▶️ How to Run

1. Make sure your **conda environment is activated**:

```bash
conda activate fuji3d
```

2. Launch the app:

```bash
python main.py
```

3. A browser window will open automatically (or visit the link printed in the console).

---

## 🌐 How to Use the Web UI

* **Input Path:** Enter either:

  * A single `.avi` file (e.g., `D:/Videos/MyVideo.avi`)
  * Or a folder containing multiple `.avi` files for **batch conversion**.

* **Output Folder:** Enter the path to the folder where you want the converted `.mp4` files to be saved.

* Click **Submit**.

* The tool will:

  * Extract left and right eye video streams.
  * Merge them into SBS frames.
  * Preserve audio.
  * Generate `.mp4` files with the original frame rate and stereo layout.

---

## ✅ Output Example

For `MyVideo.avi`, the tool will generate:

```
MyVideo_SBS.mp4
```

---

## 📝 Notes

* All work is done **locally**—no internet or cloud processing involved.
* This tool is provided **as-is** with no warranty. Use at your own risk.

---

## 📄 License

MIT License. See `LICENSE` file for details.
