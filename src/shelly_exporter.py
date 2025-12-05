import argparse
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests
from requests import HTTPError
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
    apparent_power_va: Optional[float] = None
    reactive_power_var: Optional[float] = None
    power_factor: Optional[float] = None
    extra_metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class ShellyStatus:
    phases: List[PhaseReading]
    total_power_w: Optional[float] = None
    total_apparent_power_va: Optional[float] = None
    total_reactive_power_var: Optional[float] = None
    total_energy_wh: Optional[float] = None
    total_returned_energy_wh: Optional[float] = None
    frequency_hz: Optional[float] = None
    misc_metrics: Dict[str, float] = field(default_factory=dict)


class ShellyPro3EMClient:
    def __init__(
        self,
        host: str,
        protocol: str = "http",
        port: Optional[int] = None,
        timeout: int = 5,
        username: Optional[str] = None,
        password: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.base = f"{protocol}://{host}"
        if port:
            self.base = f"{self.base}:{port}"
        self.timeout = timeout
        self.auth = (username, password) if username and password else None
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

        try:
            data = self._request_json("/rpc/EM.GetStatus", params={"id": 0})
        except HTTPError as exc:
            self.logger.debug("EM.GetStatus with id=0 failed: %s", exc)
            data = self._request_json("/rpc/EM.GetStatus")
        parsed = self._parse_rpc_status(data)
        if parsed:
            return parsed
        raise RuntimeError("Unable to parse Shelly response for EM data")

    def _request_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict:
        url = f"{self.base}{path}"
        self.logger.debug("Requesting %s", url)
        response = requests.get(url, timeout=self.timeout, auth=self.auth, params=params)
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
            "apparent_power": "apparent_power_va",
            "reactive_power": "reactive_power_var",
            "pf": "power_factor",
        }

        found_metric = False
        for prefix in phase_prefixes:
            kwargs: Dict[str, Optional[float]] = {"phase": prefix.upper(), "extra_metrics": {}}
            for key_suffix, attr in metrics.items():
                value = data.get(f"{prefix}_{key_suffix}")
                if isinstance(value, (int, float)):
                    kwargs[attr] = value
                    found_metric = True
            for key, value in data.items():
                if not key.startswith(f"{prefix}_"):
                    continue
                suffix = key[len(prefix) + 1 :]
                if suffix not in metrics and isinstance(value, (int, float)):
                    kwargs["extra_metrics"][suffix] = value
            phases.append(PhaseReading(**kwargs))

        if not found_metric:
            return None

        total_power = data.get("total_act_power") or data.get("total_power")
        total_apparent_power = data.get("total_apparent_power")
        total_reactive_power = data.get("total_reactive_power")
        total_energy = data.get("total_act_energy")
        total_returned_energy = data.get("total_act_ret_energy")
        frequency = data.get("freq") or data.get("frequency")

        misc_metrics: Dict[str, float] = {}
        for key, value in data.items():
            if not isinstance(value, (int, float)):
                continue
            if key.startswith(tuple(f"{prefix}_" for prefix in phase_prefixes)):
                continue
            if key.startswith("total_") and key in {
                "total_act_power",
                "total_power",
                "total_apparent_power",
                "total_reactive_power",
                "total_act_energy",
                "total_act_ret_energy",
            }:
                continue
            if key in {"freq", "frequency"}:
                continue
            misc_metrics[key] = value

        if not isinstance(total_power, (int, float)):
            total_power = None
        if not isinstance(total_apparent_power, (int, float)):
            total_apparent_power = None
        if not isinstance(total_reactive_power, (int, float)):
            total_reactive_power = None
        if not isinstance(total_energy, (int, float)):
            total_energy = None
        if not isinstance(total_returned_energy, (int, float)):
            total_returned_energy = None
        if not isinstance(frequency, (int, float)):
            frequency = None

        return ShellyStatus(
            phases=phases,
            total_power_w=total_power,
            total_apparent_power_va=total_apparent_power,
            total_reactive_power_var=total_reactive_power,
            total_energy_wh=total_energy,
            total_returned_energy_wh=total_returned_energy,
            frequency_hz=frequency,
            misc_metrics=misc_metrics,
        )


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

        total_apparent_power = GaugeMetricFamily(
            "shelly_total_apparent_power_va",
            "Total apparent power across all phases",
            labels=[],
        )
        if status.total_apparent_power_va is not None:
            total_apparent_power.add_metric([], status.total_apparent_power_va)
            yield total_apparent_power

        total_reactive_power = GaugeMetricFamily(
            "shelly_total_reactive_power_var",
            "Total reactive power across all phases",
            labels=[],
        )
        if status.total_reactive_power_var is not None:
            total_reactive_power.add_metric([], status.total_reactive_power_var)
            yield total_reactive_power

        total_energy = GaugeMetricFamily(
            "shelly_total_energy_wh",
            "Total delivered energy across all phases",
            labels=[],
        )
        if status.total_energy_wh is not None:
            total_energy.add_metric([], status.total_energy_wh)
            yield total_energy

        total_returned_energy = GaugeMetricFamily(
            "shelly_total_returned_energy_wh",
            "Total returned energy across all phases",
            labels=[],
        )
        if status.total_returned_energy_wh is not None:
            total_returned_energy.add_metric([], status.total_returned_energy_wh)
            yield total_returned_energy

        frequency = GaugeMetricFamily(
            "shelly_frequency_hz", "Measured grid frequency", labels=[]
        )
        if status.frequency_hz is not None:
            frequency.add_metric([], status.frequency_hz)
            yield frequency

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
        phase_apparent_power = GaugeMetricFamily(
            "shelly_phase_apparent_power_va", "Phase apparent power", labels=["phase"]
        )
        phase_reactive_power = GaugeMetricFamily(
            "shelly_phase_reactive_power_var", "Phase reactive power", labels=["phase"]
        )
        phase_pf = GaugeMetricFamily(
            "shelly_phase_power_factor", "Phase power factor", labels=["phase"]
        )

        dynamic_phase_metrics: Dict[str, GaugeMetricFamily] = {}

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
            if reading.apparent_power_va is not None:
                phase_apparent_power.add_metric([reading.phase], reading.apparent_power_va)
            if reading.reactive_power_var is not None:
                phase_reactive_power.add_metric([reading.phase], reading.reactive_power_var)
            if reading.power_factor is not None:
                phase_pf.add_metric([reading.phase], reading.power_factor)
            for key, value in reading.extra_metrics.items():
                metric_name = f"shelly_phase_{key}"
                if metric_name not in dynamic_phase_metrics:
                    dynamic_phase_metrics[metric_name] = GaugeMetricFamily(
                        metric_name,
                        f"Phase metric reported by Shelly ({key})",
                        labels=["phase"],
                    )
                dynamic_phase_metrics[metric_name].add_metric([reading.phase], value)

        yield phase_power
        yield phase_voltage
        yield phase_current
        yield phase_energy
        yield phase_returned
        yield phase_apparent_power
        yield phase_reactive_power
        yield phase_pf
        yield from dynamic_phase_metrics.values()

        for key, value in status.misc_metrics.items():
            metric_name = f"shelly_{key}"
            gauge = GaugeMetricFamily(
                metric_name, f"Metric reported by Shelly ({key})", labels=[],
            )
            gauge.add_metric([], value)
            yield gauge


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
        "--username",
        default=os.environ.get("SHELLY_USERNAME"),
        help="Optional username for Shelly HTTP Basic Auth (SHELLY_USERNAME)",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("SHELLY_PASSWORD"),
        help="Optional password for Shelly HTTP Basic Auth (SHELLY_PASSWORD)",
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
        username=args.username,
        password=args.password,
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
