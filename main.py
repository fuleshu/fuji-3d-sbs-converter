import gradio as gr
from pathlib import Path
import struct
import subprocess
import shutil
from PIL import Image


def extract_and_create_sbs_with_audio(input_video_or_folder, output_folder):
    try:
        input_path = Path(input_video_or_folder)
        output_path = Path(output_folder)

        if not output_path.exists():
            output_path.mkdir(parents=True, exist_ok=True)

        avi_files = []
        if input_path.is_file() and input_path.suffix.lower() == ".avi":
            avi_files = [input_path]
        elif input_path.is_dir():
            avi_files = list(input_path.glob("*.avi"))

        if not avi_files:
            return "Error: No AVI files found."

        results = []

        for avi_file in avi_files:
            temp_folder = output_path / f"{avi_file.stem}_tmp"
            combined_folder = temp_folder / "sbs_frames"
            combined_folder.mkdir(parents=True, exist_ok=True)

            # Extract framerate using ffprobe
            probe_cmd = [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=r_frame_rate",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(avi_file)
            ]
            result = subprocess.run(probe_cmd, capture_output=True, text=True)
            framerate_raw = result.stdout.strip()
            if '/' in framerate_raw:
                num, denom = map(int, framerate_raw.split('/'))
                framerate = round(num / denom, 3) if denom != 0 else 30
            else:
                framerate = float(framerate_raw) if framerate_raw else 30

            # Extract audio
            audio_file = temp_folder / "audio.m4a"
            audio_cmd = [
                "ffmpeg", "-y", "-i", str(avi_file),
                "-vn", "-acodec", "aac", "-b:a", "192k", str(audio_file)
            ]
            subprocess.run(audio_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            left_count = 0
            right_count = 0

            # Extract frames
            with open(avi_file, 'rb') as f:
                riff_header = f.read(12)
                riff_id, riff_size, riff_format = struct.unpack('<4sI4s', riff_header)
                if riff_id != b'RIFF' or riff_format != b'AVI ':
                    results.append(f"Skipping {avi_file.name}: Not a valid AVI.")
                    continue

                while True:
                    pos = f.tell()
                    header = f.read(8)
                    if not header or len(header) < 8:
                        break

                    chunk_id_bytes, chunk_size = struct.unpack('<4sI', header)
                    chunk_id = chunk_id_bytes.decode('ascii', errors='ignore').strip()

                    if chunk_id == 'LIST':
                        list_type = f.read(4)
                        subtype = list_type.decode('ascii', errors='ignore').strip()

                        if subtype == 'movi':
                            movi_end = pos + 8 + chunk_size
                            while f.tell() < movi_end:
                                frame_header = f.read(8)
                                if not frame_header or len(frame_header) < 8:
                                    break

                                frame_id_bytes, frame_size = struct.unpack('<4sI', frame_header)
                                frame_id = frame_id_bytes.decode('ascii', errors='ignore').strip()

                                frame_data = f.read(frame_size)

                                if frame_id == '00dc':
                                    left_file = temp_folder / f"left_{left_count:04d}.jpg"
                                    with open(left_file, 'wb') as out_file:
                                        out_file.write(frame_data)
                                    left_count += 1

                                elif frame_id == '02dc':
                                    right_file = temp_folder / f"right_{right_count:04d}.jpg"
                                    with open(right_file, 'wb') as out_file:
                                        out_file.write(frame_data)
                                    right_count += 1

                                if frame_size % 2 == 1:
                                    f.seek(1, 1)
                            break
                    else:
                        f.seek(chunk_size + (chunk_size % 2), 1)

            min_frames = min(left_count, right_count)
            if min_frames == 0:
                results.append(f"Extraction failed: {avi_file.name}: Left {left_count}, Right {right_count}")
                continue

            # Merge images using PIL
            for idx in range(min_frames):
                left_img_path = temp_folder / f"left_{idx:04d}.jpg"
                right_img_path = temp_folder / f"right_{idx:04d}.jpg"
                combined_file = combined_folder / f"sbs_{idx:04d}.jpg"

                left_img = Image.open(left_img_path)
                right_img = Image.open(right_img_path)

                new_width = left_img.width + right_img.width
                new_height = max(left_img.height, right_img.height)

                sbs_img = Image.new('RGB', (new_width, new_height))
                sbs_img.paste(left_img, (0, 0))
                sbs_img.paste(right_img, (left_img.width, 0))
                sbs_img.save(combined_file, quality=95)

            # Create video
            sbs_video = output_path / f"{avi_file.stem}_SBS_noaudio.mp4"
            cmd_video = [
                "ffmpeg", "-y",
                "-framerate", str(framerate),
                "-i", str(combined_folder / "sbs_%04d.jpg"),
                "-c:v", "libx264", "-crf", "18", "-preset", "medium",
                "-pix_fmt", "yuv420p",
                str(sbs_video)
            ]
            subprocess.run(cmd_video, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Mux audio
            final_output = output_path / f"{avi_file.stem}_SBS.mp4"
            cmd_mux = [
                "ffmpeg", "-y",
                "-i", str(sbs_video),
                "-i", str(audio_file),
                "-c:v", "copy",
                "-c:a", "aac",
                str(final_output)
            ]
            subprocess.run(cmd_mux, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            shutil.rmtree(temp_folder, ignore_errors=True)
            if sbs_video.exists():
                sbs_video.unlink()

            results.append(f"✅ {avi_file.name} → {final_output.name} ({framerate} FPS)")

        return "\n".join(results)

    except Exception as e:
        return f"Error: {str(e)}"


def main():
    gr.Interface(
        fn=extract_and_create_sbs_with_audio,
        inputs=[
            gr.Textbox(label="Input AVI File or Folder", placeholder="C:/Videos/input.avi or folder"),
            gr.Textbox(label="Output Folder", placeholder="C:/Videos/Output"),
        ],
        outputs=gr.Textbox(label="Status"),
        title="Fuji 3D → SBS MP4 Batch Converter",
        description="Convert one AVI or a folder of AVIs to SBS MP4 with audio."
    ).launch()


if __name__ == "__main__":
    main()
