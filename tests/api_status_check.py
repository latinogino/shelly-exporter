"""Connectivity check against a Shelly device.

This script issues requests to the legacy `/status` endpoint and the modern
`/rpc/EM.GetStatus` endpoint and reports the HTTP status code and whether JSON
was returned. It is intentionally lightweight and does not require
authentication.
"""

import argparse
import json
import sys
from typing import Dict, Optional

import requests


def _build_url(host: str, protocol: str, port: Optional[int], path: str) -> str:
    base = f"{protocol}://{host}"
    if port:
        base = f"{base}:{port}"
    return f"{base}{path}"


def check_endpoint(url: str, timeout: int) -> Dict[str, str]:
    result: Dict[str, str] = {"url": url}
    try:
        response = requests.get(url, timeout=timeout)
        result["status_code"] = str(response.status_code)
        try:
            parsed = response.json()
            result["json_keys"] = ", ".join(sorted(parsed.keys())) if isinstance(parsed, dict) else "(non-dict JSON)"
        except ValueError:
            result["json_keys"] = "(no JSON body)"
    except Exception as exc:  # pylint: disable=broad-except
        result["error"] = str(exc)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test Shelly HTTP endpoints")
    parser.add_argument("--host", required=True, help="Shelly IP or hostname")
    parser.add_argument("--protocol", default="http", choices=["http", "https"], help="Protocol to use")
    parser.add_argument("--port", type=int, default=None, help="Optional port override for the Shelly device")
    parser.add_argument("--timeout", type=int, default=5, help="Request timeout in seconds")
    args = parser.parse_args()

    endpoints = ["/status", "/rpc/EM.GetStatus"]
    results = []
    for path in endpoints:
        url = _build_url(args.host, args.protocol, args.port, path)
        results.append(check_endpoint(url, args.timeout))

    print("Shelly endpoint check results:\n")
    for result in results:
        print(json.dumps(result, indent=2))

    failures = [r for r in results if "error" in r]
    if len(failures) == len(results):
        print("\nBoth Shelly endpoints failed; verify the device is reachable and supports these APIs.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
