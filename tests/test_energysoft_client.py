import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("RAWA_EMAIL", "test@example.com")
os.environ.setdefault("RAWA_PASSWORD", "password")
os.environ.setdefault("ENERGYSOFT_USER", "user")
os.environ.setdefault("ENERGYSOFT_PASSWORD", "pass")
os.environ.setdefault("TELEGRAM_TOKEN", "token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "123")
os.environ.setdefault("BREVO_API_KEY", "key")
os.environ.setdefault("SENDER_EMAIL", "sender@example.com")
os.environ.setdefault("RECEIVER_EMAIL", "receiver@example.com")

from app.collectors.energysoft import EnergysoftClient


def test_odata_key_uses_quoted_literal_values():
    client = EnergysoftClient()

    assert client._get_odata_key("834") == "'834'"
    assert client._get_odata_key(834) == "'834'"
    assert client._get_odata_key("site-834") == "'site-834'"


def test_matches_site_hints_from_nested_records():
    client = EnergysoftClient()
    record = {
        "ID": "inv-1",
        "Site": {
            "Name": "CRF - AC+IR - CRF CANNES LA BOCCA - 270,48kWc",
            "Id": "7236",
        },
    }

    assert client._record_matches_hints(record, ["7236", "CRF CANNES LA BOCCA"])
