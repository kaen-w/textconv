"""检查 GitHub 上的新版本。

只做两件事：查最新 Release、下载安装包。UI 由各平台的托盘/菜单负责。

GitHub API 在部分网络环境下不可达，所以：
- 失败时静默返回 None（自动检查不会打扰用户）
- 可用 TEXTCONV_UPDATE_URL 指向自建镜像（返回同样的 JSON 结构）
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import sys
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from . import __version__

log = logging.getLogger(__name__)

REPO = "kaen-w/textconv"
DEFAULT_API = f"https://api.github.com/repos/{REPO}/releases/latest"
USER_AGENT = f"TextConv/{__version__} (+https://github.com/{REPO})"


@dataclass
class Release:
    version: str
    tag: str
    page_url: str
    notes: str = ""
    assets: Dict[str, str] = field(default_factory=dict)  # 文件名 -> 下载地址


def parse_version(text: str) -> Tuple[int, ...]:
    """'v0.2.13' -> (0, 2, 13)；解析不了的段按 0 处理。"""
    cleaned = (text or "").strip().lstrip("vV")
    parts: List[int] = []
    for chunk in cleaned.split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def is_newer(remote: str, local: str) -> bool:
    return parse_version(remote) > parse_version(local)


def api_url() -> str:
    return os.environ.get("TEXTCONV_UPDATE_URL") or DEFAULT_API


def fetch_latest(timeout: float = 8.0) -> Optional[Release]:
    """查询最新 Release；网络失败返回 None，不抛异常。"""
    request = urllib.request.Request(
        api_url(),
        headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except Exception as exc:
        log.info("检查更新失败：%s", exc)
        return None

    tag = str(payload.get("tag_name") or "")
    assets = {
        str(item.get("name")): str(item.get("browser_download_url"))
        for item in payload.get("assets") or []
        if item.get("name") and item.get("browser_download_url")
    }
    return Release(
        version=tag.lstrip("vV"),
        tag=tag,
        page_url=str(payload.get("html_url") or f"https://github.com/{REPO}/releases/latest"),
        notes=str(payload.get("body") or ""),
        assets=assets,
    )


def pick_asset(release: Release, platform: Optional[str] = None) -> Optional[str]:
    """按平台挑安装包：Windows 用 Setup，macOS 用 dmg。"""
    platform = platform or ("win32" if sys.platform == "win32" else "darwin")
    if platform == "win32":
        for name, url in release.assets.items():
            if name.startswith("TextConv-Setup-") and name.endswith(".exe"):
                return url
        return None
    for name, url in release.assets.items():
        if name.endswith(".dmg"):
            return url
    return None


def download(url: str, dest: str, timeout: float = 60.0) -> str:
    """下载到 dest，返回路径。失败抛异常。"""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    os.makedirs(os.path.dirname(os.path.abspath(dest)) or ".", exist_ok=True)
    with urllib.request.urlopen(request, timeout=timeout) as response, open(dest, "wb") as fh:
        while True:
            chunk = response.read(64 * 1024)
            if not chunk:
                break
            fh.write(chunk)
    return dest


def due_for_check(last_iso: str, hours: int = 24) -> bool:
    """距上次检查超过 hours 小时（或从未检查过）就返回 True。"""
    if not last_iso:
        return True
    try:
        last = datetime.datetime.fromisoformat(last_iso)
    except ValueError:
        return True
    return datetime.datetime.now() - last >= datetime.timedelta(hours=hours)
