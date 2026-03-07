# E2E Tests

End-to-end tests using headless Chromium via Selenium WebDriver.

## Purpose

Verify the full stack (server + frontend) works correctly in a browser environment, including UI interactions, API integration, and multi-client WebSocket sync.

## Test Coverage

| Test | Description |
|------|-------------|
| `test_page_loads_with_canvas` | Page loads and vis-network renders a canvas element |
| `test_add_triplet_via_ui` | Add a triplet via bulk input, verify nodes appear via API |
| `test_delete_node_via_modal` | Double-click node to trigger delete modal, confirm deletion |
| `test_multi_client_sync` | Two browser windows receive the same graph updates |

## Running

```bash
# Via manage script (recommended)
./manage test

# Manual Docker build + run
docker build -t graph-vis-e2e -f e2e/Dockerfile .
docker run --rm graph-vis-e2e
```

## Stack

* **Python 3.12-slim** base image
* **Chromium** + **chromedriver** for headless browser
* **Selenium** WebDriver for browser automation
* **pytest** test runner
* Server starts in-process via `multiprocessing`
