import json
import subprocess
def main(file_list):
    processed_path = "processed.mp4"
    command_ffmpeg = [
        'ffmpeg',
        '-i', file_list[0],
        '-c', 'copy',
        '-movflags', '+faststart',
        processed_path,
        '-y'
    ]
    subprocess.run(command_ffmpeg, check=True, capture_output=True)
    command = [
        'ffprobe',
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_streams',
        processed_path
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    metadata = json.loads(result.stdout)
    video_stream = next((stream for stream in metadata['streams'] if stream['codec_type'] == 'video'), None)
    width = int(video_stream['width'])
    height = int(video_stream['height'])
    duration = int(float(video_stream['duration']))
    return processed_path, width, height, duration
