
import json
import unittest

from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

import httpx

from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError
)

from ai.ai_generator import (
    validate_input,
    extract_json,
    request_ai,
    generate_scenario
)

from ai.exceptions import (
    AIInputError,
    AIConnectionError,
    AIAuthenticationError,
    AIRateLimitError,
    AIGenerationError
)


ROOT = Path(__file__).resolve().parent.parent


class TestAIGenerator(unittest.TestCase):

    def setUp(self):

        self.scenario = json.loads(
            (
                ROOT
                / "schemas"
                / "scenario_example.json"
            ).read_text(encoding="utf-8-sig")
        )

        self.valid_json = json.dumps(
            self.scenario,
            ensure_ascii=False
        )

    # 정상 입력
    def test_valid_input(self):

        result = validate_input(
            "파일 삭제 기록 분석",
            "easy"
        )

        self.assertEqual(
            result,
            "파일 삭제 기록 분석"
        )

    # 빈 입력
    def test_empty_input(self):

        with self.assertRaises(AIInputError):

            validate_input("", "easy")

    # 너무 긴 입력
    def test_long_input(self):

        with self.assertRaises(AIInputError):

            validate_input("가" * 1001, "easy")

    # 잘못된 난이도
    def test_invalid_difficulty(self):

        with self.assertRaises(AIInputError):

            validate_input("파일 생성", "expert")

    # 지원하지 않는 주제
    def test_unsupported_objective(self):

        with self.assertRaises(AIInputError):

            validate_input(
                "USB 연결 기록 분석",
                "easy"
            )

    # 정상 JSON
    def test_valid_json(self):

        result = extract_json(self.valid_json)

        self.assertEqual(
            result,
            self.scenario
        )

    # 마크다운 JSON
    def test_markdown_json(self):

        text = (
            "```json\n"
            + self.valid_json
            + "\n```"
        )

        result = extract_json(text)

        self.assertEqual(
            result,
            self.scenario
        )

    # 설명이 포함된 JSON
    def test_json_with_text(self):

        text = (
            "생성 결과입니다.\n"
            + self.valid_json
        )

        result = extract_json(text)

        self.assertEqual(
            result,
            self.scenario
        )

    # 빈 JSON 응답
    def test_empty_response(self):

        with self.assertRaises(ValueError):

            extract_json("")

    # 잘못된 JSON
    def test_invalid_json(self):

        with self.assertRaises(ValueError):

            extract_json("잘못된 AI 응답")

    # 서버 연결 실패
    def test_connection_error(self):

        client = Mock()

        request = httpx.Request(
            "POST",
            "https://example.com"
        )

        client.chat.completions.create.side_effect = (
            APIConnectionError(request=request)
        )

        with self.assertRaises(AIConnectionError):

            request_ai(client, "test-model", [])

    # 응답 시간 초과
    def test_timeout_error(self):

        client = Mock()

        request = httpx.Request(
            "POST",
            "https://example.com"
        )

        client.chat.completions.create.side_effect = (
            APITimeoutError(request=request)
        )

        with self.assertRaises(AIConnectionError):

            request_ai(client, "test-model", [])

    # API 인증 실패
    def test_authentication_error(self):

        client = Mock()

        response = httpx.Response(
            401,
            request=httpx.Request(
                "POST",
                "https://example.com"
            )
        )

        client.chat.completions.create.side_effect = (
            AuthenticationError(
                "Unauthorized",
                response=response,
                body=None
            )
        )

        with self.assertRaises(AIAuthenticationError):

            request_ai(client, "test-model", [])

    # API 사용량 초과
    def test_rate_limit_error(self):

        client = Mock()

        response = httpx.Response(
            429,
            request=httpx.Request(
                "POST",
                "https://example.com"
            )
        )

        client.chat.completions.create.side_effect = (
            RateLimitError(
                "Rate limit",
                response=response,
                body=None
            )
        )

        with self.assertRaises(AIRateLimitError):

            request_ai(client, "test-model", [])

    # 잘못된 응답 후 재생성 성공
    @patch("ai.ai_generator.get_api_config")
    @patch("ai.ai_generator.OpenAI")
    @patch("ai.ai_generator.request_ai")
    def test_retry_success(
        self,
        mock_request,
        mock_openai,
        mock_config
    ):

        mock_config.return_value = (
            "test-key",
            "https://example.com",
            "test-model"
        )

        mock_openai.return_value = MagicMock()

        mock_request.side_effect = [
            "잘못된 응답",
            self.valid_json
        ]

        result = generate_scenario(
            "삭제된 파일 분석",
            "easy"
        )

        self.assertIsInstance(result, dict)

        self.assertEqual(
            mock_request.call_count,
            2
        )

    # 최대 재생성 횟수 초과
    @patch("ai.ai_generator.get_api_config")
    @patch("ai.ai_generator.OpenAI")
    @patch("ai.ai_generator.request_ai")
    def test_retry_failure(
        self,
        mock_request,
        mock_openai,
        mock_config
    ):

        mock_config.return_value = (
            "test-key",
            "https://example.com",
            "test-model"
        )

        mock_openai.return_value = MagicMock()

        mock_request.return_value = (
            "잘못된 응답"
        )

        with self.assertRaises(AIGenerationError):

            generate_scenario(
                "삭제된 파일 분석",
                "easy"
            )

        self.assertEqual(
            mock_request.call_count,
            3
        )


if __name__ == "__main__":
    unittest.main()
