"""Uvicorn JSON formatter: no URL, message, exception, or credentials emitted."""
import datetime
import json
import logging

class SafeJSONFormatter(logging.Formatter):
    def format(self, record):
        event = {"time": datetime.datetime.now(datetime.timezone.utc).isoformat(), "level": record.levelname, "logger": record.name, "event": "http_access" if record.name == "uvicorn.access" else "server_event"}
        if record.name == "uvicorn.access" and isinstance(record.args, tuple) and len(record.args) == 5:
            _, method, _, _, status = record.args
            event.update(method=method, status=status)
        if record.exc_info:
            event["exception_type"] = record.exc_info[0].__name__
        return json.dumps(event, separators=(",", ":"))
