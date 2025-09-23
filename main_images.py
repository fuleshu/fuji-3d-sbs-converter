# fast_mpo_to_sbs_unreal.py
# pip install pillow gradio turbojpeg (turbojpeg optional but fast)
from pathlib import Path
from io import BytesIO
from typing import List, Tuple, Optional
import mmap
import os
import gradio as gr
from PIL import Image, ImageOps

# Try turbojpeg (fast path)
try:
    from turbojpeg import TurboJPEG  # type: ignore
    _TJ = TurboJPEG()
except Exception:
    _TJ = None

# ---- EXACT Unreal-style marker scan ----
def parse_mpo_for_second_image(buf: memoryview) -> Tuple[int, int]:
    pattern1 = (0xFF, 0xD8, 0xFF, 0xE1)
    pattern2 = (0xFF, 0xD8, 0xFF, 0xE0)
    offsets: List[int] = []
    n = len(buf)
    i = 0
    while i <= n - 4:
        b0, b1, b2, b3 = buf[i], buf[i + 1], buf[i + 2], buf[i + 3]
        if (b0, b1, b2, b3) == pattern1 or (b0, b1, b2, b3) == pattern2:
            offsets.append(i)
            i += 3
        i += 1
    if len(offsets) < 2:
        raise ValueError("Could not find enough JPEG markers in the MPO file.")
    start = offsets[1]
    length = (offsets[2] - offsets[1]) if len(offsets) >= 3 else (n - offsets[1])
    return start, length

# ---- Decoding (fast with TurboJPEG, else Pillow) ----
from PIL import Image
import numpy as np

def _decode_jpeg_slice(buf: memoryview) -> Image.Image:
    if _TJ is not None:
        # Default output is BGR in many builds → swap to RGB
        arr = _TJ.decode(buf)           # shape: (H, W, 3) in BGR
        if arr.ndim == 3 and arr.shape[2] == 3:
            arr = arr[..., ::-1]        # BGR -> RGB
            return Image.fromarray(arr, mode="RGB")
        elif arr.ndim == 3 and arr.shape[2] == 4:
            # If you ever get BGRA, convert to RGBA then to RGB
            arr = arr[..., [2,1,0,3]]   # BGRA -> RGBA
            return Image.fromarray(arr, mode="RGBA").convert("RGB")
        else:
            # grayscale etc.
            return Image.fromarray(arr)
    # Fallback to Pillow
    with Image.open(BytesIO(buf)) as im:
        im.load()
        return im.convert("RGB")

def read_two_frames_unreal_way(mpo_path: Path, exif_autorotate: bool) -> Tuple[Image.Image, Image.Image]:
    with open(mpo_path, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        mv = memoryview(mm)
        try:
            # first image: decode whole buffer (TurboJPEG ignores trailing data after its EOI)
            left = _decode_jpeg_slice(mv)
            # second image: slice from 2nd marker to 3rd/EOF
            off, cnt = parse_mpo_for_second_image(mv)
            right = _decode_jpeg_slice(mv[off:off+cnt])
        finally:
            # memoryview must be released before closing mmap on Windows
            mv.release()
            mm.close()

    if exif_autorotate:
        left = ImageOps.exif_transpose(left)
        right = ImageOps.exif_transpose(right)
    return left, right

# ---- SBS maker ----
def make_sbs(left: Image.Image, right: Image.Image, target_height: int = 0) -> Image.Image:
    # Upscale/Downscale only if needed
    def scale_to_h(im: Image.Image, H: int) -> Image.Image:
        if H <= 0 or im.height == H:
            return im
        W = int(round(im.width * (H / im.height)))
        # TurboJPEG can scale natively only by 1/2, 1/4, 1/8; Pillow’s LANCZOS is fine here.
        return im.resize((W, H), Image.Resampling.LANCZOS)

    if target_height and target_height > 0:
        L = scale_to_h(left, target_height)
        R = scale_to_h(right, target_height)
        H = target_height
    else:
        H = max(left.height, right.height)
        L = scale_to_h(left, H)
        R = scale_to_h(right, H)

    out = Image.new("RGB", (L.width + R.width, H))
    out.paste(L, (0, 0))
    out.paste(R, (L.width, 0))
    return out

# ---- Gradio workflow with optional parallel batch ----
def mpo_to_sbs(input_path: str, output_folder: str, exif_autorotate: bool, recursive: bool, target_height: int, workers: int) -> str:
    inp = Path(input_path)
    outdir = Path(output_folder)
    outdir.mkdir(parents=True, exist_ok=True)

    def process_one(p: Path) -> str:
        try:
            left, right = read_two_frames_unreal_way(p, exif_autorotate)
            sbs = make_sbs(left, right, target_height)
            out = outdir / f"{p.stem}_sbs.jpg"
            sbs.save(out, "JPEG", quality=92, subsampling=0)
            left.close(); right.close()
            return f"OK: {p.name} → {out.name}"
        except Exception as e:
            return f"FAIL: {p.name} → {e}"

    tasks: List[Path] = []
    if inp.is_file():
        if inp.suffix.lower() not in [".mpo", ".jpg", ".jpeg"]:
            return f"Unsupported file: {inp.name}"
        tasks = [inp]
    elif inp.is_dir():
        it = inp.rglob("*") if recursive else inp.iterdir()
        tasks = [p for p in it if p.is_file() and p.suffix.lower() in [".mpo", ".jpg", ".jpeg"]]
        if not tasks:
            return "No MPO/JPG files found."
    else:
        return f"Input path not found: {inp}"

    logs: List[str] = []
    if len(tasks) == 1 or workers <= 1:
        for p in tasks:
            logs.append(process_one(p))
    else:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        # JPEG decode is in C (releases GIL) -> threads help
        w = max(1, min(workers, os.cpu_count() or 4))
        with ThreadPoolExecutor(max_workers=w) as ex:
            futs = {ex.submit(process_one, p): p for p in tasks}
            for f in as_completed(futs):
                logs.append(f.result())

    return "\n".join(logs)

def main():
    default_workers = max(1, (os.cpu_count() or 4) // 2)
    turbo = "ON" if _TJ is not None else "OFF"
    iface = gr.Interface(
        fn=mpo_to_sbs,
        inputs=[
            gr.Textbox(label="Input Path (MPO file or folder)"),
            gr.Textbox(label="Output Folder"),
            gr.Checkbox(label="Auto-apply EXIF Orientation", value=True),
            gr.Checkbox(label="Recursive (when input is a folder)", value=False),
            gr.Slider(label="Target Height (0 = keep largest)", minimum=0, maximum=4096, step=1, value=0),
            gr.Slider(label=f"Workers (TurboJPEG {turbo})", minimum=1, maximum=32, step=1, value=default_workers),
        ],
        outputs=gr.Textbox(label="Status / Logs", lines=12),
        title="MPO → SBS JPG (Unreal markers, fast)",
        description="Exact Unreal-style slicing. Uses TurboJPEG if available; else Pillow. Parallel for folders."
    )
    iface.launch()

if __name__ == "__main__":
    main()
