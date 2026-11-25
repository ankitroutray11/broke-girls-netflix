import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from fastapi.testclient import TestClient
import server


class TestSanctuaryServer(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(server.app)

    def test_cors_restricts_external_origin(self):
        resp = self.client.options(
            "/api/vlc/status",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        self.assertNotIn("access-control-allow-origin", resp.headers)

    def test_cors_allows_localhost(self):
        resp = self.client.options(
            "/api/vlc/status",
            headers={
                "Origin": "http://127.0.0.1:7890",
                "Access-Control-Request-Method": "GET",
            },
        )
        self.assertEqual(resp.headers.get("access-control-allow-origin"), "http://127.0.0.1:7890")

    def test_vlc_status_endpoint(self):
        resp = self.client.get("/api/vlc/status")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), dict)

    def test_subtitles_missing_episode_returns_404(self):
        resp = self.client.get("/api/subtitles/does_not_exist_999")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
