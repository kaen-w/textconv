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


def download(url: str, dest: str, timeout: float = 60.0, progress=None) -> str:
    """下载到 dest，返回路径。失败抛异常。

    progress(done, total) 会在下载过程中被调用，total 未知时为 0。
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    os.makedirs(os.path.dirname(os.path.abspath(dest)) or ".", exist_ok=True)
    with urllib.request.urlopen(request, timeout=timeout) as response, open(dest, "wb") as fh:
        try:
            total = int(response.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            total = 0
        done = 0
        last_reported = -1
        while True:
            chunk = response.read(64 * 1024)
            if not chunk:
                break
            fh.write(chunk)
            done += len(chunk)
            if progress is not None:
                percent = int(done * 100 / total) if total else 0
                if percent != last_reported:
                    last_reported = percent
                    try:
                        progress(done, total)
                    except Exception:
                        pass
    return dest


def install_dmg(dmg_path: str, app_name: str = "TextConv.app", target: str = "/Applications") -> str:
    """把 dmg 里的 App 复制到 /Applications，返回安装路径。失败抛异常。"""
    import shutil
    import subprocess
    import tempfile

    mount = tempfile.mkdtemp(prefix="textconv-update-")
    mounted = False
    try:
        result = subprocess.run(
            ["hdiutil", "attach", dmg_path, "-nobrowse", "-quiet", "-mountpoint", mount],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "挂载 dmg 失败")
        mounted = True

        source = os.path.join(mount, app_name)
        if not os.path.isdir(source):
            raise RuntimeError(f"dmg 里没有 {app_name}")

        os.makedirs(target, exist_ok=True)
        destination = os.path.join(target, app_name)
        backup = destination + ".old"
        if os.path.exists(backup):
            shutil.rmtree(backup, ignore_errors=True)
        if os.path.exists(destination):
            os.rename(destination, backup)
        try:
            shutil.copytree(source, destination, symlinks=True)
        except Exception:
            # 复制失败就把旧版本还原，别让用户既没新的也没旧的
            shutil.rmtree(destination, ignore_errors=True)
            if os.path.exists(backup):
                os.rename(backup, destination)
            raise
        shutil.rmtree(backup, ignore_errors=True)
        return destination
    finally:
        if mounted:
            subprocess.run(["hdiutil", "detach", mount, "-quiet"], capture_output=True)
        shutil.rmtree(mount, ignore_errors=True)


def due_for_check(last_iso: str, hours: int = 24) -> bool:
    """距上次检查超过 hours 小时（或从未检查过）就返回 True。"""
    if not last_iso:
        return True
    try:
        last = datetime.datetime.fromisoformat(last_iso)
    except ValueError:
        return True
    return datetime.datetime.now() - last >= datetime.timedelta(hours=hours)
