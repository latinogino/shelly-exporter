import argparse
import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests
from prometheus_client import start_http_server
from prometheus_client.core import CollectorRegistry, GaugeMetricFamily


def _build_logger(verbose: bool) -> logging.Logger:
    logger = logging.getLogger("shelly_exporter")
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    if not logger.handlers:
        logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    return logger


@dataclass
class PhaseReading:
    phase: str
    power_w: Optional[float] = None
    voltage_v: Optional[float] = None
    current_a: Optional[float] = None
    energy_wh: Optional[float] = None
    returned_energy_wh: Optional[float] = None


@dataclass
class ShellyStatus:
    phases: List[PhaseReading]
    total_power_w: Optional[float] = None


class ShellyPro3EMClient:
    def __init__(
        self,
        host: str,
        protocol: str = "http",
        port: Optional[int] = None,
        timeout: int = 5,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.base = f"{protocol}://{host}"
        if port:
            self.base = f"{self.base}:{port}"
        self.timeout = timeout
        self.logger = logger or logging.getLogger("shelly_exporter")

    def fetch_status(self) -> ShellyStatus:
        try:
            data = self._request_json("/status")
            parsed = self._parse_legacy_status(data)
            if parsed:
                return parsed
            self.logger.debug("/status endpoint returned no EM data, trying RPC API")
        except Exception as exc:  # pylint: disable=broad-except
            self.logger.debug("Legacy /status endpoint unavailable: %s", exc)

        data = self._request_json("/rpc/EM.GetStatus")
        parsed = self._parse_rpc_status(data)
        if parsed:
            return parsed
        raise RuntimeError("Unable to parse Shelly response for EM data")

    def _request_json(self, path: str) -> Dict:
        url = f"{self.base}{path}"
        self.logger.debug("Requesting %s", url)
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _parse_legacy_status(data: Dict) -> Optional[ShellyStatus]:
        emeters = data.get("emeters")
        if not isinstance(emeters, list) or not emeters:
            return None

        phases: List[PhaseReading] = []
        total_power = 0.0
        has_power = False
        for idx, meter in enumerate(emeters, start=1):
            power = meter.get("power")
            if isinstance(power, (int, float)):
                total_power += power
                has_power = True
            phases.append(
                PhaseReading(
                    phase=str(idx),
                    power_w=power if isinstance(power, (int, float)) else None,
                    voltage_v=meter.get("voltage"),
                    current_a=meter.get("current"),
                    energy_wh=meter.get("total"),
                    returned_energy_wh=meter.get("total_returned"),
                )
            )

        return ShellyStatus(phases=phases, total_power_w=total_power if has_power else None)

    @staticmethod
    def _parse_rpc_status(data: Dict) -> Optional[ShellyStatus]:
        phases: List[PhaseReading] = []
        phase_prefixes = ["a", "b", "c"]
        metrics = {
            "act_power": "power_w",
            "power": "power_w",
            "voltage": "voltage_v",
            "current": "current_a",
            "act_energy": "energy_wh",
            "act_ret_energy": "returned_energy_wh",
        }

        found_metric = False
        for prefix in phase_prefixes:
            kwargs: Dict[str, Optional[float]] = {"phase": prefix.upper()}
            for key_suffix, attr in metrics.items():
                value = data.get(f"{prefix}_{key_suffix}")
                if isinstance(value, (int, float)):
                    kwargs[attr] = value
                    found_metric = True
            phases.append(PhaseReading(**kwargs))

        if not found_metric:
            return None

        total_power = data.get("total_act_power") or data.get("total_power")
        if not isinstance(total_power, (int, float)):
            total_power = None

        return ShellyStatus(phases=phases, total_power_w=total_power)


class ShellyCollector:
    def __init__(self, client: ShellyPro3EMClient, logger: logging.Logger) -> None:
        self.client = client
        self.logger = logger

    def collect(self):
        up_metric = GaugeMetricFamily("shelly_up", "Shelly device reachable", labels=[])
        try:
            status = self.client.fetch_status()
            up_metric.add_metric([], 1)
            yield up_metric
            yield from self._emit_status(status)
        except Exception as exc:  # pylint: disable=broad-except
            self.logger.error("Failed to scrape Shelly: %s", exc)
            up_metric.add_metric([], 0)
            yield up_metric

    def _emit_status(self, status: ShellyStatus):
        total_power = GaugeMetricFamily(
            "shelly_total_power_watts", "Total active power across all phases", labels=[]
        )
        if status.total_power_w is not None:
            total_power.add_metric([], status.total_power_w)
            yield total_power

        phase_power = GaugeMetricFamily(
            "shelly_phase_power_watts", "Phase active power", labels=["phase"]
        )
        phase_voltage = GaugeMetricFamily(
            "shelly_phase_voltage_volts", "Phase voltage", labels=["phase"]
        )
        phase_current = GaugeMetricFamily(
            "shelly_phase_current_amperes", "Phase current", labels=["phase"]
        )
        phase_energy = GaugeMetricFamily(
            "shelly_phase_energy_wh", "Total delivered energy", labels=["phase"]
        )
        phase_returned = GaugeMetricFamily(
            "shelly_phase_returned_energy_wh", "Total returned energy", labels=["phase"]
        )

        for reading in status.phases:
            if reading.power_w is not None:
                phase_power.add_metric([reading.phase], reading.power_w)
            if reading.voltage_v is not None:
                phase_voltage.add_metric([reading.phase], reading.voltage_v)
            if reading.current_a is not None:
                phase_current.add_metric([reading.phase], reading.current_a)
            if reading.energy_wh is not None:
                phase_energy.add_metric([reading.phase], reading.energy_wh)
            if reading.returned_energy_wh is not None:
                phase_returned.add_metric([reading.phase], reading.returned_energy_wh)

        yield phase_power
        yield phase_voltage
        yield phase_current
        yield phase_energy
        yield phase_returned


def parse_args() -> argparse.Namespace:
    def _optional_env_int(var_name: str) -> Optional[int]:
        value = os.environ.get(var_name)
        if value is None or value == "":
            return None
        try:
            return int(value)
        except ValueError as exc:  # pragma: no cover - validated via argparse when provided
            raise argparse.ArgumentTypeError(
                f"Environment variable {var_name} must be an integer"
            ) from exc

    parser = argparse.ArgumentParser(description="Prometheus exporter for Shelly Pro 3EM")
    parser.add_argument(
        "--host",
        default=os.environ.get("SHELLY_HOST"),
        help="Shelly host or IP address (can also be set via SHELLY_HOST)",
    )
    parser.add_argument(
        "--protocol",
        default=os.environ.get("SHELLY_PROTOCOL", "http"),
        choices=["http", "https"],
        help="Protocol to use when contacting the Shelly device",
    )
    parser.add_argument(
        "--shelly-port",
        type=int,
        default=_optional_env_int("SHELLY_PORT"),
        help="Optional port for the Shelly device",
    )
    parser.add_argument(
        "--listen-address",
        default=os.environ.get("LISTEN_ADDRESS", "0.0.0.0"),
        help="Address for the exporter to bind to",
    )
    parser.add_argument(
        "--listen-port",
        type=int,
        default=int(os.environ.get("LISTEN_PORT", "8000")),
        help="Port for the exporter to listen on",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=int(os.environ.get("SHELLY_TIMEOUT", "5")),
        help="Timeout in seconds for Shelly API requests",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    logger = _build_logger(args.verbose)

    if not args.host:
        raise SystemExit("--host or SHELLY_HOST environment variable is required")

    client = ShellyPro3EMClient(
        host=args.host,
        protocol=args.protocol,
        port=args.shelly_port,
        timeout=args.timeout,
        logger=logger,
    )

    registry = CollectorRegistry()
    registry.register(ShellyCollector(client, logger))

    logger.info("Starting Shelly exporter on %s:%s", args.listen_address, args.listen_port)
    start_http_server(args.listen_port, addr=args.listen_address, registry=registry)

    try:
        import time

        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        logger.info("Exporter interrupted, shutting down")


if __name__ == "__main__":
    main()
