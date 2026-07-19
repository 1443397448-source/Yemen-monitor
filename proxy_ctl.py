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


def _proxy_ready(proxy_url, timeout=5):
    """通过代理访问一个稳定网站来验证代理是否真正可用（非仅端口开放）。"""
    import urllib.request
    host, port = _addr(proxy_url)
    proxy_handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
    opener = urllib.request.build_opener(proxy_handler)
    try:
        opener.open("https://www.google.com", timeout=timeout)
        return True
    except Exception:
        return False


def ensure_proxy(proxy_url, app_name, wait_seconds=90):
    """返回 (端口是否就绪, 是否由本程序启动)。"""
    host, port = _addr(proxy_url)
    if _port_open(host, port):
        time.sleep(2)
        if _proxy_ready(proxy_url, 8):
            return True, False
    try:
        subprocess.run(["open", "-g", "-a", app_name],
                       check=True, capture_output=True, timeout=15)
    except Exception:
        return False, False
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if _port_open(host, port):
            time.sleep(8)  # 等 Clash 核心完全加载
            for _ in range(6):  # 再等最多 30 秒直到代理真正可用
                if _proxy_ready(proxy_url, 5):
                    return True, True
                time.sleep(5)
            return True, True  # 端口可达就继续，碰运气
        time.sleep(3)
    return False, True


def stop_proxy(app_name):
    subprocess.run(["osascript", "-e", f'quit app "{app_name}"'],
                   capture_output=True, timeout=20)
    time.sleep(3)
    if subprocess.run(["pgrep", "-f", app_name],
                      capture_output=True).returncode == 0:
        subprocess.run(["pkill", "-f", app_name], capture_output=True)
