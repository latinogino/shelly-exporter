"""One-shot metrics collection test for a Shelly device.

This script uses the exporter client to fetch data from the Shelly API and then
runs a ShellyCollector scrape cycle to ensure metrics can be produced.
"""

import argparse
import sys

from prometheus_client.core import CollectorRegistry

from shelly_exporter import ShellyCollector, ShellyPro3EMClient, _build_logger


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect metrics from a Shelly device once and print them")
    parser.add_argument("--host", required=True, help="Shelly IP or hostname")
    parser.add_argument("--protocol", default="http", choices=["http", "https"], help="Protocol to use")
    parser.add_argument("--port", type=int, default=None, help="Optional port override for the Shelly device")
    parser.add_argument("--timeout", type=int, default=5, help="Request timeout in seconds")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging output")
    args = parser.parse_args()

    logger = _build_logger(args.verbose)
    client = ShellyPro3EMClient(
        host=args.host,
        protocol=args.protocol,
        port=args.port,
        timeout=args.timeout,
        logger=logger,
    )

    registry = CollectorRegistry()
    collector = ShellyCollector(client, logger)
    registry.register(collector)

    metrics = list(collector.collect())
    print("Collected metric families:\n")
    for family in metrics:
        print(f"- {family.name} ({len(family.samples)} samples)")

    if not metrics:
        print("\nNo metrics were emitted; verify the Shelly API response includes energy meter data.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
