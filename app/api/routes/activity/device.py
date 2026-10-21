"""Browser and device facts taken from the user agent and optional client hints.

A browser will not reveal a hardware model on most desktops. Phones sometimes do,
through the user agent or the User-Agent Client Hints API.
"""

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class DeviceHint:
    user_agent: str | None = None
    model: str | None = None
    platform: str | None = None
    mobile: bool | None = None


@dataclass(frozen=True)
class DeviceFacts:
    browser: str
    os_name: str
    device_type: str
    device_model: str | None
    label: str


_ANDROID_MODEL = re.compile(r"Android [^;)]*;\s*([^;)]+)")
_SKIP_MODEL = frozenset({"mobile", "wv", "k", "linux", "android", "u"})


def facts_from(hint: DeviceHint) -> DeviceFacts:
    agent = (hint.user_agent or "")[:400]
    browser = _browser(agent)
    os_name = _clip(hint.platform, 48) or _os_name(agent)
    model = _clip(hint.model, 80) or _model_from_agent(agent)
    if model and model.lower() in {os_name.lower(), browser.lower()}:
        model = _model_from_agent(agent)
    kind = _kind(agent, hint.mobile, model)
    label = f"{browser} on {os_name}"
    if model:
        label = f"{label} · {model}"
    return DeviceFacts(browser[:48], os_name[:48], kind, model, label[:120])


def _clip(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    text = " ".join(value.split())
    if not text or text.lower() in {"unknown", "null", "undefined"}:
        return None
    return text[:limit]


def _browser(agent: str) -> str:
    if "Edg/" in agent or "Edge/" in agent:
        return "Edge"
    if "OPR/" in agent or "Opera" in agent:
        return "Opera"
    if "Chrome/" in agent or "CriOS/" in agent:
        return "Chrome"
    if "Firefox/" in agent or "FxiOS/" in agent:
        return "Firefox"
    if "Safari/" in agent:
        return "Safari"
    return "Browser"


def _os_name(agent: str) -> str:
    if "Windows" in agent:
        return "Windows"
    if "Android" in agent:
        return "Android"
    if "iPhone" in agent or "iPad" in agent:
        return "iOS"
    if "Mac OS" in agent or "Macintosh" in agent:
        return "macOS"
    if "Linux" in agent:
        return "Linux"
    return "Unknown system"


def _model_from_agent(agent: str) -> str | None:
    if "iPad" in agent:
        return "iPad"
    if "iPhone" in agent:
        return "iPhone"
    match = _ANDROID_MODEL.search(agent)
    if match is None:
        return None
    token = match.group(1).strip()
    if token.lower() in _SKIP_MODEL or token.lower().startswith("linux"):
        return None
    return token[:80]


def _kind(agent: str, mobile: bool | None, model: str | None) -> str:
    if "iPad" in agent or (model or "").lower().find("tablet") >= 0:
        return "tablet"
    if mobile is True or "iPhone" in agent or "Android" in agent or "Mobile" in agent:
        return "phone"
    return "desktop"
