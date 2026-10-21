from app.api.routes.activity.device import DeviceHint, facts_from
from app.api.routes.activity.xlsx import workbook


def test_phone_model_comes_from_the_client_hint() -> None:
    facts = facts_from(
        DeviceHint(
            user_agent="Mozilla/5.0 (Linux; Android 14; K) AppleWebKit Chrome/120.0.0.0 Mobile",
            model="SM-A515F",
            platform="Android",
            mobile=True,
        )
    )
    assert facts.browser == "Chrome"
    assert facts.os_name == "Android"
    assert facts.device_type == "phone"
    assert facts.device_model == "SM-A515F"


def test_desktop_browser_has_no_invented_model() -> None:
    facts = facts_from(
        DeviceHint(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            platform="Windows",
            mobile=False,
        )
    )
    assert facts.browser == "Chrome"
    assert facts.os_name == "Windows"
    assert facts.device_type == "desktop"
    assert facts.device_model is None


def test_iphone_is_named_from_the_user_agent() -> None:
    facts = facts_from(DeviceHint(user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari/605.1"))
    assert facts.device_model == "iPhone"
    assert facts.device_type == "phone"
    assert facts.os_name == "iOS"


def test_workbook_is_an_xlsx_zip() -> None:
    payload = workbook([["When", "Person"], ["2026-10-22 09:00", "Asha"]])
    assert payload[:2] == b"PK"
