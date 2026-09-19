"""Game time: minutes since the world began, shown with the calendar from data/calendar.json."""

from __future__ import annotations

from dataclasses import dataclass

MINUTES_PER_HOUR = 60
HOURS_PER_DAY = 24
MINUTES_PER_DAY = MINUTES_PER_HOUR * HOURS_PER_DAY


@dataclass(frozen=True)
class Month:
    name: str
    season: str
    daylight: float
    temp_offset: float


class Calendar:
    def __init__(self, data: dict) -> None:
        self.era = data["era"]
        self.start_year = int(data["start_year"])
        self.days_per_month = int(data["days_per_month"])
        self.weekdays = list(data["weekdays"])
        self.months = [Month(m["name"], m["season"], float(m["daylight"]), float(m["temp_offset"])) for m in data["months"]]
        self.days_per_year = self.days_per_month * len(self.months)

    def at(self, minutes: int) -> Moment:
        return Moment(self, int(minutes))

    def minutes_for(self, year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> int:
        """Minutes since the epoch for a date. month and day are 1-based."""
        days = (year - self.start_year) * self.days_per_year + (month - 1) * self.days_per_month + (day - 1)
        return days * MINUTES_PER_DAY + hour * MINUTES_PER_HOUR + minute


class Moment:
    """A point in time, with everything the UI and simulation want to know about it."""

    def __init__(self, calendar: Calendar, minutes: int) -> None:
        self.cal = calendar
        self.minutes = minutes
        self.total_days, rem = divmod(minutes, MINUTES_PER_DAY)
        self.hour, self.minute = divmod(rem, MINUTES_PER_HOUR)
        years, day_of_year = divmod(self.total_days, calendar.days_per_year)
        self.year = calendar.start_year + years
        self.day_of_year = day_of_year
        month_index, day_index = divmod(day_of_year, calendar.days_per_month)
        self.month_index = month_index
        self.month = calendar.months[month_index]
        self.day = day_index + 1
        self.weekday = calendar.weekdays[self.total_days % len(calendar.weekdays)]

    @property
    def season(self) -> str:
        return self.month.season

    @property
    def fractional_hour(self) -> float:
        return self.hour + self.minute / 60.0

    def daylight_hours(self, latitude: float = 0.5) -> float:
        """Hours of daylight. latitude 0 = far north (extreme), 1 = far south (mild swing)."""
        base = self.month.daylight
        swing = (base - 12.0) * (1.4 - 0.8 * latitude)
        return max(4.0, min(20.0, 12.0 + swing))

    def sun_times(self, latitude: float = 0.5) -> tuple[float, float]:
        half = self.daylight_hours(latitude) / 2.0
        return 12.0 - half, 12.0 + half

    def light(self, latitude: float = 0.5) -> float:
        """Outdoor light: 1.0 full day, about 0.12 at night, with an hour of twilight either side."""
        sunrise, sunset = self.sun_times(latitude)
        h = self.fractional_hour
        night = 0.12
        if sunrise + 0.5 <= h <= sunset - 0.5:
            return 1.0
        if h < sunrise - 0.5 or h > sunset + 0.5:
            return night
        if h < sunrise + 0.5:
            t = (h - (sunrise - 0.5))
        else:
            t = ((sunset + 0.5) - h)
        return night + (1.0 - night) * max(0.0, min(1.0, t))

    def part_of_day(self, latitude: float = 0.5) -> str:
        sunrise, sunset = self.sun_times(latitude)
        h = self.fractional_hour
        if h < sunrise - 1.5:
            return "night"
        if h < sunrise - 0.5:
            return "before dawn"
        if h < sunrise + 0.5:
            return "dawn"
        if h >= sunset + 0.5:
            return "night"
        if h >= sunset - 0.5:
            return "dusk"
        if h < 11:
            return "morning"
        if h < 13:
            return "midday"
        if h < 17:
            return "afternoon"
        return "evening"

    def is_dark(self, latitude: float = 0.5) -> bool:
        return self.light(latitude) < 0.5

    def date_text(self) -> str:
        return f"{self.weekday}, {self.day} {self.month.name}, {self.year}"

    def time_text(self) -> str:
        return f"{self.hour:02d}:{self.minute:02d}"

    def long_text(self) -> str:
        return f"{self.date_text()} {self.cal.era}"


def duration_text(minutes: float) -> str:
    """'2 days 5 hours', '3 hours 10 minutes', '40 minutes'."""
    minutes = int(round(minutes))
    days, rem = divmod(minutes, MINUTES_PER_DAY)
    hours, mins = divmod(rem, MINUTES_PER_HOUR)
    parts = []
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if mins and not days:
        parts.append(f"{mins} minute{'s' if mins != 1 else ''}")
    return " ".join(parts) or "no time at all"
