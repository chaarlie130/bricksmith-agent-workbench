import io
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from bricksmith.workbench import chatgpt_plan as plan


class PlanUsageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "auth.json"

    def test_private_storage_and_scope_gate(self):
        plan._write_private(self.path, {"ext_agent_host_id": "urn:uuid:test"})
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        with self.assertRaisesRegex(RuntimeError, "plan-usage grant"):
            plan.access_token(self.path)
        self.path.chmod(0o644)
        with self.assertRaisesRegex(RuntimeError, "permissions"):
            plan.access_token(self.path)

    def test_refresh_uses_issued_client_and_rotates_token(self):
        plan._write_private(self.path, {
            "client_id": "oaiapp_test", "access_token": "expired",
            "refresh_token": "old-refresh", "expires_at": 0,
            "scopes": [plan.REQUIRED_SCOPE],
        })
        with patch.object(plan, "_read_json", return_value={
            "access_token": "new-access", "refresh_token": "new-refresh",
            "expires_in": 3600, "scope": plan.REQUIRED_SCOPE,
        }) as request:
            self.assertEqual(plan.access_token(self.path), "new-access")
        self.assertEqual(request.call_args.kwargs["data"]["client_id"], "oaiapp_test")
        self.assertEqual(request.call_args.kwargs["data"]["resource"], plan.RESOURCE)
        saved = json.loads(self.path.read_text())
        self.assertEqual(saved["refresh_token"], "new-refresh")
        self.assertGreater(saved["expires_at"], time.time())

    def test_models_use_plan_catalog_slugs(self):
        with patch.object(plan, "access_token", return_value="test-access"), \
             patch.object(plan, "_read_json", return_value={"models": [
                 {"slug": "gpt-6-astra", "visibility": "list"},
                 {"slug": "internal", "visibility": "hide"},
             ]}):
            self.assertEqual(plan.list_models(self.path), ["gpt-6-astra"])

    def test_ask_sends_real_plan_usage_request_contract(self):
        stream = io.BytesIO(
            b'data: {"type":"response.output_text.delta","delta":"Brick"}\n\n'
            b'data: {"type":"response.output_text.delta","delta":"Smith"}\n\n'
            b'data: {"type":"response.completed"}\n\n'
        )
        with patch.object(plan, "list_models", return_value=["example-model"]), \
             patch.object(plan, "access_token", return_value="test-access"), \
             patch.object(plan, "urlopen", return_value=stream) as open_url:
            result = plan.ask("example-model", "build a roof", "agent instructions", self.path)
        self.assertEqual(result, "BrickSmith")
        request = open_url.call_args.args[0]
        self.assertEqual(request.full_url, plan.RESOURCE + "/responses")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-access")
        payload = json.loads(request.data)
        self.assertEqual(payload["instructions"], "agent instructions")
        self.assertEqual(payload["input"], [{"role": "user", "content": "build a roof"}])
        self.assertEqual(payload["store"], False)
        self.assertEqual(payload["stream"], True)

    def test_ask_rejects_incomplete_stream_and_unavailable_model(self):
        with patch.object(plan, "list_models", return_value=["example-model"]), \
             patch.object(plan, "access_token", return_value="test-access"), \
             patch.object(plan, "urlopen", return_value=io.BytesIO(
                 b'data: {"type":"response.output_text.delta","delta":"partial"}\n\n')):
            with self.assertRaisesRegex(RuntimeError, "without response.completed"):
                plan.ask("example-model", "hello", "", self.path)
        with patch.object(plan, "list_models", return_value=[]):
            with self.assertRaisesRegex(ValueError, "not listed"):
                plan.ask("missing", "hello", "", self.path)

    def test_respond_recovers_streamed_function_call_when_final_output_empty(self):
        item = {"type": "function_call", "name": "bricksmith.search", "call_id": "call_1",
                "arguments": '{"query":"roof"}'}
        events = [
            {"type": "response.output_item.done", "output_index": 0, "item": item},
            {"type": "response.completed", "response": {"output": [], "usage": {"total_tokens": 10}}},
        ]
        stream = io.BytesIO("".join(f"data: {json.dumps(event)}\n\n" for event in events).encode())
        with patch.object(plan, "list_models", return_value=["example-model"]), \
             patch.object(plan, "access_token", return_value="test-access"), \
             patch.object(plan, "urlopen", return_value=stream):
            result = plan.respond("example-model", "instructions", [], [], self.path)
        self.assertEqual(result["output"], [item])

    def test_respond_explains_separate_plan_sharing_limit(self):
        event = {"type": "response.failed", "response": {"error": {
            "code": "subscription_sharing_usage_limit_exceeded"}}}
        stream = io.BytesIO(f"data: {json.dumps(event)}\n\n".encode())
        with patch.object(plan, "list_models", return_value=["example-model"]), \
             patch.object(plan, "access_token", return_value="test-access"), \
             patch.object(plan, "urlopen", return_value=stream):
            with self.assertRaisesRegex(RuntimeError, "pause live model requests"):
                plan.respond("example-model", "instructions", [], [], self.path)


if __name__ == "__main__":
    unittest.main()
