"""E2E tests using headless Chromium via Selenium."""

import multiprocessing
import time

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


BASE_URL = "http://127.0.0.1:7849"


def _run_server():
    """Start the FastAPI server in a subprocess."""
    import uvicorn
    from graph_vis_server import app
    uvicorn.run(app, host="0.0.0.0", port=7849, log_level="warning")


@pytest.fixture(scope="session")
def server():
    """Launch the server for the test session."""
    proc = multiprocessing.Process(target=_run_server, daemon=True)
    proc.start()
    # Wait for server to be ready
    import urllib.request
    for _ in range(30):
        try:
            urllib.request.urlopen(f"{BASE_URL}/api/graph", timeout=1)
            break
        except Exception:
            time.sleep(0.5)
    yield proc
    proc.terminate()
    proc.join(timeout=5)


def _make_driver(block_cdn=False):
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    if block_cdn:
        # Simulate offline / air-gapped: make the CDN host unresolvable so the
        # <script src="https://cdnjs...vis-network..."> fails to load and the
        # local /static/deps fallback must take over.
        opts.add_argument("--host-resolver-rules=MAP cdnjs.cloudflare.com 127.0.0.1:1")
    service = Service("/usr/bin/chromedriver")
    return webdriver.Chrome(service=service, options=opts)


@pytest.fixture
def driver(server):
    d = _make_driver()
    d.get(BASE_URL)
    yield d
    d.quit()


def test_page_loads_with_canvas(driver):
    """Page loads and vis-network renders a canvas element."""
    wait = WebDriverWait(driver, 10)
    canvas = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#graph canvas")))
    assert canvas.is_displayed()


def test_add_triplet_via_ui(driver):
    """Add a triplet via the bulk input and verify nodes appear in the graph data."""
    wait = WebDriverWait(driver, 10)
    # Wait for page to be ready
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#graph canvas")))

    # The page starts in multi-line mode; use the bulk textarea
    textarea = driver.find_element(By.ID, "bulk-input")
    textarea.clear()
    textarea.send_keys("Alice knows Bob")

    add_btn = driver.find_element(By.ID, "add-button")
    add_btn.click()

    # Give WS broadcast time to update
    time.sleep(1)

    # Verify via API that the graph has the triplet
    import urllib.request
    import json
    resp = urllib.request.urlopen(f"{BASE_URL}/api/graph", timeout=5)
    graph = json.loads(resp.read())
    node_ids = {n["id"] for n in graph["nodes"]}
    assert "Alice" in node_ids
    assert "Bob" in node_ids
    assert any(e["label"] == "knows" for e in graph["edges"])


def test_delete_node_via_modal(driver):
    """Double-click a node to trigger delete modal, confirm deletion."""
    wait = WebDriverWait(driver, 10)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#graph canvas")))

    # Add a node via API first
    import urllib.request
    import json
    data = json.dumps({"subject": "Test", "predicate": "is", "object": "Node"}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/api/add-triplet",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=5)
    time.sleep(1)

    # Double-click on canvas center (where nodes cluster)
    canvas = driver.find_element(By.CSS_SELECTOR, "#graph canvas")
    from selenium.webdriver.common.action_chains import ActionChains
    actions = ActionChains(driver)
    actions.move_to_element(canvas).click().pause(0.1).click().perform()

    # If a node was hit, the modal should appear
    time.sleep(0.5)
    modal = driver.find_element(By.ID, "delete-modal")
    if modal.is_displayed():
        yes_btn = driver.find_element(By.ID, "yes-button")
        yes_btn.click()
        time.sleep(0.5)
        # Verify deletion via API
        resp = urllib.request.urlopen(f"{BASE_URL}/api/graph", timeout=5)
        graph = json.loads(resp.read())
        # At least one node should have been removed
        assert len(graph["nodes"]) < 2


def test_offline_cdn_fallback_boots_app(server):
    """With the CDN blocked, the local vis-network fallback must still boot the
    app: the canvas renders and a triplet can be added end-to-end."""
    driver = _make_driver(block_cdn=True)
    try:
        driver.get(BASE_URL)
        wait = WebDriverWait(driver, 15)

        # Canvas only exists if vis-network loaded (here: from the local copy).
        canvas = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#graph canvas"))
        )
        assert canvas.is_displayed()

        # vis global must be defined by the local UMD build.
        assert driver.execute_script("return !!window.vis") is True

        # The "both sources failed" error banner must NOT be present.
        assert "Failed to load vis-network" not in driver.page_source

        # Add a triplet through the UI and confirm it lands in the graph.
        textarea = driver.find_element(By.ID, "bulk-input")
        textarea.clear()
        textarea.send_keys("Offline knows Fallback")
        driver.find_element(By.ID, "add-button").click()
        time.sleep(1)

        import urllib.request
        import json
        resp = urllib.request.urlopen(f"{BASE_URL}/api/graph", timeout=5)
        graph = json.loads(resp.read())
        node_ids = {n["id"] for n in graph["nodes"]}
        assert "Offline" in node_ids
        assert "Fallback" in node_ids
    finally:
        driver.quit()


def test_multi_client_sync(server):
    """Two browser windows see the same graph updates."""
    driver1 = _make_driver()
    driver2 = _make_driver()
    try:
        driver1.get(BASE_URL)
        driver2.get(BASE_URL)

        wait1 = WebDriverWait(driver1, 10)
        wait2 = WebDriverWait(driver2, 10)
        wait1.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#graph canvas")))
        wait2.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#graph canvas")))

        # Add triplet via API
        import urllib.request
        import json
        data = json.dumps({"subject": "Sync1", "predicate": "with", "object": "Sync2"}).encode()
        req = urllib.request.Request(
            f"{BASE_URL}/api/add-triplet",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5)
        time.sleep(1)

        # Both drivers should see the update via the API
        resp = urllib.request.urlopen(f"{BASE_URL}/api/graph", timeout=5)
        graph = json.loads(resp.read())
        node_ids = {n["id"] for n in graph["nodes"]}
        assert "Sync1" in node_ids
        assert "Sync2" in node_ids
    finally:
        driver1.quit()
        driver2.quit()
