"""Quiet desktop launcher for the frozen Lioran application."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

APP_URL = "http://127.0.0.1:8000"
OLLAMA_DOWNLOAD_URL = "https://ollama.com/download"
MODEL = "hermes3:8b"
APP_NAME = "Lioran"


def _data_dir() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    elif sys.platform == "darwin":
        root = Path.home() / "Library/Application Support"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    path = root / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _ollama_binary() -> str | None:
    binary = shutil.which("ollama")
    if binary:
        return binary
    candidates = []
    if sys.platform == "darwin":
        candidates.extend(
            [
                Path("/Applications/Ollama.app/Contents/Resources/ollama"),
                Path.home() / "Applications/Ollama.app/Contents/Resources/ollama",
            ]
        )
    elif sys.platform == "win32":
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        candidates.extend(
            [
                local / "Programs/Ollama/ollama.exe",
                Path(os.environ.get("PROGRAMFILES", "C:/Program Files"))
                / "Ollama/ollama.exe",
            ]
        )
    return next((str(path) for path in candidates if path.is_file()), None)


def _ollama_url() -> str:
    return os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")


def _ollama_tags() -> list[str] | None:
    try:
        with urllib.request.urlopen(f"{_ollama_url()}/api/tags", timeout=2) as response:
            data = json.loads(response.read())
        return [model.get("name", "") for model in data.get("models", [])]
    except (OSError, ValueError, urllib.error.URLError):
        return None


def _message(title: str, message: str, *, error: bool = False) -> None:
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()
    if error:
        messagebox.showerror(title, message, parent=root)
    else:
        messagebox.showinfo(title, message, parent=root)
    root.destroy()


def _run_progress(
    title: str,
    message: str,
    command: list[str],
    log_file: Path,
    environment: dict[str, str] | None = None,
) -> bool:
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title(title)
    root.resizable(False, False)
    root.geometry("430x130")
    root.eval("tk::PlaceWindow . center")
    root.protocol("WM_DELETE_WINDOW", lambda: None)
    ttk.Label(root, text=message, wraplength=390, justify="left").pack(
        padx=20, pady=(22, 14), anchor="w"
    )
    progress = ttk.Progressbar(root, mode="indeterminate", length=390)
    progress.pack(padx=20, pady=(0, 18))
    progress.start(12)
    root.update()

    try:
        with log_file.open("ab") as output:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                env=environment,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                start_new_session=sys.platform != "win32",
            )
            while process.poll() is None:
                root.update()
                time.sleep(0.15)
    except OSError:
        logging.exception("Could not run setup command: %s", command[0])
        root.destroy()
        return False
    progress.stop()
    root.destroy()
    return process.returncode == 0


def _wait_with_progress(title: str, message: str, check, timeout: int) -> bool:
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title(title)
    root.resizable(False, False)
    root.geometry("430x130")
    root.eval("tk::PlaceWindow . center")
    root.protocol("WM_DELETE_WINDOW", lambda: None)
    ttk.Label(root, text=message, wraplength=390, justify="left").pack(
        padx=20, pady=(22, 14), anchor="w"
    )
    progress = ttk.Progressbar(root, mode="indeterminate", length=390)
    progress.pack(padx=20, pady=(0, 18))
    progress.start(12)
    result = {"ready": False}
    deadline = time.monotonic() + timeout

    def poll() -> None:
        try:
            result["ready"] = bool(check())
        except Exception:
            result["ready"] = False
        if result["ready"] or time.monotonic() >= deadline:
            root.quit()
        else:
            root.after(1000, poll)

    root.after(0, poll)
    root.mainloop()
    progress.stop()
    root.destroy()
    return result["ready"]


def _ensure_ollama(binary: str, log_file: Path) -> bool:
    if _ollama_tags() is not None:
        return True

    try:
        with log_file.open("ab") as output:
            subprocess.Popen(
                [binary, "serve"],
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                start_new_session=sys.platform != "win32",
            )
    except OSError:
        logging.exception("Could not start Ollama")
        return False
    return _wait_with_progress(
        "Lioran",
        "Starting the local Ollama service…",
        lambda: _ollama_tags() is not None,
        timeout=60,
    )


def _ensure_model(binary: str, log_file: Path) -> bool:
    models = _ollama_tags()
    if models is None:
        return False
    if any(name == MODEL or name.startswith(f"{MODEL}:") for name in models):
        return True
    return _run_progress(
        "Lioran",
        f"Downloading {MODEL} (about 4.7 GB). This may take a while.",
        [binary, "pull", MODEL],
        log_file,
    )


def _browser_executable(module_name: str) -> Path:
    from importlib import import_module

    api = import_module(f"{module_name}.sync_api")
    with api.sync_playwright() as playwright:
        return Path(playwright.chromium.executable_path)


def _install_browser(module_name: str, log_file: Path) -> bool:
    from importlib import import_module

    try:
        driver = import_module(f"{module_name}._impl._driver")
        executable, cli = driver.compute_driver_executable()
        command = [executable, cli, "install", "chromium"]
        environment = driver.get_driver_env()
        environment["PLAYWRIGHT_BROWSERS_PATH"] = os.environ.get(
            "PLAYWRIGHT_BROWSERS_PATH", ""
        )
    except Exception:
        logging.exception("Could not prepare %s browser installation", module_name)
        return False
    return _run_progress(
        "Lioran",
        f"Installing the {module_name.capitalize()} Chromium browser. This may take a few minutes.",
        command,
        log_file,
        environment,
    )


def _ensure_browsers(log_file: Path) -> bool:
    for module_name in ("playwright", "patchright"):
        try:
            if _browser_executable(module_name).is_file():
                continue
        except Exception:
            logging.exception("Could not inspect %s browser installation", module_name)
        if not _install_browser(module_name, log_file):
            return False
    return True


def _healthcheck() -> bool:
    try:
        with urllib.request.urlopen(f"{APP_URL}/health", timeout=1) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def _port_available() -> bool:
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", 8000))
            return True
        except OSError:
            return False


def _start_server(log_file: Path) -> threading.Thread | bool:
    if _healthcheck():
        return True
    if not _port_available():
        _message(
            "Lioran",
            "Port 8000 is already in use. Close the other app using it and try again.",
            error=True,
        )
        return False

    try:
        import uvicorn
        from app.main import app

        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host="127.0.0.1",
                port=8000,
                log_level="info",
                log_config=None,
                access_log=False,
            )
        )
        thread = threading.Thread(target=server.run, name="lioran-api", daemon=True)
        thread.start()
    except Exception:
        logging.exception("Could not start the Lioran API")
        return False

    for _ in range(100):
        if _healthcheck():
            return thread
        if not thread.is_alive():
            return False
        time.sleep(0.1)
    return False


def main() -> None:
    data_dir = _data_dir()
    os.chdir(data_dir)
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(data_dir / "browsers"))
    log_file = data_dir / "lioran.log"
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        from dotenv import load_dotenv

        load_dotenv(data_dir / ".env")
    except ImportError:
        logging.exception("Could not load Lioran settings")

    binary = _ollama_binary()
    if binary is None:
        _message(
            "Ollama is required",
            "Install Ollama, then launch Lioran again. The Ollama download page will open.",
            error=True,
        )
        webbrowser.open(OLLAMA_DOWNLOAD_URL)
        return
    if not _ensure_ollama(binary, log_file):
        _message(
            "Ollama is not responding",
            f"Lioran could not start Ollama. Check the Ollama installation and see:\n{log_file}",
            error=True,
        )
        return
    if not _ensure_model(binary, log_file):
        _message(
            "Model download failed",
            f"Lioran could not download {MODEL}. Check your internet connection and see:\n{log_file}",
            error=True,
        )
        return
    if not _ensure_browsers(log_file):
        _message(
            "Browser setup failed",
            f"Lioran could not install its Chromium browser. Check your internet connection and see:\n{log_file}",
            error=True,
        )
        return

    server_thread = _start_server(log_file)
    if server_thread is False:
        _message(
            "Lioran could not start",
            f"The local server did not start. See the diagnostic log:\n{log_file}",
            error=True,
        )
        return

    webbrowser.open(APP_URL)
    if isinstance(server_thread, threading.Thread):
        server_thread.join()


if __name__ == "__main__":
    main()
