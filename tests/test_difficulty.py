
import unittest

from ai.difficulty_generator import (
    get_difficulty_rules,
    validate_difficulty,
    build_difficulty_prompt
)


class TestDifficulty(unittest.TestCase):

    # 테스트용 사건 데이터 생성
    def make_scenario(self, difficulty):

        rules = get_difficulty_rules(difficulty)

        actions = []

        # 파일 생성 작업
        for i in range(rules["file_count"]):

            actions.append({
                "id": i + 1,
                "action": "create",
                "path": f"file_{i + 1}.txt",
                "content": f"테스트 문서 {i + 1}"
            })

        # 추가 파일 작업
        extra_count = (
            rules["min_actions"]
            - rules["file_count"]
        )

        for i in range(extra_count):

            actions.append({
                "id": len(actions) + 1,
                "action": "recycle",
                "path": f"file_{i + 1}.txt"
            })

        # 실습 문제 생성
        questions = []

        for i in range(rules["question_count"]):

            questions.append({
                "id": i + 1,
                "question": "파일의 이름은 무엇인가?",
                "answer_type": "filename",
                "action_id": actions[-1 - i]["id"]
            })

        return {
            "case_title": "난이도 테스트 사건",
            "description": "난이도 검증용 사건",
            "objective": "파일 작업 기록 분석",
            "difficulty": difficulty,
            "actions": actions,
            "questions": questions
        }

    # 초급 설정 검사
    def test_easy_rules(self):

        rules = get_difficulty_rules("easy")

        self.assertEqual(rules["file_count"], 3)
        self.assertEqual(rules["min_actions"], 4)
        self.assertEqual(rules["max_actions"], 5)
        self.assertEqual(rules["question_count"], 2)

    # 중급 설정 검사
    def test_medium_rules(self):

        rules = get_difficulty_rules("medium")

        self.assertEqual(rules["file_count"], 5)
        self.assertEqual(rules["min_actions"], 7)
        self.assertEqual(rules["max_actions"], 10)
        self.assertEqual(rules["question_count"], 3)

    # 고급 설정 검사
    def test_hard_rules(self):

        rules = get_difficulty_rules("hard")

        self.assertEqual(rules["file_count"], 7)
        self.assertEqual(rules["min_actions"], 11)
        self.assertEqual(rules["max_actions"], 15)
        self.assertEqual(rules["question_count"], 4)

    # 잘못된 난이도 검사
    def test_invalid_difficulty(self):

        with self.assertRaises(ValueError):

            get_difficulty_rules("expert")

    # 초급 사건 검사
    def test_valid_easy(self):

        scenario = self.make_scenario("easy")

        result = validate_difficulty(
            scenario, "easy"
        )

        self.assertEqual(result, scenario)

    # 중급 사건 검사
    def test_valid_medium(self):

        scenario = self.make_scenario("medium")

        result = validate_difficulty(
            scenario, "medium"
        )

        self.assertEqual(result, scenario)

    # 고급 사건 검사
    def test_valid_hard(self):

        scenario = self.make_scenario("hard")

        result = validate_difficulty(
            scenario, "hard"
        )

        self.assertEqual(result, scenario)

    # 생성 파일 수 부족
    def test_invalid_file_count(self):

        scenario = self.make_scenario("easy")

        scenario["actions"].pop(0)

        with self.assertRaises(ValueError):

            validate_difficulty(scenario, "easy")

    # 전체 작업 수 부족
    def test_too_few_actions(self):

        scenario = self.make_scenario("medium")

        scenario["actions"].pop()

        with self.assertRaises(ValueError):

            validate_difficulty(scenario, "medium")

    # 전체 작업 수 초과
    def test_too_many_actions(self):

        scenario = self.make_scenario("easy")

        for i in range(3):

            scenario["actions"].append({
                "id": 100 + i,
                "action": "copy",
                "path": "file_2.txt",
                "destination": f"copy_{i}.txt"
            })

        with self.assertRaises(ValueError):

            validate_difficulty(scenario, "easy")

    # 실습 문제 수 부족
    def test_invalid_question_count(self):

        scenario = self.make_scenario("hard")

        scenario["questions"].pop()

        with self.assertRaises(ValueError):

            validate_difficulty(scenario, "hard")

    # 요청 난이도 불일치
    def test_difficulty_mismatch(self):

        scenario = self.make_scenario("easy")

        with self.assertRaises(ValueError):

            validate_difficulty(scenario, "hard")

    # 난이도별 프롬프트 검사
    def test_difficulty_prompt(self):

        for difficulty in ["easy", "medium", "hard"]:

            with self.subTest(difficulty=difficulty):

                prompt = build_difficulty_prompt(
                    difficulty
                )

                self.assertIn(difficulty, prompt)
                self.assertIn("파일 생성", prompt)
                self.assertIn("전체 작업", prompt)
                self.assertIn("실습 문제", prompt)

    # 원본 난이도 설정 변경 방지
    def test_rules_copy(self):

        rules = get_difficulty_rules("easy")

        rules["file_count"] = 999

        original = get_difficulty_rules("easy")

        self.assertEqual(
            original["file_count"], 3
        )


if __name__ == "__main__":
    unittest.main()
