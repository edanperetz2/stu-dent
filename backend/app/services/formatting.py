from datetime import datetime
from zoneinfo import ZoneInfo

# The app is built for Israel-based users only (see CLAUDE.md); notification/
# message text is generated server-side and read directly (unlike API
# timestamps, which the frontend formats itself via dayjs), so it must
# already be in the same dd/mm/yy HH:mm, local-time form the frontend
# shows elsewhere -- not the stored UTC value.
DISPLAY_TIMEZONE = ZoneInfo("Asia/Jerusalem")


def format_dt(dt: datetime) -> str:
    return dt.astimezone(DISPLAY_TIMEZONE).strftime("%d/%m/%y %H:%M")
