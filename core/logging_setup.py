from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict

from core.config import IS_DEV


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        doc: Dict[str, Any] = {
            "ts":     datetime.utcnow().isoformat() + "Z",
            "level":  record.levelname,
            "logger": record.name,
            "msg":    record.getMessage(),
        }
        if record.exc_info:
            doc["exc"] = self.formatException(record.exc_info)
        return json.dumps(doc, ensure_ascii=False)


def build_logger(name: str = "chimera") -> logging.Logger:
    handler: logging.Handler = logging.StreamHandler(sys.stdout)
    if IS_DEV:
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
    else:
        handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(handler)
    return logging.getLogger(name)


logger = build_logger()