import hashlib
import hmac
import http.client
import json
import os
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import app


class WebhookTests(unittest.TestCase):
    def test_signed_tracked_release_is_queued_and_invalid_signature_is_rejected(self):
        secret = "test-secret-only"
        payload = json.dumps({
            "action": "published",
            "repository": {"full_name": "PeterSuh-Q3/syno_nvidia_driver"},
        }).encode()
        signature = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        queued = threading.Event()
        previous_secret = os.environ.get("GITHUB_WEBHOOK_SECRET")
        os.environ["GITHUB_WEBHOOK_SECRET"] = secret
        server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(app, "queue_release_sync", side_effect=queued.set):
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
                connection.request("POST", "/webhook/github", body=payload,
                                   headers={"Content-Type": "application/json",
                                            "X-GitHub-Event": "release",
                                            "X-Hub-Signature-256": "sha256=bad"})
                response = connection.getresponse()
                self.assertEqual(response.status, 401)
                response.read()
                self.assertFalse(queued.is_set())

                connection.request("POST", "/webhook/github", body=payload,
                                   headers={"Content-Type": "application/json",
                                            "X-GitHub-Event": "release",
                                            "X-Hub-Signature-256": signature})
                response = connection.getresponse()
                self.assertEqual(response.status, 202)
                response.read()
                self.assertTrue(queued.is_set())
                connection.close()
        finally:
            server.shutdown()
            server.server_close()
            if previous_secret is None:
                os.environ.pop("GITHUB_WEBHOOK_SECRET", None)
            else:
                os.environ["GITHUB_WEBHOOK_SECRET"] = previous_secret


if __name__ == "__main__":
    unittest.main()
