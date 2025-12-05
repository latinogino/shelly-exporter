# Shelly Pro 3EM Prometheus Exporter

## Overview
A lightweight Prometheus exporter that scrapes metrics directly from a Shelly Pro 3EM (latest firmware) and exposes them on `/metrics` for collection. The exporter supports both legacy and modern Shelly APIs and is packaged as a Docker image for straightforward deployment.

## Features
- Supports both legacy `/status` and modern `/rpc/EM.GetStatus` Shelly APIs (no credentials required). The exporter first calls `/rpc/EM.GetStatus?id=0` as recommended by current Shelly firmware documentation and falls back to the legacy call shape for older devices.
- Exposes per-phase power, voltage, current, energy, and returned energy metrics.
- Provides a `shelly_up` gauge to indicate device availability.

## Installation for Linux
1. Build the Docker image from the repository root:
   ```bash
   docker build -t shelly-exporter https://github.com/latinogino/shelly-exporter.git
   ```
2. Run the container, passing your Shelly device address via environment variables:
   ```bash
   docker run -d \
     --name shelly-exporter \
     -e SHELLY_HOST=192.0.2.10 \
     -e LISTEN_PORT=8000 \
     -p 8000:8000 \
     --restart unless-stopped \
     shelly-exporter
   ```
3. Confirm that the exporter is responding:
   ```bash
   curl http://localhost:8000/metrics
   ```

## Installation for Windows
Run the Docker image from PowerShell with equivalent environment variables:
```powershell
docker run -d --name shelly-exporter -e SHELLY_HOST=10.0.30.12 -e LISTEN_PORT=8000 -p 8000:8000 --restart unless-stopped shelly-exporter
```

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
| `--username` | `SHELLY_USERNAME` | _empty_ | Optional username for HTTP Basic Auth on the Shelly. |
| `--password` | `SHELLY_PASSWORD` | _empty_ | Optional password for HTTP Basic Auth on the Shelly. |
| `--verbose` | _n/a_ | off | Enable debug logging. |

## Usage
You can run the exporter locally or via Docker.

### Docker
```bash
docker run -d \
  --name shelly-exporter \
  -e SHELLY_HOST=192.0.2.10 \
  -e LISTEN_PORT=8000 \
  -p 8000:8000 \
  --restart unless-stopped \
  shelly-exporter
```

### Local execution
```bash
pip install -r requirements.txt
PYTHONPATH=src python src/shelly_exporter.py --host 192.0.2.10 --listen-port 8000
```

## Troubleshooting
- **Metrics endpoint empty or unavailable:** Ensure `SHELLY_HOST` points to a reachable Shelly Pro 3EM and that the device allows local API access.
- **Authentication errors:** If device authentication is enabled, provide `--username`/`--password` or the corresponding environment variables.
- **Network timeouts:** Increase `--timeout` or verify network connectivity between the exporter host and the Shelly device.
- **Docker port conflicts:** Adjust `LISTEN_PORT` and the published port if `8000` is already in use.

## Project Structure
- `src/shelly_exporter.py` – Entry point for the exporter.
- `src/` – Core exporter logic and helpers.
- `tests/` – Smoke test scripts for validating Shelly API responses and metric emission.
- `Dockerfile` – Container build definition.
- `requirements.txt` – Python dependencies for running the exporter and tests.

## API Documentation
- **Prometheus metrics**
  - `shelly_up` – 1 when the exporter successfully scrapes the device, otherwise 0.
  - `shelly_total_power_watts` – Sum of active power across all phases (if provided by the device).
  - `shelly_total_apparent_power_va` – Sum of apparent power across all phases.
  - `shelly_total_reactive_power_var` – Sum of reactive power across all phases.
  - `shelly_total_energy_wh` – Cumulative delivered energy across all phases.
  - `shelly_total_returned_energy_wh` – Cumulative returned energy across all phases.
  - `shelly_frequency_hz` – Reported grid frequency.
  - `shelly_phase_power_watts{phase="X"}` – Active power per phase.
  - `shelly_phase_voltage_volts{phase="X"}` – Voltage per phase.
  - `shelly_phase_current_amperes{phase="X"}` – Current per phase.
  - `shelly_phase_energy_wh{phase="X"}` – Total delivered energy (watt-hours).
  - `shelly_phase_returned_energy_wh{phase="X"}` – Total returned energy (watt-hours).
  - `shelly_phase_apparent_power_va{phase="X"}` – Apparent power per phase.
  - `shelly_phase_reactive_power_var{phase="X"}` – Reactive power per phase.
  - `shelly_phase_power_factor{phase="X"}` – Power factor per phase.
  - Additional per-phase and device-level numeric values exposed directly from the Shelly API using the `shelly_phase_*` and `shelly_*` prefixes.

## Resources to Read
- [Shelly Pro 3EM documentation](https://kb.shelly.cloud/knowledge-base/shelly-pro-3em) – Official device information and API references.
- [Prometheus exposition format](https://prometheus.io/docs/instrumenting/exposition_formats/) – Details on how metrics are structured.
- [Docker documentation](https://docs.docker.com/) – Guidance for building and running containers.

## Notes
- The exporter queries the legacy `/status` endpoint first for broad compatibility and falls back to `/rpc/EM.GetStatus` when needed.
- Shelly Pro 3EM devices do not require authentication for local status endpoints by default. If you enable authentication, supply credentials with `--username/--password` or `SHELLY_USERNAME/SHELLY_PASSWORD`.
