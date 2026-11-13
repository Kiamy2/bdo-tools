"""HTTP helper shared by all tools: JSON GET with retries and proxy-block detection."""
import json
import time
import urllib.error
import urllib.request


class NetworkBlocked(Exception):
    """The session's egress proxy refused the host (domain not in the allowed list)."""


def get_json(url, tries=5):
    """GET a JSON URL. Retries on network errors and on Arsha error payloads
    (e.g. status 500 'probably blocked by Imperva' - frequent and temporary),
    waiting 2/4/8/16 s between tries. Raises NetworkBlocked on a proxy refusal,
    RuntimeError with the last error otherwise."""
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "bdo-tools"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read().decode("utf-8"))
            if isinstance(data, dict) and "status" in data and "message" in data:
                last = f"API error {data.get('status')}: {data.get('message')}"
            else:
                return data
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}"
        except urllib.error.URLError as e:
            if "Tunnel connection failed: 403" in str(e.reason):
                raise NetworkBlocked(str(e.reason))
            last = f"URLError: {e.reason}"
        except Exception as e:  # JSON errors etc.
            last = f"{type(e).__name__}: {e}"
        if i < tries - 1:
            time.sleep(2 ** (i + 1))
    raise RuntimeError(last)


def blocked_message(host, err):
    return (f"NETWORK BLOCKED: this session cannot reach {host} ({err}). Ask the user to add "
            f"{host} to the allowed domains in claude.ai Settings > Capabilities (may only apply "
            "to new chats). Do not retry with other commands.")
