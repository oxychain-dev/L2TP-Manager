#!/usr/bin/env python3
"""Guard against EAP account onboarding incorrectly requiring IKEv2 server JSON."""
import contextlib
import importlib.util
import io
import pathlib
import sys
import tempfile
import unittest
from unittest import mock


SOURCE = pathlib.Path(__file__).resolve().parent.parent / "tools" / "ikev2-dualstack.py"
SPEC = importlib.util.spec_from_file_location("ikev2_registry", SOURCE)
BACKEND = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BACKEND)


class RegistryCliTests(unittest.TestCase):
    def call_main(self, arguments):
        with mock.patch.object(sys, "argv", ["ikev2-dualstack.py", *arguments]):
            with mock.patch.object(BACKEND.os, "geteuid", return_value=0):
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    BACKEND.main()
                    return output.getvalue()

    def test_init_users_does_not_read_server_config(self):
        with mock.patch.object(BACKEND, "create_new_registry") as create:
            with mock.patch.object(BACKEND, "root_file", side_effect=AssertionError("server JSON accessed")):
                result = self.call_main(["init-users", "--config", "/nonexistent/server.json"])
        create.assert_called_once_with(pathlib.Path("/etc/l2tp-manager/ikev2-users.json"))
        self.assertIn("Created private EAP", result)

    def test_add_user_without_server_config(self):
        registry = pathlib.Path("/etc/l2tp-manager/ikev2-users.json")
        def only_users(path):
            if path != registry:
                raise AssertionError("server JSON accessed before user creation")
            return {}
        with mock.patch.object(BACKEND, "root_file", side_effect=only_users):
            with mock.patch.object(BACKEND, "atomic_json") as update:
                with mock.patch.object(BACKEND.getpass, "getpass", return_value="random-correct-strong-secret"):
                    result = self.call_main(["add-user", "--username", "myphone",
                                             "--config", "/nonexistent/server.json"])
        update.assert_called_once()
        self.assertEqual(update.call_args.args[0], registry)
        self.assertIn("myphone", update.call_args.args[1])
        self.assertIn("NOT loaded", result)

    def test_audit_reports_missing_config_and_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = self.call_main(["audit", "--config", tmp + "/server.json",
                                     "--users", tmp + "/users.json"])
        self.assertIn("registry: not created", output)
        self.assertIn("configuration: not created", output)

    def test_render_still_requires_server_config(self):
        with mock.patch.object(BACKEND, "root_file", side_effect=FileNotFoundError("missing server JSON")):
            with self.assertRaises(FileNotFoundError):
                self.call_main(["render", "--output", "/nonexistent/example.conf"])


if __name__ == "__main__":
    unittest.main()
