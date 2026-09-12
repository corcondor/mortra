"""Optional factual research events, separate from ordinary process output."""

from datetime import datetime, timezone
from contextlib import contextmanager
import json
import os
from pathlib import Path
import threading
import time


PREFIX = "MORTRA_EVENT "
SCHEMA = "mortra.research-event.v1"
_LOCK = threading.Lock()


@contextmanager
def measured(component, stage, **data):
    """Observe work without putting nondeterministic timings in certificates."""
    start = time.perf_counter()
    emit(component, "stage_started", stage=stage, **data)
    try:
        yield
    except Exception as exc:
        emit(component, "stage_finished", stage=stage, status="error",
             seconds=time.perf_counter()-start, error_type=type(exc).__name__, **data)
        raise
    else:
        emit(component, "stage_finished", stage=stage, status="completed",
             seconds=time.perf_counter()-start, **data)


def emit(component, event, *, _payload_directory=None, **data):
    if os.environ.get("MORTRA_LIVE_EVENTS") != "1":
        return
    if _payload_directory is not None:
        from math_os_prototype.shared_json import pack, canonical, scalar
        payload = pack(data)
        encoded = canonical(payload)
        if len(encoded) > 8192:
            directory = Path(_payload_directory)
            directory.mkdir(parents=True, exist_ok=True)
            path = directory/(payload["sha256"]+".json")
            if not path.exists():
                path.write_text(encoded+"\n", encoding="utf-8")
            data = {**{k: v for k, v in data.items() if scalar(v)},
                    "shared_payload": {"path": str(path.resolve()), "sha256": payload["sha256"],
                                       "encoding": payload["schema"]}}
    line = PREFIX + json.dumps({
        "schema": SCHEMA, "component": component, "event": event,
        "pid": os.getpid(),
        "emitted_utc": datetime.now(timezone.utc).isoformat(), "data": data,
    }, ensure_ascii=False, allow_nan=False)
    sink = os.environ.get("MORTRA_EVENT_SINK")
    if sink:
        # Each process has its own append stream, including buffered workers.
        with _LOCK, (Path(sink) / f"{os.getpid()}.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")
            stream.flush()
    else:
        print(line, flush=True)


def decode(line):
    if not line.startswith(PREFIX):
        return None
    try:
        value = json.loads(line[len(PREFIX):])
    except (ValueError, TypeError):
        return None
    if (not isinstance(value, dict) or value.get("schema") != SCHEMA
            or not isinstance(value.get("component"), str)
            or not isinstance(value.get("event"), str)
            or not isinstance(value.get("data"), dict)):
        return None
    return value
