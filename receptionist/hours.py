from datetime import datetime
from zoneinfo import ZoneInfo

from receptionist.config import Settings


def is_business_open(settings: Settings, now: datetime | None = None) -> bool:
    local_now = (now or datetime.now(tz=ZoneInfo(settings.business_timezone))).astimezone(
        ZoneInfo(settings.business_timezone)
    )
    return (
        local_now.weekday() in settings.business_weekdays
        and settings.business_opens
        <= local_now.time().replace(tzinfo=None)
        < settings.business_closes
    )
