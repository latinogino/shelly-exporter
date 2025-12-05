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

## Running with Docker (Linux)

The exporter is built to run well on Linux hosts. You can either build the image locally or pull one that you have already publ
ished to your registry.

1. Build the image (run from the repository root):

   ```bash
   docker build -t shelly-pro-3em-exporter .
   ```

2. Start the container, passing your Shelly device address via environment variables:

   ```bash
   docker run -d \
     --name shelly-exporter \
     -e SHELLY_HOST=192.0.2.10 \
     -e LISTEN_PORT=8000 \
     -p 8000:8000 \
     --restart unless-stopped \
     shelly-pro-3em-exporter
   ```

3. Confirm that the exporter is responding:

   ```bash
   curl http://localhost:8000/metrics
   ```

The same commands work for a pre-built image (replace `shelly-pro-3em-exporter` with the published tag you want to pull).

## Local execution

You can also run the exporter without Docker (from the repository root):

```bash
pip install -r requirements.txt
PYTHONPATH=src python -m shelly_exporter --host 192.0.2.10 --listen-port 8000
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
