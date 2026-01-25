import json
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from helpers import SUMMARIES_ROOT


def _coerce_json_value(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_coerce_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _coerce_json_value(val) for key, val in value.items()}
    return value


def get_timings_log_path() -> Path:
    return SUMMARIES_ROOT / "timings.log"


def log_timing(label: str, start_time: float, end_time: float, **context) -> None:
    duration = end_time - start_time
    payload = {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "label": label,
        "duration_s": round(duration, 6),
    }
    if context:
        payload.update(_coerce_json_value(context))

    log_path = get_timings_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(payload, ensure_ascii=False) + "\n")


@contextmanager
def timing_step(label: str, **context):
    start = time.perf_counter()
    try:
        yield
    finally:
        end = time.perf_counter()
        log_timing(label, start, end, **context)
