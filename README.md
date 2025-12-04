# Shelly Pro 3EM Prometheus Exporter

A lightweight Prometheus exporter that scrapes metrics directly from a Shelly Pro 3EM (latest firmware) and exposes them on `/metrics` for collection. The exporter is packaged as a Docker image for easy deployment.

## Features

- Supports both legacy `/status` and modern `/rpc/EM.GetStatus` Shelly APIs (no credentials required).
- Exposes per-phase power, voltage, current, energy, and returned energy metrics.
- Provides a `shelly_up` gauge to indicate device availability.

## Configuration

The exporter can be configured via command-line flags or environment variables. Environment variables are convenient when running the Docker image.

| Flag | Environment variable | Default | Description |
| --- | --- | --- | --- |
| `--host` | `SHELLY_HOST` | _required_ | Shelly device IP or hostname. |
| `--protocol` | `SHELLY_PROTOCOL` | `http` | Protocol for connecting to the Shelly. |
| `--shelly-port` | `SHELLY_PORT` | _empty_ | Optional Shelly port override. |
| `--listen-address` | `LISTEN_ADDRESS` | `0.0.0.0` | Address to bind the exporter. |
| `--listen-port` | `LISTEN_PORT` | `8000` | Port to expose Prometheus metrics. |
| `--timeout` | `SHELLY_TIMEOUT` | `5` | Shelly API request timeout (seconds). |
| `--verbose` | _n/a_ | off | Enable debug logging. |

## Running with Docker

Build the image locally and run it on Linux:

```bash
docker build -t shelly-pro-3em-exporter .
```

Run the container, providing your Shelly host/IP:

```bash
docker run -d \
  --name shelly-exporter \
  -e SHELLY_HOST=192.0.2.10 \
  -p 8000:8000 \
  shelly-pro-3em-exporter
```

Visit the metrics endpoint in your browser or Prometheus scrape configuration at:

```
http://localhost:8000/metrics
```

## Local execution

You can also run the exporter without Docker:

```bash
pip install -r requirements.txt
python exporter.py --host 192.0.2.10 --listen-port 8000
```

## Prometheus metric reference

- `shelly_up` – 1 when the exporter successfully scrapes the device, otherwise 0.
- `shelly_total_power_watts` – Sum of active power across all phases (if provided by the device).
- `shelly_phase_power_watts{phase="X"}` – Active power per phase.
- `shelly_phase_voltage_volts{phase="X"}` – Voltage per phase.
- `shelly_phase_current_amperes{phase="X"}` – Current per phase.
- `shelly_phase_energy_wh{phase="X"}` – Total delivered energy (watt-hours).
- `shelly_phase_returned_energy_wh{phase="X"}` – Total returned energy (watt-hours).

## Notes

- The exporter queries the legacy `/status` endpoint first for broad compatibility and falls back to `/rpc/EM.GetStatus` when needed.
- Shelly Pro 3EM devices do not require authentication for local status endpoints by default. If you enable authentication, provide the required credentials via network configuration (not currently supported by this exporter).
