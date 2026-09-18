import csv
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import dotenv
import httpx2
import logger
import translate_history
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)

# 避免导入 translate.py 时读取项目中的 .env。
with patch.object(dotenv, "load_dotenv", return_value=False):
    import translate as translate_module
    from translate import (
        ENV_PATH,
        MAX_TEXT_LENGTH,
        REQUEST_TIMEOUT,
        TranslationAuthError,
        TranslationConfigError,
        TranslationInputError,
        TranslationNetworkError,
        TranslationRateLimitError,
        TranslationResponseError,
        TranslationServerError,
        translate,
    )
    from main import once_translate

from translate_history import save_translate_history


def make_response(content):
    response = MagicMock()
    response.choices = [
        MagicMock(message=MagicMock(content=content))
    ]
    return response


def make_status_error(error_type, status_code):
    request = httpx2.Request("POST", "https://api.deepseek.com")
    response = httpx2.Response(status_code, request=request)
    return error_type(
        "模拟 API 错误",
        response=response,
        body=None,
    )


class TestTranslate(unittest.TestCase):
    def assert_input_error(self, text, source_language, target_language):
        with patch.dict(
            os.environ,
            {"DEEPSEEK_API_KEY": "test-key"},
            clear=True,
        ):
            with patch("translate.OpenAI") as mock_openai:
                with self.assertRaises(TranslationInputError):
                    translate(text, source_language, target_language)

                mock_openai.assert_not_called()

    def test_missing_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("translate.OpenAI") as mock_openai:
                with self.assertRaises(TranslationConfigError) as context:
                    translate("你好", "中文", "英语")
                mock_openai.assert_not_called()
        self.assertIn(".env.example", str(context.exception))
        self.assertIn(str(ENV_PATH.parent), str(context.exception))

    def test_source_mode_uses_project_directory(self):
        with patch.object(translate_module.sys, "frozen", False, create=True):
            self.assertEqual(
                translate_module._application_dir(),
                Path(translate_module.__file__).resolve().parent,
            )

    def test_frozen_mode_uses_executable_directory(self):
        executable = Path("C:/Program Files/AI Translator/AITranslator.exe")
        with patch.object(translate_module.sys, "frozen", True, create=True):
            with patch.object(translate_module.sys, "executable", str(executable)):
                self.assertEqual(
                    translate_module._application_dir(),
                    executable.resolve().parent,
                )

    def test_empty_text(self):
        self.assert_input_error("   ", "中文", "英语")

    def test_non_string_text(self):
        self.assert_input_error(None, "中文", "英语")

    def test_text_too_long(self):
        self.assert_input_error(
            "a" * (MAX_TEXT_LENGTH + 1),
            "中文",
            "英语",
        )

    def test_empty_source_language(self):
        self.assert_input_error("你好", "   ", "英语")

    def test_empty_target_language(self):
        self.assert_input_error("你好", "中文", "   ")

    def test_success_and_timeout(self):
        with patch.dict(
            os.environ,
            {"DEEPSEEK_API_KEY": "test-key"},
            clear=True,
        ):
            with patch("translate.OpenAI") as mock_openai:
                mock_openai.return_value.chat.completions.create.return_value = (
                    make_response(" Hello ")
                )

                result = translate("你好", "中文", "英语")

                self.assertEqual(result, "Hello")
                mock_openai.assert_called_once_with(
                    api_key="test-key",
                    base_url="https://api.deepseek.com",
                    timeout=REQUEST_TIMEOUT,
                )
                mock_openai.return_value.chat.completions.create.assert_called_once()
                create_kwargs = (
                    mock_openai.return_value.chat.completions.create.call_args.kwargs
                )
                self.assertEqual(create_kwargs["model"], "deepseek-v4-pro")
                self.assertFalse(create_kwargs["stream"])

    def test_empty_choices(self):
        with patch.dict(
            os.environ,
            {"DEEPSEEK_API_KEY": "test-key"},
            clear=True,
        ):
            with patch("translate.OpenAI") as mock_openai:
                response = MagicMock()
                response.choices = []
                mock_openai.return_value.chat.completions.create.return_value = (
                    response
                )

                with self.assertRaises(TranslationResponseError):
                    translate("你好", "中文", "英语")

    def test_malformed_response(self):
        with patch.dict(
            os.environ,
            {"DEEPSEEK_API_KEY": "test-key"},
            clear=True,
        ):
            with patch("translate.OpenAI") as mock_openai:
                response = MagicMock()
                response.choices = None
                mock_openai.return_value.chat.completions.create.return_value = (
                    response
                )

                with self.assertRaises(TranslationResponseError):
                    translate("你好", "中文", "英语")

    def test_empty_content(self):
        with patch.dict(
            os.environ,
            {"DEEPSEEK_API_KEY": "test-key"},
            clear=True,
        ):
            with patch("translate.OpenAI") as mock_openai:
                mock_openai.return_value.chat.completions.create.return_value = (
                    make_response("   ")
                )

                with self.assertRaises(TranslationResponseError):
                    translate("你好", "中文", "英语")

    def assert_request_error(self, sdk_error, expected_error):
        with patch.dict(
            os.environ,
            {"DEEPSEEK_API_KEY": "test-key"},
            clear=True,
        ):
            with patch("translate.OpenAI") as mock_openai:
                mock_openai.return_value.chat.completions.create.side_effect = (
                    sdk_error
                )

                with self.assertRaises(expected_error):
                    translate("你好", "中文", "英语")

    def test_authentication_error(self):
        self.assert_request_error(
            make_status_error(AuthenticationError, 401),
            TranslationAuthError,
        )

    def test_timeout_error(self):
        request = httpx2.Request(
            "POST",
            "https://api.deepseek.com",
        )
        self.assert_request_error(
            APITimeoutError(request),
            TranslationNetworkError,
        )

    def test_connection_error(self):
        request = httpx2.Request(
            "POST",
            "https://api.deepseek.com",
        )
        self.assert_request_error(
            APIConnectionError(request=request),
            TranslationNetworkError,
        )

    def test_rate_limit_error(self):
        self.assert_request_error(
            make_status_error(RateLimitError, 429),
            TranslationRateLimitError,
        )

    def test_server_error(self):
        self.assert_request_error(
            make_status_error(APIStatusError, 500),
            TranslationServerError,
        )


