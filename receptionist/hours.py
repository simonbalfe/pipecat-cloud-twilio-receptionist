from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class BusinessHours:
    timezone: ZoneInfo
    weekdays: frozenset[int]
    opens: time
    closes: time

    def __post_init__(self) -> None:
        if not self.weekdays or not self.weekdays <= set(range(7)):
            raise ValueError("must contain weekday numbers from 0 (Monday) to 6 (Sunday)")
        if self.closes <= self.opens:
            raise ValueError("must be later than BUSINESS_OPENS")


def is_business_open(hours: BusinessHours, now: datetime | None = None) -> bool:
    local_now = (now or datetime.now(tz=hours.timezone)).astimezone(hours.timezone)
    return (
        local_now.weekday() in hours.weekdays
        and hours.opens <= local_now.time().replace(tzinfo=None) < hours.closes
    )
