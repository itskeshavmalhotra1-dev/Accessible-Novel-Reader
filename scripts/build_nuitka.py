"""
Nuitka Standalone Build & Packaging Script for Accessible Novel Reader.
Compiles Python application into a standalone Windows executable (.exe) using Nuitka + Zig/C compiler.
Includes ONLY required runtime packages:
- novel_reader (application core, UI, sources)
- accessible_output2 (screen reader drivers and DLLs)
- curl_cffi and requests (HTTP networking)
- bs4 and soupsieve (HTML parsing)
- charset_normalizer
- wxPython (desktop GUI)

Strips all unnecessary bloatware:
PyQt, PySide, Tkinter, Trio, Pytest, Unittest, Setuptools, Numpy, Pandas, Torch, etc.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from novel_reader.updater import CURRENT_VERSION

DIST_DIR = BASE_DIR / "dist"
BUILD_DIR = DIST_DIR / "main.dist"
TARGET_DIR = DIST_DIR / "Accessible_Novel_Reader"
ZIP_NAME = f"Accessible_Novel_Reader_v{CURRENT_VERSION}.zip"
ZIP_PATH = DIST_DIR / ZIP_NAME

BLOAT_MODULES = [
    "pytest", "unittest", "doctest", "pydoc", "test", "tests",
    "trio", "setuptools", "pip", "distutils", "tkinter",
    "PyQt5", "PyQt6", "PySide2", "PySide6",
    "matplotlib", "scipy", "numpy", "pandas", "IPython", "jupyter",
    "curses", "PIL", "cv2", "torch", "tensorflow", "moviepy", "pygame",
    "selenium", "yt_dlp", "onnxruntime", "sympy", "pypdf", "fitz", "pymupdf",
]


def clean_previous_builds() -> None:
    """Clean dist directory while preserving the C compilation cache for faster builds."""
    print("Cleaning previous distribution artifacts in dist/...")
    if DIST_DIR.exists():
        for item in DIST_DIR.iterdir():
            if item.name == "main.build":
                continue  # Preserve incremental C compiler cache
            try:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            except Exception:
                pass


def build() -> None:
    clean_previous_builds()
    print(f"\n=== Starting Optimized Nuitka Compilation for v{CURRENT_VERSION} ===")
    start_time = time.time()

    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--assume-yes-for-downloads",
        "--windows-console-mode=disable",
        "--output-dir=dist",
        "--output-filename=Accessible_Novel_Reader.exe",
        "--jobs=8",
        # Explicit core packages
        "--include-package=novel_reader",
        "--include-package=accessible_output2",
        "--include-package=platform_utils",
        "--include-package=libloader",
        "--include-package=curl_cffi",
        "--include-package=bs4",
        "--include-package=soupsieve",
        "--include-package=requests",
        "--include-package=charset_normalizer",
        "--include-package-data=accessible_output2",
        "--include-package-data=curl_cffi",
        # Anti-bloat exclusions
        "--enable-plugin=no-qt",
        "--noinclude-pytest-mode=nofollow",
        "--noinclude-unittest-mode=nofollow",
        "--noinclude-setuptools-mode=nofollow",
        "--noinclude-pydoc-mode=nofollow",
        "--noinclude-IPython-mode=nofollow",
        "--noinclude-default-mode=nofollow",
        f"--nofollow-import-to={','.join(BLOAT_MODULES)}",
        "main.py",
    ]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC_DIR) + os.pathsep + env.get("PYTHONPATH", "")

    print("Running compilation command...")
    proc = subprocess.run(cmd, cwd=str(BASE_DIR), env=env)
    if proc.returncode != 0:
        print(f"Compilation failed with exit code: {proc.returncode}")
        sys.exit(proc.returncode)

    elapsed = time.time() - start_time
    print(f"\nCompilation completed successfully in {elapsed:.1f} seconds!")

    # Locate generated output directory
    cand_dir = None
    if BUILD_DIR.exists():
        cand_dir = BUILD_DIR
    elif (DIST_DIR / "Accessible_Novel_Reader.dist").exists():
        cand_dir = DIST_DIR / "Accessible_Novel_Reader.dist"

    if not cand_dir or not cand_dir.exists():
        print("Error: Could not locate compiled distribution folder.")
        sys.exit(1)

    print(f"Found compiled distribution at: {cand_dir}")

    if TARGET_DIR.exists():
        shutil.rmtree(TARGET_DIR)
    shutil.copytree(cand_dir, TARGET_DIR)
    print(f"Synced build output to {TARGET_DIR}")

    # Copy screen reader DLLs into root of TARGET_DIR for guaranteed discovery
    try:
        import accessible_output2
        ao2_lib = Path(accessible_output2.__file__).parent / "lib"
        if ao2_lib.exists():
            for dll in ao2_lib.glob("*.dll"):
                shutil.copy2(dll, TARGET_DIR / dll.name)
            target_ao2_lib = TARGET_DIR / "accessible_output2" / "lib"
            target_ao2_lib.mkdir(parents=True, exist_ok=True)
            for dll in ao2_lib.glob("*.dll"):
                shutil.copy2(dll, target_ao2_lib / dll.name)
            print("Successfully verified and bundled screen-reader DLLs.")
    except Exception as e:
        print(f"Notice: Accessible DLL verification: {e}")

    # Copy curl_cffi libs if present in environment
    try:
        import curl_cffi
        site_packages = Path(curl_cffi.__file__).parent.parent
        curl_libs = site_packages / "curl_cffi.libs"
        if curl_libs.exists():
            for dll in curl_libs.glob("*.dll"):
                shutil.copy2(dll, TARGET_DIR / dll.name)
            print("Successfully verified and bundled curl-impersonate runtime DLLs.")
    except Exception as e:
        print(f"Notice: Curl DLL verification: {e}")

    # Copy documentation
    readme = BASE_DIR / "README.md"
    if readme.exists():
        shutil.copy2(readme, TARGET_DIR / "README.md")

    # Compress into distribution ZIP
    print(f"\nCompressing standalone distribution into {ZIP_PATH}...")
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(TARGET_DIR):
            for file in files:
                abs_file = Path(root) / file
                rel_file = abs_file.relative_to(TARGET_DIR)
                zf.write(abs_file, Path("Accessible_Novel_Reader") / rel_file)

    zip_size_mb = ZIP_PATH.stat().st_size / (1024 * 1024)
    print(f"Successfully packaged {ZIP_NAME}! Archive size: {zip_size_mb:.1f} MB")
    print(f"Standalone executable ready at: {TARGET_DIR / 'Accessible_Novel_Reader.exe'}")

    # Write version.json manifest
    manifest = {
        "version": CURRENT_VERSION,
        "release_tag": f"v{CURRENT_VERSION}",
        "release_name": f"Accessible Novel Reader v{CURRENT_VERSION}",
        "archive_name": ZIP_NAME,
        "archive_size_bytes": ZIP_PATH.stat().st_size,
    }
    manifest_path = DIST_DIR / "version.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"Generated release manifest at {manifest_path}")


if __name__ == "__main__":
    build()
