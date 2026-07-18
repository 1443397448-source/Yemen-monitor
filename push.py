"""推送模块：企业微信群机器人文件直传 + Server酱微信 双通道。"""
import os

import requests

MAX_B = 29000  # Server酱 desp 安全上限


# ── 企业微信群机器人：文件直传（推荐，150KB 一个文件搞定） ──

def push_wecom_file(webhook_key, file_path, summary, timeout=30):
    """上传 Markdown 报告文件到企业微信群 + 附一条 markdown 摘要。
    Key 从群机器人 Webhook URL 末尾提取。"""
    if not webhook_key:
        return "未配置 WECOM_WEBHOOK_KEY"

    base = f"https://qyapi.weixin.qq.com/cgi-bin/webhook"

    # 1. 上传文件 → media_id
    try:
        with open(file_path, "rb") as fh:
            r = requests.post(
                f"{base}/upload_media?key={webhook_key}&type=file",
                files={"media": (os.path.basename(file_path), fh,
                                 "application/octet-stream")},
                timeout=timeout)
        data = r.json()
        media_id = data.get("media_id")
        if not media_id:
            return f"企业微信文件上传失败: {data}"
    except Exception as e:
        return f"企业微信文件上传异常: {e}"

    send_url = f"{base}/send?key={webhook_key}"

    # 2. 发送文件到群
    try:
        r = requests.post(send_url,
                          json={"msgtype": "file", "file": {"media_id": media_id}},
                          timeout=timeout)
        if r.json().get("errcode") != 0:
            return f"企业微信文件发送失败: {r.json()}"
    except Exception as e:
        return f"企业微信文件发送异常: {e}"

    # 3. 附送 markdown 摘要（企微最多 4096 字符）
    try:
        requests.post(send_url,
                      json={"msgtype": "markdown",
                            "markdown": {"content": summary[:4000]}},
                      timeout=timeout)
    except Exception:
        pass

    return None


# ── Server酱：方糖个人微信或企业微信应用（备用，有 32KB 限制） ──

def push_serverchan(title, body, timeout=20):
    key = os.environ.get("SERVERCHAN_SENDKEY")
    if not key:
        return "未设置 SERVERCHAN_SENDKEY"
    body_bytes = body.encode("utf-8")
    if len(body_bytes) > MAX_B:
        body = body_bytes[:MAX_B].decode("utf-8", errors="ignore")
        body = body[:body.rfind("\n")] + "\n\n> ⚠️ 内容过长已截断"
    try:
        r = requests.post(f"https://sctapi.ftqq.com/{key}.send",
                          data={"title": title[:32], "desp": body},
                          timeout=timeout)
        return None if r.json().get("code") == 0 else f"Server酱: {r.json()}"
    except Exception as e:
        return f"Server酱异常: {e}"
