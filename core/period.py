"""core/period.py — 교시표 및 변환 함수
1교시 09:00~10:00, 2교시 10:00~11:00, ..., 15교시 23:00~00:00(다음날)
"""
from datetime import date, datetime, time, timedelta

# 1~14교시: 시작 = (8+N):00, 종료 = (9+N):00
# 15교시:   시작 = 23:00,    종료 = 자정 (00:00 다음날 → timedelta로 처리)
PERIOD_TABLE: dict[int, tuple[time, time | None]] = {
    **{n: (time(8 + n, 0), time(9 + n, 0)) for n in range(1, 15)},
    15: (time(23, 0), None),   # None = 자정(00:00 다음날)
}

PERIOD_LABELS: dict[int, str] = {
    k: f"{k}교시 ({v[0].strftime('%H:%M')}~{'00:00+1' if v[1] is None else v[1].strftime('%H:%M')})"
    for k, v in PERIOD_TABLE.items()
}


def period_start(d: date, period: int) -> datetime:
    return datetime.combine(d, PERIOD_TABLE[period][0])


def period_end(d: date, period: int) -> datetime:
    start_time, end_time = PERIOD_TABLE[period]
    if end_time is None:
        # 15교시 종료: 다음날 00:00
        return datetime.combine(d, time(0, 0)) + timedelta(days=1)
    return datetime.combine(d, end_time)


def periods_to_range(d: date, start_p: int, end_p: int) -> tuple[datetime, datetime]:
    if end_p < start_p:
        raise ValueError(f"종료 교시({end_p})는 시작 교시({start_p}) 이상이어야 합니다.")
    return period_start(d, start_p), period_end(d, end_p)


def combine_datetime(d: date, time_str: str) -> datetime:
    h, m = map(int, time_str.split(":"))
    return datetime(d.year, d.month, d.day, h, m)
