"""TAE age tracking — birthday 2026-06-25."""

from __future__ import annotations

from datetime import datetime, timezone

TAE_BIRTHDAY = datetime(2026, 6, 25, 0, 0, 0, tzinfo=timezone.utc)


class TAEAge:
    """Computes TAE age from fixed birthday."""

    def __init__(self, birthday: datetime = TAE_BIRTHDAY) -> None:
        self._birthday = birthday

    def birthday(self) -> datetime:
        return self._birthday

    def birthday_string(self) -> str:
        return self._birthday.strftime("%Y-%m-%d")

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def current_age_days(self) -> int:
        delta = self._now() - self._birthday
        return max(0, delta.days)

    def current_age_hours(self) -> int:
        delta = self._now() - self._birthday
        total_hours = int(delta.total_seconds() // 3600)
        remainder_hours = total_hours - (self.current_age_days() * 24)
        return max(0, remainder_hours)

    def days_alive(self) -> int:
        return self.current_age_days()

    def age_string(self) -> str:
        days = self.current_age_days()
        hours = self.current_age_hours()
        return f"{days} Days\n{hours} Hours"

    def age_one_line(self) -> str:
        return f"{self.current_age_days()} Days, {self.current_age_hours()} Hours"
