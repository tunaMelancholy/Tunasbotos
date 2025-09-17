import os
from pathlib import Path

def cleanup_files(file_paths: list):
    for path in file_paths:
        if Path(path).is_file():
            try:
                os.remove(path)
            except OSError as e:
                print(f" {path}\nError: {e}")