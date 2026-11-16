import os
import sys
import pathlib
import unittest
from unittest.mock import MagicMock

# Ensure chatbotbackend root is in sys.path
TEST_DIR = pathlib.Path(__file__).parent.resolve()
BACKEND_ROOT = TEST_DIR.parent.resolve()
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Mock optional packages if not installed in the test environment
for mod_name in ["groq", "schedule", "playwright", "playwright.sync_api"]:
    if mod_name not in sys.modules:
        mock_mod = MagicMock()
        if mod_name == "playwright.sync_api":
            mock_mod.TimeoutError = type("TimeoutError", (Exception,), {})
        sys.modules[mod_name] = mock_mod


class TestScraperDecouplingAndLifecycle(unittest.TestCase):
    def test_scraper_paths_resolve_to_absolute(self):
        """Verify scraper paths resolve to absolute paths regardless of current working directory."""
        import scraper

        self.assertTrue(scraper.ROOT.is_absolute(), f"ROOT {scraper.ROOT} must be absolute")
        self.assertTrue(scraper.LOG_FILE.is_absolute(), f"LOG_FILE {scraper.LOG_FILE} must be absolute")
        self.assertTrue(scraper.LOCK_FILE.is_absolute(), f"LOCK_FILE {scraper.LOCK_FILE} must be absolute")
        self.assertTrue(scraper.DB_DIR.is_absolute(), f"DB_DIR {scraper.DB_DIR} must be absolute")
        self.assertEqual(scraper.ROOT, BACKEND_ROOT)

    def test_scraper_process_lock_acquisition_and_release(self):
        """Verify process lock prevents duplicate scraper runs and releases cleanly."""
        import scraper

        # Ensure lock is cleanly released initially
        scraper.release_process_lock()

        # 1. Acquire lock
        acquired = scraper.acquire_process_lock()
        self.assertTrue(acquired, "First attempt to acquire lock should succeed")
        self.assertTrue(scraper.LOCK_FILE.exists(), "scraper.lock file should be created")
        self.assertIsNotNone(scraper._lock_file_handle, "Lock handle should be held")

        # 2. Second acquisition attempt while lock is active must fail
        # Attempting to acquire lock with another handle/process
        second_acquired = False
        second_handle = None
        try:
            second_handle = open(scraper.LOCK_FILE, "a+", encoding="utf-8")
            if sys.platform == "win32":
                import msvcrt
                second_handle.seek(0)
                msvcrt.locking(second_handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(second_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            second_acquired = True
        except (IOError, OSError):
            second_acquired = False
        finally:
            if second_handle is not None:
                try:
                    second_handle.close()
                except Exception:
                    pass

        self.assertFalse(second_acquired, "Concurrent lock acquisition must fail")

        # 3. Release lock
        scraper.release_process_lock()
        self.assertIsNone(scraper._lock_file_handle, "Lock handle should be reset to None")

        # 4. Acquire again after release must succeed
        reacquired = scraper.acquire_process_lock()
        self.assertTrue(reacquired, "Re-acquiring lock after release should succeed")
        scraper.release_process_lock()

    def test_api_does_not_register_scraper_startup_hook(self):
        """Verify api.py no longer registers startup or shutdown hooks that spawn a scraper subprocess."""
        import api

        # Verify scraper_process is not defined on api module
        self.assertFalse(hasattr(api, "scraper_process"), "api module should not have scraper_process")
        self.assertFalse(hasattr(api, "start_background_scraper"), "api should not have start_background_scraper")
        self.assertFalse(hasattr(api, "stop_background_scraper"), "api should not have stop_background_scraper")

        # Verify FastAPI router on_startup has no scraper callbacks
        startup_handlers = getattr(api.app.router, "on_startup", [])
        for handler in startup_handlers:
            self.assertNotIn("scraper", handler.__name__.lower())

    def test_api_health_endpoint(self):
        """Verify GET /health returns exact existing contract."""
        from fastapi.testclient import TestClient
        import api

        client = TestClient(api.app)
        res = client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get("status"), "ok")
        self.assertIn("running", res.json().get("message", "").lower())

    def test_api_chat_get_info_endpoint(self):
        """Verify GET /chat returns exact existing helper payload."""
        from fastapi.testclient import TestClient
        import api

        client = TestClient(api.app)
        res = client.get("/chat")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("endpoint"), "/chat")
        self.assertEqual(data.get("method_required"), "POST")

    def test_api_scraper_log_endpoint_behavior(self):
        """Verify GET /scraper/log handles missing and existing log files properly."""
        from fastapi.testclient import TestClient
        import api

        client = TestClient(api.app)
        from api import get_current_principal, AuthenticatedPrincipal

        api.app.dependency_overrides[get_current_principal] = lambda: AuthenticatedPrincipal(
            user_id="test-user",
            tenant_id="test-tenant",
            role="tenant_admin",
        )

        if not api.SCRAPER_LOG_PATH.exists():
            res = client.get("/scraper/log")
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json(), {"status": "error", "message": "Scraper log not found"})

        # Temporarily append an entry to scraper.log to test reading
        created_temp = not api.SCRAPER_LOG_PATH.exists()
        try:
            with open(api.SCRAPER_LOG_PATH, "a", encoding="utf-8") as f:
                f.write("2026-10-27 [INFO] Test scraper log entry\n")

            res = client.get("/scraper/log?lines=5")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data.get("status"), "success")
            self.assertIn("Test scraper log entry", data.get("log", ""))
        finally:
            if created_temp and api.SCRAPER_LOG_PATH.exists():
                api.SCRAPER_LOG_PATH.unlink()

    def test_chat_request_schema(self):
        """Verify ChatRequest accepts question or message and resolves user_query."""
        import api

        req1 = api.ChatRequest(question="What is Recruitment?")
        self.assertEqual(req1.user_query, "What is Recruitment?")

        req2 = api.ChatRequest(message="Tell me about pricing")
        self.assertEqual(req2.user_query, "Tell me about pricing")

        req3 = api.ChatRequest(question="Prioritized", message="Ignored")
        self.assertEqual(req3.user_query, "Prioritized")

    def test_chat_post_ndjson_streaming(self):
        """Verify POST /chat returns streaming NDJSON with expected token and sources."""
        import json
        from fastapi.testclient import TestClient
        import api

        client = TestClient(api.app)

        from api import get_current_principal, AuthenticatedPrincipal

        api.app.dependency_overrides[get_current_principal] = lambda: AuthenticatedPrincipal(
            user_id="test-user",
            tenant_id="test-tenant",
            role="tenant_admin",
        )

        # Empty message returns JSON error
        empty_res = client.post("/chat", json={"question": ""})
        self.assertEqual(empty_res.status_code, 400)
        self.assertEqual(empty_res.json(), {"detail": "Empty message received."})

        # Conversational message returns NDJSON stream
        chat_res = client.post("/chat", json={"question": "hi"})
        self.assertEqual(chat_res.status_code, 200)
        self.assertEqual(chat_res.headers.get("content-type"), "application/x-ndjson")

        lines = [line.strip() for line in chat_res.text.strip().split("\n") if line.strip()]
        self.assertTrue(len(lines) > 0, "Expected at least one NDJSON line")
        first_chunk = json.loads(lines[0])
        self.assertIn("token", first_chunk)
        self.assertIn("sources", first_chunk)


if __name__ == "__main__":
    unittest.main()
