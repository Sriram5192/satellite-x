from pathlib import Path


def test_offline_queue_rendering_does_not_use_inner_html_for_evidence():
    script = Path("mobile/app.js").read_text()
    assert ".innerHTML" not in script
    assert "textContent" in script
    assert "replaceChildren" in script


def test_service_worker_never_intercepts_api_requests():
    worker = Path("mobile/service-worker.js").read_text()
    assert 'url.pathname.startsWith("/api/")' in worker
    assert "cache.put" in worker
    assert 'const ASSETS=new Set' in worker
