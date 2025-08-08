from datetime import date, timedelta

from utils import get_links_for_period


def test_get_links_for_period_inclusive():
    today = date.today()
    links = [
        {"url": "yesterday", "date_str": (today - timedelta(days=1)).strftime("%d.%m.%Y")},
        {"url": "today", "date_str": today.strftime("%d.%m.%Y")},
        {"url": "future", "date_str": (today + timedelta(days=1)).strftime("%d.%m.%Y")},
    ]

    assert get_links_for_period(today, today, links) == ["today"]
    assert get_links_for_period(today - timedelta(days=1), today - timedelta(days=1), links) == ["yesterday"]
    assert get_links_for_period(today - timedelta(days=1), today, links) == ["yesterday", "today"]
