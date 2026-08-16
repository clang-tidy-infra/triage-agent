import unittest
from unittest.mock import MagicMock, patch

import requests

from triage_agent import godbolt


def _fake_compile_response(tool_code: int = 0, tool_id: str = "clangtidytrunk"):
    response = MagicMock()
    response.json.return_value = {
        "code": 0,
        "tools": [
            {
                "id": tool_id,
                "code": tool_code,
                "stdout": [{"text": "warning: found issue"}],
                "stderr": [],
            }
        ],
    }
    return response


class TestRunClangTidy(unittest.TestCase):
    @patch("triage_agent.godbolt.requests.post")
    def test_posts_expected_payload(self, mock_post):
        mock_post.return_value = _fake_compile_response()

        godbolt.run_clang_tidy(
            "int main() {}",
            tidy_args="-checks=bugprone-foo",
            compiler_args="-std=c++20",
        )

        mock_post.assert_called_once()
        url, kwargs = mock_post.call_args[0][0], mock_post.call_args[1]
        self.assertEqual(
            url, f"{godbolt.GODBOLT_BASE_URL}/api/compiler/clang_trunk/compile"
        )
        payload = kwargs["json"]
        self.assertEqual(payload["source"], "int main() {}")
        self.assertEqual(payload["options"]["userArguments"], "-std=c++20")
        self.assertEqual(
            payload["options"]["tools"],
            [{"id": "clangtidytrunk", "args": "-checks=bugprone-foo"}],
        )

    @patch("triage_agent.godbolt.requests.post")
    def test_parses_matching_tool_result(self, mock_post):
        mock_post.return_value = _fake_compile_response(tool_code=1)

        result = godbolt.run_clang_tidy("int main() {}", tidy_args="-checks=*")

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.stdout, "warning: found issue\n")
        self.assertEqual(result.stderr, "")

    @patch("triage_agent.godbolt.requests.post")
    def test_raises_when_tool_result_missing(self, mock_post):
        mock_post.return_value = _fake_compile_response(tool_id="clangformattrunk")

        with self.assertRaises(RuntimeError):
            godbolt.run_clang_tidy("int main() {}", tidy_args="-checks=*")

    @patch("triage_agent.godbolt.requests.post")
    def test_raises_on_http_error(self, mock_post):
        response = MagicMock()
        response.raise_for_status.side_effect = requests.HTTPError("500")
        mock_post.return_value = response

        with self.assertRaises(requests.HTTPError):
            godbolt.run_clang_tidy("int main() {}", tidy_args="-checks=*")


class TestMakeShortlink(unittest.TestCase):
    @patch("triage_agent.godbolt.requests.post")
    def test_posts_shortener_payload_and_returns_url(self, mock_post):
        response = MagicMock()
        response.json.return_value = {"url": "https://godbolt.org/z/abc123"}
        mock_post.return_value = response

        url = godbolt.make_shortlink("int main() {}", tidy_args="-checks=*")

        self.assertEqual(url, "https://godbolt.org/z/abc123")
        mock_post.assert_called_once()
        call_url, kwargs = mock_post.call_args[0][0], mock_post.call_args[1]
        self.assertEqual(call_url, f"{godbolt.GODBOLT_BASE_URL}/api/shortener")
        session = kwargs["json"]["sessions"][0]
        self.assertEqual(session["source"], "int main() {}")
        self.assertEqual(
            session["compilers"][0]["tools"],
            [{"id": "clangtidytrunk", "args": "-checks=*"}],
        )


if __name__ == "__main__":
    unittest.main()
