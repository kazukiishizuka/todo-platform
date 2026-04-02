from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.schemas import ParseResult


WEEKDAY_MAP = {
    "月": 0,
    "火": 1,
    "水": 2,
    "木": 3,
    "金": 4,
    "土": 5,
    "日": 6,
}

RELATIVE_DATES = {
    "今日": 0,
    "明日": 1,
    "明後日": 2,
}

TIME_WORDS = {
    "朝": 9,
    "昼": 12,
    "夕方": 17,
    "夜": 20,
    "正午": 12,
}


@dataclass
class ParsedDateTime:
    due_date: datetime | None = None
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None
    is_all_day: bool = False
    recurrence_rule: str | None = None
    ambiguity_flags: list[str] | None = None


class NaturalLanguageParser:
    def __init__(self) -> None:
        self.settings = get_settings()

    def parse(self, text: str, timezone_name: str, now: datetime | None = None) -> ParseResult:
        now = now or datetime.now(ZoneInfo(timezone_name))
        lowered = self._normalize_text(text)
        intent = self._detect_intent(lowered)
        parsed = self._extract_datetime(lowered, timezone_name, now)
        title = self._extract_title(lowered)
        ambiguity_flags = parsed.ambiguity_flags or []
        if "毎週" not in lowered and any(f"{day}曜" in lowered for day in WEEKDAY_MAP) and "weekday_needs_week_scope" not in ambiguity_flags:
            ambiguity_flags.append("weekday_needs_week_scope")
        if any(f"{day}曜" in lowered for day in WEEKDAY_MAP) and any(f"{hour}時" in lowered for hour in range(1, 12)) and "午前" not in lowered and "午後" not in lowered and "hour_needs_meridiem" not in ambiguity_flags:
            ambiguity_flags.append("hour_needs_meridiem")
        confidence = 0.92 if parsed.start_datetime or parsed.due_date else 0.45
        if not title:
            title = lowered
            ambiguity_flags.append("title_inferred_from_original")
            confidence -= 0.05
        parse_status = self._determine_status(parsed, ambiguity_flags)
        if intent == "create" and parse_status == "on_hold" and title and not ambiguity_flags:
            parse_status = "confirmed"
            confidence = max(confidence, 0.7)
        return ParseResult(
            original_text=text,
            title=title,
            due_date=parsed.due_date.date() if parsed.due_date else None,
            start_datetime=parsed.start_datetime,
            end_datetime=parsed.end_datetime,
            timezone=timezone_name,
            is_all_day=parsed.is_all_day,
            recurrence_rule=parsed.recurrence_rule,
            confidence=max(0.0, min(confidence, 0.99)),
            ambiguity_flags=ambiguity_flags,
            parse_status=parse_status,
            intent=intent,
        )

    def _normalize_text(self, text: str) -> str:
        import re

        normalized = text.strip()
        normalized = re.sub(r"<@[^>]+>", " ", normalized)
        normalized = normalized.replace("&nbsp;", " ")
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()

    def clean_title(self, text: str) -> str:
        import re

        cleaned = self._normalize_text(text)
        cleaned = re.sub(r"^(から|まで)\s*", "", cleaned)
        cleaned = re.sub(r"\s+(から|まで)$", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" 。")
        return cleaned

    def _detect_intent(self, text: str) -> str:
        if any(token in text for token in ["完了", "終わった"]):
            return "complete"
        if any(token in text for token in ["消して", "削除", "キャンセル", "取り消し"]):
            return "delete"
        if any(token in text for token in ["変更", "して", "変えて"]):
            return "update"
        if any(token in text for token in ["教えて", "見せて", "一覧", "ある？", "表示"]):
            return "query"
        return "create"

    def _extract_datetime(self, text: str, timezone_name: str, now: datetime) -> ParsedDateTime:
        tz = ZoneInfo(timezone_name)
        ambiguity_flags: list[str] = []
        recurrence_rule = self._extract_recurrence(text)
        target_date = None
        for word, offset in RELATIVE_DATES.items():
            if word in text:
                target_date = (now + timedelta(days=offset)).date()
                break

        if target_date is None:
            target_date = self._extract_explicit_date(text, now, ambiguity_flags)

        hour, minute = self._extract_time(text, ambiguity_flags)

        if target_date and hour is not None:
            start = datetime(target_date.year, target_date.month, target_date.day, hour, minute, tzinfo=tz)
            end = start + timedelta(minutes=self.settings.default_event_duration_minutes)
            return ParsedDateTime(start_datetime=start, end_datetime=end, recurrence_rule=recurrence_rule, ambiguity_flags=ambiguity_flags)
        if target_date:
            due = datetime(target_date.year, target_date.month, target_date.day, tzinfo=tz)
            return ParsedDateTime(due_date=due, is_all_day=True, recurrence_rule=recurrence_rule, ambiguity_flags=ambiguity_flags)
        return ParsedDateTime(ambiguity_flags=ambiguity_flags, recurrence_rule=recurrence_rule)

    def _extract_recurrence(self, text: str) -> str | None:
        if "毎日" in text:
            return "FREQ=DAILY"
        if "平日" in text:
            return "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"
        for jp, byday in [("月", "MO"), ("火", "TU"), ("水", "WE"), ("木", "TH"), ("金", "FR"), ("土", "SA"), ("日", "SU")]:
            if f"毎週{jp}曜" in text:
                return f"FREQ=WEEKLY;BYDAY={byday}"
        if "毎月1日" in text:
            return "FREQ=MONTHLY;BYMONTHDAY=1"
        return None

    def _extract_explicit_date(self, text: str, now: datetime, ambiguity_flags: list[str]):
        import re

        m = re.search(r"(?:(\d{4})/)?(\d{1,2})/(\d{1,2})", text)
        if m:
            year = int(m.group(1) or now.year)
            month = int(m.group(2))
            day = int(m.group(3))
            return datetime(year, month, day).date()

        m = re.search(r"(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日", text)
        if m:
            year = int(m.group(1) or now.year)
            month = int(m.group(2))
            day = int(m.group(3))
            return datetime(year, month, day).date()

        m = re.search(r"(今週|来週|再来週)([月火水木金土日])曜", text)
        if m:
            base_word, weekday_jp = m.groups()
            weeks = {"今週": 0, "来週": 1, "再来週": 2}[base_word]
            start = now.date() - timedelta(days=now.weekday()) + timedelta(weeks=weeks)
            return start + timedelta(days=WEEKDAY_MAP[weekday_jp])

        if "毎週" not in text and re.search(r"([月火水木金土日])曜", text):
            ambiguity_flags.append("weekday_needs_week_scope")

        if "今月末" in text:
            next_month = datetime(now.year + (1 if now.month == 12 else 0), 1 if now.month == 12 else now.month + 1, 1)
            return (next_month - timedelta(days=1)).date()

        m = re.search(r"来月(\d{1,2})日", text)
        if m:
            month = 1 if now.month == 12 else now.month + 1
            year = now.year + (1 if now.month == 12 else 0)
            return datetime(year, month, int(m.group(1))).date()

        if "来週" in text and all(marker not in text for marker in WEEKDAY_MAP):
            ambiguity_flags.append("missing_weekday")

        return None

    def _extract_time(self, text: str, ambiguity_flags: list[str]):
        import re

        if "正午" in text:
            return 12, 0
        for label, hour in TIME_WORDS.items():
            if label in text and label != "正午":
                m = re.search(label + r"\s*(\d{1,2})時", text)
                if m:
                    return hour if label in ["朝", "昼", "夕方"] else int(m.group(1)), 0
                ambiguity_flags.append(f"time_word:{label}")
                return hour, 0

        m = re.search(r"(午前|午後)\s*(\d{1,2})時(?:([0-5]?\d)分|半)?", text)
        if m:
            meridiem, hour, minute = m.groups()
            hour = int(hour)
            if meridiem == "午後" and hour < 12:
                hour += 12
            if meridiem == "午前" and hour == 12:
                hour = 0
            return hour, 30 if minute == "半" else int(minute[:-1]) if minute else 0

        m = re.search(r"(\d{1,2}):(\d{2})", text)
        if m:
            return int(m.group(1)), int(m.group(2))

        matches = list(re.finditer(r"(\d{1,2})時(半|([0-5]?\d)分)?", text))
        if matches:
            m = matches[-1]
            hour = int(m.group(1))
            minute = 30 if m.group(2) == "半" else int(m.group(3)) if m.group(3) else 0
            if hour <= 11 and ("午後" not in text and "午前" not in text) and "weekday_needs_week_scope" in ambiguity_flags:
                ambiguity_flags.append("hour_needs_meridiem")
            return hour, minute

        m = re.search(r"(\d{1,2})\s*pm", text, re.IGNORECASE)
        if m:
            return int(m.group(1)) + 12, 0

        return None, None

    def _extract_title(self, text: str) -> str:
        import re

        cleaned = text
        patterns = [
            r"<@[^>]+>",
            r"\d{4}/\d{1,2}/\d{1,2}",
            r"\d{1,2}/\d{1,2}",
            r"\d{1,2}月\d{1,2}日",
            r"(今日|明日|明後日|今週|来週|再来週|今月末|来月\d{1,2}日)",
            r"([月火水木金土日])曜",
            r"(午前|午後)?\s*\d{1,2}(?::\d{2})?時?(?:\d{1,2}分|半)?",
            r"\d{1,2}:\d{2}",
            r"毎日|平日|毎週[月火水木金土日]曜|毎月1日",
            r"に|を|の|から|まで",
            r"教えて|見せて|完了|終わった|消して|変更|して|変えて|取り消し|ある？|一覧|表示",
        ]
        for pattern in patterns:
            cleaned = re.sub(pattern, " ", cleaned)
        return self.clean_title(cleaned)

    @staticmethod
    def _determine_status(parsed: ParsedDateTime, ambiguity_flags: list[str]) -> str:
        if any(flag in ambiguity_flags for flag in ["weekday_needs_week_scope", "hour_needs_meridiem"]):
            return "needs_confirmation"
        if not parsed.due_date and not parsed.start_datetime:
            return "on_hold"
        return "confirmed"

