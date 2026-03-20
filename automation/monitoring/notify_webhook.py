from __future__ import annotations

import json
import urllib.error
import urllib.request


def send_webhook_message(webhook_url: str, message: str, timeout_seconds: int = 10) -> bool:
    """Send a simple text webhook message (Discord-compatible).

    Returns True on success, False on failure.
    Failures are warning-only and should not crash callers.
    """
    payload = {"content": message[:1900]}
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            status = getattr(response, "status", 200)
            if 200 <= status < 300:
                return True
            print(f"[monitor] warning webhook_non_2xx status={status}")
            return False
    except urllib.error.HTTPError as exc:
        print(f"[monitor] warning webhook_http_error status={exc.code} reason={exc.reason}")
        return False
    except urllib.error.URLError as exc:
        print(f"[monitor] warning webhook_url_error reason={exc.reason}")
        return False
    except Exception as exc:
        print(f"[monitor] warning webhook_unexpected_error error={exc!r}")
        return False
