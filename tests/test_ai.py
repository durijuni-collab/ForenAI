
import json
import unittest
from pathlib import Path

from ai.scenario_validator import validate_scenario


ROOT = Path(__file__).resolve().parent.parent


class TestScenarioValidator(unittest.TestCase):

    def setUp(self):

        example_path = (
            ROOT / "schemas" / "scenario_example.json"
        )

        self.scenario = json.loads(
            example_path.read_text(encoding="utf-8")
        )

    # 정상적인 사건
    def test_valid_scenario(self):

        result = validate_scenario(self.scenario)

        self.assertIsInstance(result, dict)

    # 필수 항목 누락
    def test_missing_field(self):

        del self.scenario["case_title"]

        with self.assertRaises(ValueError):
            validate_scenario(self.scenario)

    # 지원하지 않는 명령어
    def test_invalid_action(self):

        self.scenario["actions"][0]["action"] = "execute"

        with self.assertRaises(ValueError):
            validate_scenario(self.scenario)

    # 존재하지 않는 파일 삭제
    def test_missing_file(self):

        self.scenario["actions"][-1]["path"] = "unknown.txt"

        with self.assertRaises(ValueError):
            validate_scenario(self.scenario)

    # 중복 파일 생성
    def test_duplicate_file(self):

        first = self.scenario["actions"][0]

        self.scenario["actions"].append({
            "id": 999,
            "action": "create",
            "path": first["path"].upper(),
            "content": "중복 파일"
        })

        with self.assertRaises(ValueError):
            validate_scenario(self.scenario)

    # 절대 경로 접근
    def test_absolute_path(self):

        self.scenario["actions"][0]["path"] = "C:/test.txt"

        with self.assertRaises(ValueError):
            validate_scenario(self.scenario)

    # 상위 폴더 접근
    def test_parent_path(self):

        self.scenario["actions"][0]["path"] = "../test.txt"

        with self.assertRaises(ValueError):
            validate_scenario(self.scenario)

    # 작업 ID 중복
    def test_duplicate_action_id(self):

        self.scenario["actions"][1]["id"] = (
            self.scenario["actions"][0]["id"]
        )

        with self.assertRaises(ValueError):
            validate_scenario(self.scenario)

    # 잘못된 작업 참조
    def test_invalid_reference(self):

        self.scenario["questions"][0]["action_id"] = 999

        with self.assertRaises(ValueError):
            validate_scenario(self.scenario)

    # 잘못된 정답 유형
    def test_invalid_answer_type(self):

        self.scenario["questions"][0]["answer_type"] = "unknown"

        with self.assertRaises(ValueError):
            validate_scenario(self.scenario)

    # Windows 예약 파일명
    def test_reserved_filename(self):

        self.scenario["actions"][0]["path"] = "CON.txt"

        with self.assertRaises(ValueError):
            validate_scenario(self.scenario)

    # 복사 목적지 충돌
    def test_destination_conflict(self):

        self.scenario["actions"].insert(2, {
            "id": 999,
            "action": "copy",
            "path": "report.txt",
            "destination": "memo.txt"
        })

        with self.assertRaises(ValueError):
            validate_scenario(self.scenario)


if __name__ == "__main__":
    unittest.main()
