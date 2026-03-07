# manage

Docker orchestration script for building and running E2E tests.

## Purpose

Manages the Docker lifecycle for E2E testing: building the test image, running tests, checking status, and cleaning up artifacts.

## Usage

```bash
./manage build    # Build the E2E Docker image
./manage test     # Run E2E tests (auto-builds if needed)
./manage status   # Show container/image status
./manage clean    # Remove containers and images
./manage logs     # Show logs from last test run
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `GRAPH_VIS_PREFIX` | `graph-vis-` | Prefix for Docker artifacts (images, containers) |

## Examples

```bash
# Run with custom prefix
GRAPH_VIS_PREFIX=my-app- ./manage test

# Check what Docker artifacts exist
./manage status

# Full cleanup
./manage clean
```

## Docker Artifacts

* Image: `graph-vis-e2e`
* Container: `graph-vis-e2e-run` (removed after test via `--rm`)
