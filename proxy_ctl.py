"""按需自动启停代理 App（Clash Verge 等）。
原则：端口已开放则不动它；只有本程序启动的实例才会在运行结束后被退出，
避免误关用户自己正在使用的代理。"""
import socket
import subprocess
import time
from urllib.parse import urlsplit


def _addr(proxy_url):
    p = urlsplit(proxy_url)
    return p.hostname or "127.0.0.1", p.port or 7890


def _port_open(host, port, timeout=1.0):
    try:
        with socket.create_connection((host, port), timeout):
            return True
    except OSError:
        return False


def ensure_proxy(proxy_url, app_name, wait_seconds=45):
    """返回 (端口是否就绪, 是否由本程序启动)。"""
    host, port = _addr(proxy_url)
    if _port_open(host, port):
        return True, False
    try:
        subprocess.run(["open", "-g", "-a", app_name],
                       check=True, capture_output=True, timeout=15)
    except Exception:
        return False, False
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if _port_open(host, port):
            time.sleep(5)  # 等代理核心完全就绪
            return True, True
        time.sleep(2)
    return False, True


def stop_proxy(app_name):
    subprocess.run(["osascript", "-e", f'quit app "{app_name}"'],
                   capture_output=True, timeout=20)
    time.sleep(3)
    if subprocess.run(["pgrep", "-f", app_name],
                      capture_output=True).returncode == 0:
        subprocess.run(["pkill", "-f", app_name], capture_output=True)
