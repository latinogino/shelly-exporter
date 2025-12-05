# Shelly Pro 3EM Prometheus Exporter

A lightweight Prometheus exporter that scrapes metrics directly from a Shelly Pro 3EM (latest firmware) and exposes them on `/metrics` for collection. The exporter is packaged as a Docker image for easy deployment.

## Features

- Supports both legacy `/status` and modern `/rpc/EM.GetStatus` Shelly APIs (no credentials required).
  The exporter first calls `/rpc/EM.GetStatus?id=0` as recommended by current Shelly
  firmware documentation and falls back to the legacy call shape for older devices.
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
| `--username` | `SHELLY_USERNAME` | _empty_ | Optional username for HTTP Basic Auth on the Shelly. |
| `--password` | `SHELLY_PASSWORD` | _empty_ | Optional password for HTTP Basic Auth on the Shelly. |
| `--verbose` | _n/a_ | off | Enable debug logging. |

## Running with Docker (Linux)

The exporter is built to run well on Linux hosts. You can either build the image locally or pull one that you have already publ
ished to your registry.

1. Build the image (run from the repository root):

   ```bash
   docker build -t shelly-exporter https://github.com/latinogino/shelly-exporter.git
   ```

2. Start the container, passing your Shelly device address via environment variables:

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

The same commands work for a pre-built image (replace `shelly-pro-3em-exporter` with the published tag you want to pull).

## Local execution

You can also run the exporter without Docker (from the repository root):

```bash
pip install -r requirements.txt
PYTHONPATH=src python src/shelly_exporter.py --host 192.0.2.10 --listen-port 8000
```

## Testing against a Shelly device

The repository includes simple smoke-test scripts that contact a Shelly device
directly (no authentication is required by default):

1. Clone the repository and install dependencies:

   ```bash
   git clone https://github.com/latinogino/shelly-exporter.git
   cd shelly-exporter
   pip install -r requirements.txt
   ```

2. Export `PYTHONPATH` so the tests can import the exporter code:

   ```bash
   export PYTHONPATH=src
   ```

3. Verify the Shelly HTTP APIs respond over the network:

   ```bash
   python tests/api_status_check.py --host 192.0.2.10
   ```

   The script queries both `/status` and `/rpc/EM.GetStatus` and reports the
   HTTP status code and any top-level JSON keys that were returned.

4. Run a one-shot metrics collection to confirm the exporter can produce
   Prometheus metrics:

   ```bash
   python tests/metrics_collection_check.py --host 192.0.2.10
   ```

   Add `--verbose` to see detailed logging of the scrape request. The script
   prints the metric families that were emitted; non-empty output indicates the
   exporter can parse the Shelly response successfully.

## Prometheus metric reference

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

## Notes

- The exporter queries the legacy `/status` endpoint first for broad compatibility and falls back to `/rpc/EM.GetStatus` when needed.
- Shelly Pro 3EM devices do not require authentication for local status endpoints by default. If you enable authentication, supply credentials with `--username/--password` or `SHELLY_USERNAME/SHELLY_PASSWORD`.
