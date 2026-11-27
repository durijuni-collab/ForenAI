"""C(서비스) 단위 테스트: python -m pytest tests/test_service.py -v
(unittest 기반이라 python -m unittest tests.test_service 로도 실행된다)"""
import hashlib
import json
import tempfile
import unittest
import zipfile
from copy import deepcopy
from pathlib import Path

from service.answer_generator import generate_answer
from service.grading import grade_answer
from service.package_generator import generate_package

SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"


def load(name):
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def correct_student(answer):
    return {
        "case_id": answer["case_id"],
        "answers": [
            {
                "question_id": a["question_id"],
                "submitted_value": a["expected_value"],
                "evidence_type": a["evidence_type"],
                "evidence_reference": a["evidence_reference"],
            }
            for a in answer["answers"]
        ],
    }


class GradingTest(unittest.TestCase):
    def setUp(self):
        self.answer = generate_answer(load("scenario_example.json"), load("execution_result_example.json"))
        self.student = correct_student(self.answer)

    def test_all_correct(self):
        res = grade_answer(self.student, self.answer)
        self.assertEqual(res["total_score"], 100.0)
        self.assertEqual(res["max_score"], 100)

    def test_spec_example_85(self):
        self.student["answers"][1]["evidence_reference"] = "wrong"
        res = grade_answer(self.student, self.answer)
        self.assertEqual(res["total_score"], 85.0)
        self.assertEqual(res["items"][1]["score"], 35.0)
        self.assertEqual(res["items"][1]["feedback"], "근거 다시 확인")

    def test_value_wrong_evidence_right(self):
        self.student["answers"][0]["submitted_value"] = "memo.txt"
        res = grade_answer(self.student, self.answer)
        self.assertEqual(res["items"][0]["score"], 15.0)
        self.assertFalse(res["items"][0]["value_correct"])
        self.assertTrue(res["items"][0]["evidence_correct"])

    def test_missing_answer_is_zero(self):
        del self.student["answers"][1]
        res = grade_answer(self.student, self.answer)
        self.assertEqual(res["items"][1]["score"], 0.0)
        self.assertEqual(res["total_score"], 50.0)

    def test_filename_ignores_case_and_spaces(self):
        self.student["answers"][0]["submitted_value"] = "  SECRET.TXT "
        self.assertTrue(grade_answer(self.student, self.answer)["items"][0]["value_correct"])

    def test_filepath_normalization(self):
        answer = {"case_id": "c", "answers": [{"question_id": 1, "answer_type": "filepath",
                  "expected_value": "Docs/a.txt", "evidence_type": "t", "evidence_reference": "r"}]}
        student = {"case_id": "c", "answers": [{"question_id": 1, "submitted_value": "docs\\A.TXT",
                   "evidence_type": "t", "evidence_reference": "r"}]}
        self.assertEqual(grade_answer(student, answer)["total_score"], 100.0)

    def test_timestamp_tolerance_and_timezone(self):
        def score(ts):
            self.student["answers"][1]["submitted_value"] = ts
            return grade_answer(self.student, self.answer)["items"][1]["value_correct"]

        self.assertTrue(score("2026-11-24T09:30:16Z"))          # +1초 허용
        self.assertFalse(score("2026-11-24T09:30:17Z"))         # +2초 오답
        self.assertTrue(score("2026-11-24T18:30:15+09:00"))     # KST 표기, UTC로 변환
        self.assertFalse(score("2026-11-24T09:30:15"))          # 시간대 없음
        self.assertFalse(score("not-a-time"))                   # 형식 오류

    def test_bad_timestamp_keeps_evidence_score(self):
        self.student["answers"][1]["submitted_value"] = "bad"
        item = grade_answer(self.student, self.answer)["items"][1]
        self.assertEqual(item["score"], 15.0)

    def test_duplicate_question_id_raises(self):
        self.student["answers"].append(deepcopy(self.student["answers"][0]))
        with self.assertRaises(ValueError):
            grade_answer(self.student, self.answer)

    def test_other_case_id_raises(self):
        self.student["case_id"] = "other"
        with self.assertRaises(ValueError):
            grade_answer(self.student, self.answer)

    def test_unknown_question_id_raises(self):
        self.student["answers"].append({"question_id": 99, "submitted_value": "x",
                                        "evidence_type": "x", "evidence_reference": "x"})
        with self.assertRaises(ValueError):
            grade_answer(self.student, self.answer)

    def test_display_rounding_only(self):
        answers = [{"question_id": i, "answer_type": "filename", "expected_value": f"f{i}",
                    "evidence_type": "t", "evidence_reference": "r"} for i in (1, 2, 3)]
        subs = [{"question_id": i, "submitted_value": f"f{i}", "evidence_type": "t",
                 "evidence_reference": "r"} for i in (1, 2, 3)]
        res = grade_answer({"case_id": "c", "answers": subs}, {"case_id": "c", "answers": answers})
        self.assertEqual(res["items"][0]["score"], 33.33)
        self.assertEqual(res["total_score"], 100.0)  # 내부 합산은 반올림 전 값


