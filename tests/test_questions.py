
import json
import unittest
from pathlib import Path

from ai.question_validator import (
    validate_question_references,
    generate_question_text,
    normalize_questions
)


ROOT = Path(__file__).resolve().parent.parent


class TestQuestionValidator(unittest.TestCase):

    def setUp(self):

        example_path = (
            ROOT / "schemas" / "scenario_example.json"
        )

        self.scenario = json.loads(
            example_path.read_text(encoding="utf-8-sig")
        )

    # 정상적인 문제 검사
    def test_valid_questions(self):

        result = validate_question_references(
            self.scenario
        )

        self.assertIsInstance(result, dict)

    # 존재하지 않는 작업 참조
    def test_invalid_action_reference(self):

        self.scenario["questions"][0]["action_id"] = 999

        with self.assertRaises(ValueError):
            validate_question_references(self.scenario)

    # 지원하지 않는 정답 유형
    def test_invalid_answer_type(self):

        self.scenario["questions"][0]["answer_type"] = (
            "unknown"
        )

        with self.assertRaises(ValueError):
            validate_question_references(self.scenario)

    # 중복된 문제 검사
    def test_duplicate_question(self):

        question = self.scenario["questions"][0].copy()
        question["id"] = 999

        self.scenario["questions"].append(question)

        with self.assertRaises(ValueError):
            validate_question_references(self.scenario)

    # 휴지통 이동 문제 생성
    def test_recycle_question(self):

        result = generate_question_text(
            "recycle",
            "timestamp"
        )

        self.assertEqual(
            result,
            "파일이 휴지통으로 이동된 시각은 언제인가?"
        )

    # 파일 생성 문제 생성
    def test_create_question(self):

        result = generate_question_text(
            "create",
            "filename"
        )

        self.assertEqual(
            result,
            "생성된 파일의 이름은 무엇인가?"
        )

    # 지원하지 않는 작업
    def test_invalid_action(self):

        with self.assertRaises(ValueError):

            generate_question_text(
                "execute",
                "filename"
            )

    # 지원하지 않는 작업 시각 질문
    def test_unsupported_timestamp(self):

        with self.assertRaises(ValueError):

            generate_question_text(
                "rename",
                "timestamp"
            )

    # 잘못된 문제 문장 표준화
    def test_normalize_question(self):

        self.scenario["questions"][0]["question"] = (
            "USB 연결 기록은 무엇인가?"
        )

        result = normalize_questions(self.scenario)

        self.assertEqual(
            result["questions"][0]["question"],
            "휴지통으로 이동된 파일의 이름은 무엇인가?"
        )

    # 실제 파일명 노출 방지
    def test_answer_not_exposed(self):

        self.scenario["questions"][0]["question"] = (
            "secret.txt의 파일명은 무엇인가?"
        )

        result = normalize_questions(self.scenario)

        self.assertNotIn(
            "secret.txt",
            result["questions"][0]["question"]
        )

    # 동일 종류의 작업이 여러 개일 때 순서 표시
    def test_multiple_actions(self):

        self.scenario["actions"].append({
            "id": 5,
            "action": "recycle",
            "path": "report.txt"
        })

        self.scenario["questions"].append({
            "id": 3,
            "question": "삭제된 파일의 이름은?",
            "answer_type": "filename",
            "action_id": 5
        })

        result = normalize_questions(self.scenario)

        self.assertTrue(
            result["questions"][-1]["question"].startswith(
                "2번째 휴지통 이동 작업:"
            )
        )


if __name__ == "__main__":
    unittest.main()