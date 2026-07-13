"""校招信息看板服务管理器：start / status / stop。"""
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
PID_FILE = DATA_DIR / "dashboard.pid"
LOG_FILE = DATA_DIR / "dashboard.log"
VERSION_FILE = PROJECT_DIR / "VERSION"
PORT = 8765
URL = f"http://localhost:{PORT}"
HEALTH_URL = f"{URL}/openapi.json"
ANALYSIS_SKILL = PROJECT_DIR / "app" / "prompts" / "interview_analysis.md"


def check(name: str) -> bool:
    try:
        result = subprocess.run(
            [sys.executable, "-c", f"import {name}"],
            capture_output=True,
            cwd=PROJECT_DIR,
        )
        return result.returncode == 0
    except OSError:
        return False


def process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        process_query = 0x1000
        still_active = 259
        handle = ctypes.windll.kernel32.OpenProcess(process_query, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == still_active
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError, PermissionError):
        return False


def service_ready(timeout: float = 1.0) -> bool:
    try:
        with urlopen(HEALTH_URL, timeout=timeout) as response:
            return response.status == 200
    except (OSError, URLError):
        return False


def read_pid() -> dict | None:
    try:
        data = json.loads(PID_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data.get("pid"), int) else None
    except (OSError, ValueError, TypeError):
        return None


def write_pid(pid: int) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(
        json.dumps(
            {"pid": pid, "started_at": datetime.now().isoformat(timespec="seconds"), "port": PORT},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def clear_pid() -> None:
    try:
        PID_FILE.unlink()
    except FileNotFoundError:
        pass


def ensure_dependencies() -> None:
    if not ANALYSIS_SKILL.is_file():
        raise RuntimeError(f"缺少内置简历分析 Skill: {ANALYSIS_SKILL}")
    need = {
        "fastapi": "FastAPI",
        "uvicorn": "Uvicorn",
        "requests": "requests",
        "dotenv": "python-dotenv",
        "multipart": "python-multipart",
        "docx": "python-docx",
        "pypdf": "pypdf",
        "markdown": "Markdown",
        "bleach": "bleach",
    }
    missing = [package for module, package in need.items() if not check(module)]
    if missing:
        print(f"[安装] 缺少依赖: {', '.join(missing)}")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            cwd=PROJECT_DIR,
            check=True,
        )


def start() -> int:
    metadata = read_pid()
    if metadata and process_alive(metadata["pid"]):
        print(f"[运行中] PID {metadata['pid']}  {URL}")
        return 0
    if metadata:
        clear_pid()
    if service_ready():
        print(f"[错误] 端口 {PORT} 已有服务响应，但不是由当前 PID 文件管理。")
        return 1

    try:
        ensure_dependencies()
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"[错误] {exc}")
        return 1

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    kwargs = {"cwd": PROJECT_DIR, "env": env}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True

    with LOG_FILE.open("a", encoding="utf-8") as log:
        log.write(f"\n[{datetime.now().isoformat(timespec='seconds')}] starting dashboard\n")
        log.flush()
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                str(PORT),
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            **kwargs,
        )
    write_pid(proc.pid)

    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            clear_pid()
            print(f"[错误] 服务启动失败，查看日志：{LOG_FILE}")
            return 1
        if service_ready():
            print(f"[已启动] PID {proc.pid}  {URL}")
            print(f"[日志] {LOG_FILE}")
            return 0
        time.sleep(0.4)

    stop_process(proc.pid)
    clear_pid()
    print(f"[错误] 服务启动超时，查看日志：{LOG_FILE}")
    return 1


def stop_process(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T"], capture_output=True)
    else:
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            return


def stop() -> int:
    metadata = read_pid()
    if not metadata:
        print("[未运行] 没有找到服务 PID 文件。")
        return 0
    pid = metadata["pid"]
    if not process_alive(pid):
        clear_pid()
        print("[未运行] 已清理失效的 PID 文件。")
        return 0

    stop_process(pid)
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline and process_alive(pid):
        time.sleep(0.25)
    if process_alive(pid) and os.name == "nt":
        subprocess.run(["taskkill", "/F", "/PID", str(pid), "/T"], capture_output=True)
    elif process_alive(pid):
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    clear_pid()
    print(f"[已停止] PID {pid}")
    return 0


def status() -> int:
    metadata = read_pid()
    if not metadata:
        if service_ready():
            print(f"[状态异常] {URL} 有服务响应，但没有 PID 文件。")
            return 1
        print("[已停止] 服务未运行。")
        return 1
    pid = metadata["pid"]
    alive = process_alive(pid)
    ready = service_ready()
    if alive and ready:
        print(f"[运行中] PID {pid}  {URL}")
        print(f"[启动时间] {metadata.get('started_at', '未知')}")
        print(f"[日志] {LOG_FILE}")
        return 0
    if not alive:
        clear_pid()
    print(f"[状态异常] PID存活={alive} HTTP就绪={ready}")
    return 1


def main() -> int:
    os.chdir(PROJECT_DIR)
    version = VERSION_FILE.read_text(encoding="utf-8").strip() if VERSION_FILE.exists() else ""
    command = (sys.argv[1] if len(sys.argv) > 1 else "start").lower()
    if command == "stauts":
        command = "status"
    commands = {"start": start, "status": status, "stop": stop}
    if command not in commands:
        print(f"校招信息看板 {version}")
        print("用法: python start-dashboard.py {start|status|stop}")
        return 2
    return commands[command]()


if __name__ == "__main__":
    raise SystemExit(main())