class AnswerGeneratorTest(unittest.TestCase):
    def setUp(self):
        self.scenario = load("scenario_example.json")
        self.result = load("execution_result_example.json")

    def test_normal(self):
        answer = generate_answer(self.scenario, self.result)
        self.assertEqual(answer["case_id"], "case001")
        self.assertEqual([a["question_id"] for a in answer["answers"]], [1, 2])
        self.assertEqual(answer["answers"][0]["expected_value"], "secret.txt")
        self.assertEqual(answer["answers"][1]["expected_value"], "2026-11-24T09:30:15Z")

    def test_missing_evidence_raises(self):
        self.result["results"][3]["evidence_reference"] = None
        with self.assertRaises(ValueError):
            generate_answer(self.scenario, self.result)

    def test_failed_action_raises(self):
        self.result["results"][3]["status"] = "failed"
        with self.assertRaises(ValueError):
            generate_answer(self.scenario, self.result)

    def test_missing_action_result_raises(self):
        del self.result["results"][3]
        with self.assertRaises(ValueError):
            generate_answer(self.scenario, self.result)

    def test_top_level_failed_raises(self):
        self.result["status"] = "failed"
        self.result["error"] = "VM 실패"
        with self.assertRaises(ValueError):
            generate_answer(self.scenario, self.result)


class PackageGeneratorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.scenario = load("scenario_example.json")
        self.result = load("execution_result_example.json")
        self.case_dir = self.base / "outputs" / "case001"
        self.case_dir.mkdir(parents=True)
        raw = self.case_dir / "evidence.raw"
        raw.write_bytes(b"fake-raw-image-for-test")
        self.result["evidence_path"] = "outputs/case001/evidence.raw"
        self.result["sha256"] = hashlib.sha256(raw.read_bytes()).hexdigest()

    def tearDown(self):
        self.tmp.cleanup()

    def test_returns_relative_posix_paths(self):
        pkg = generate_package(self.scenario, self.result, base_dir=self.base)
        self.assertEqual(pkg["student_zip"], "outputs/case001/student_case.zip")
        self.assertEqual(pkg["teacher_zip"], "outputs/case001/teacher_answer.zip")

    def test_student_zip_has_no_answers(self):
        pkg = generate_package(self.scenario, self.result, base_dir=self.base)
        with zipfile.ZipFile(self.base / pkg["student_zip"]) as z:
            self.assertEqual(set(z.namelist()), {"student/questions.json", "evidence.raw"})
            text = z.read("student/questions.json").decode("utf-8")
        data = json.loads(text)
        self.assertEqual(set(data), {"case_id", "case_title", "description", "objective", "difficulty", "questions"})
        self.assertEqual(set(data["questions"][0]), {"id", "question"})
        for leaked in ("expected_value", "actions", "secret.txt", "evidence_reference", "sha256"):
            self.assertNotIn(leaked, text)

    def test_teacher_zip_contents(self):
        pkg = generate_package(self.scenario, self.result, base_dir=self.base)
        with zipfile.ZipFile(self.base / pkg["teacher_zip"]) as z:
            self.assertEqual(set(z.namelist()),
                             {"teacher/answers.json", "scenario.json", "execution_result.json"})
            execution = json.loads(z.read("execution_result.json"))
        self.assertEqual(execution["sha256"], self.result["sha256"])  # 교수 자료에서 SHA-256 확인

    def test_hash_mismatch_creates_nothing(self):
        self.result["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            generate_package(self.scenario, self.result, base_dir=self.base)
        self.assertFalse((self.case_dir / "student_case.zip").exists())

    def test_missing_hash_raises(self):
        self.result["sha256"] = None
        with self.assertRaises(ValueError):
            generate_package(self.scenario, self.result, base_dir=self.base)

    def test_missing_evidence_file_raises(self):
        (self.case_dir / "evidence.raw").unlink()
        with self.assertRaises(ValueError):
            generate_package(self.scenario, self.result, base_dir=self.base)

    def test_unsafe_case_id_raises(self):
        self.result["case_id"] = "../evil"
        with self.assertRaises(ValueError):
            generate_package(self.scenario, self.result, base_dir=self.base)


if __name__ == "__main__":
    unittest.main()
