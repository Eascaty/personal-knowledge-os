"""Focused health and release checks."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union
from urllib.parse import unquote, urlsplit

from .model import CheckResult, CheckStatus, _duration_ms, _label, _path_within

def offline_network_check() -> CheckResult:
    """Record the intentional absence of online health checks."""

    return CheckResult(
        "online",
        CheckStatus.SKIP,
        "默认离线：未执行网络请求或线上健康检查",
        metrics={"network_requests": 0},
    )