class TestLogger(unittest.TestCase):
    def test_windows_log_path_uses_local_app_data(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            with patch.dict(
                os.environ,
                {"LOCALAPPDATA": temporary_directory},
                clear=False,
            ):
                self.assertEqual(
                    logger._default_log_path(),
                    Path(temporary_directory) / "AiTranslator" / "app.log",
                )


class TestCli(unittest.TestCase):
    def test_failure_does_not_save_history(self):
        with patch(
            "builtins.input",
            side_effect=["中文", "英语", "你好"],
        ):
            with patch(
                "main.translate",
                side_effect=TranslationNetworkError("网络错误"),
            ):
                with patch(
                    "main.save_translate_history"
                ) as mock_save:
                    with patch("builtins.print"):
                        once_translate()

                    mock_save.assert_not_called()

    def test_success_saves_history(self):
        with patch(
            "builtins.input",
            side_effect=["中文", "英语", "你好"],
        ):
            with patch("main.translate", return_value="Hello"):
                with patch(
                    "main.save_translate_history"
                ) as mock_save:
                    with patch("builtins.print"):
                        once_translate()

                    mock_save.assert_called_once_with(
                        "中文",
                        "英语",
                        "你好",
                        "Hello",
                    )


class TestHistory(unittest.TestCase):
    def test_save_and_load_history_uses_temporary_database(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "history.sqlite3"
            with patch.object(translate_history, "DATABASE_PATH", database_path):
                save_translate_history("中文", "英语", "你好", "Hello")
                records = translate_history.load_records()

            self.assertTrue(database_path.exists())

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["source_language"], "中文")
        self.assertEqual(records[0]["target_language"], "英语")
        self.assertEqual(records[0]["source"], "你好")
        self.assertEqual(records[0]["target"], "Hello")
        self.assertIsInstance(records[0]["id"], int)

    def test_search_delete_clear_and_export_history(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "history.sqlite3"
            export_path = Path(temp_dir) / "history.csv"
            with patch.object(translate_history, "DATABASE_PATH", database_path):
                translate_history.save_record(
                    "中文",
                    "英语",
                    "第一行\n第二行 100%_",
                    "Hello",
                    "2026-09-16 10:00:00",
                )
                translate_history.save_record(
                    "英语",
                    "中文",
                    "Good morning",
                    "早上好",
                    "2026-09-16 10:01:00",
                )

                records = translate_history.load_records()
                self.assertEqual(len(translate_history.search_records("%_")), 1)
                self.assertEqual(len(translate_history.search_records("早上")), 1)
                self.assertEqual(translate_history.export_records(export_path), 2)
                self.assertTrue(translate_history.delete_record(records[0]["id"]))
                self.assertFalse(translate_history.delete_record(records[0]["id"]))
                self.assertEqual(translate_history.clear_records(), 1)
                self.assertEqual(translate_history.load_records(), [])

            with export_path.open(encoding="utf-8-sig", newline="") as output:
                exported = list(csv.DictReader(output))

        self.assertEqual(exported[0]["source"], "第一行\n第二行 100%_")
        self.assertEqual(exported[1]["target"], "早上好")

    def test_failed_save_rolls_back(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "history.sqlite3"
            with patch.object(translate_history, "DATABASE_PATH", database_path):
                translate_history.save_record("中文", "英语", "你好", "Hello")
                with self.assertRaises(translate_history.HistoryError):
                    translate_history.save_record("中文", "英语", "失败记录", None)
                records = translate_history.load_records()

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["source"], "你好")


if __name__ == "__main__":
    unittest.main()
