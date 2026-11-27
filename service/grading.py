"""service/grading.py - 증거 기반 자동 채점 (C 담당)

명세서 7장 기준
- 총점 100점, 문제별 동일 배점
- 정답 70% / 근거 30% 독립 채점
- Python 비교만 사용 (AI 채점 없음)
- 내부 계산은 반올림하지 않고 최종 표시만 소수 둘째 자리
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

TOTAL_SCORE = 100
VALUE_RATIO = 0.7
EVIDENCE_RATIO = 0.3
TIME_TOLERANCE = timedelta(seconds=1)
ANSWER_TYPES = ("filename", "filepath", "timestamp")


def parse_iso_utc(value: Any) -> datetime:
    """시간대가 포함된 ISO 8601 문자열을 UTC datetime으로 변환한다.

    문자열이 아니거나 형식이 틀리거나 시간대가 없으면 ValueError.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError("시각은 비어 있지 않은 문자열이어야 합니다.")
    try:
        parsed = datetime.fromisoformat(value.strip())  # Python 3.11+: 'Z' 지원
    except ValueError as exc:
        raise ValueError(f"ISO 8601 형식이 아닙니다: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"시간대가 없는 시각입니다: {value!r}")
    return parsed.astimezone(timezone.utc)


def _norm_filename(value: Any) -> str:
    return str(value).strip().casefold()


def _norm_filepath(value: Any) -> str:
    return str(value).strip().replace("\\", "/").casefold()


def _same_text(expected: Any, submitted: Any) -> bool:
    if not isinstance(expected, str) or not isinstance(submitted, str):
        return False
    return expected.strip() == submitted.strip()


def _value_correct(answer_type: str, expected: Any, submitted: Any) -> bool:
    if submitted is None or not isinstance(submitted, str) or not submitted.strip():
        return False
    if answer_type == "filename":
        return _norm_filename(expected) == _norm_filename(submitted)
    if answer_type == "filepath":
        return _norm_filepath(expected) == _norm_filepath(submitted)
    if answer_type == "timestamp":
        expected_dt = parse_iso_utc(expected)  # 정답 쪽 오류는 입력 오류
        try:
            submitted_dt = parse_iso_utc(submitted)
        except ValueError:
            return False  # 학생 시각 형식 오류 -> 정답 항목만 오답
        return abs(expected_dt - submitted_dt) <= TIME_TOLERANCE
    raise ValueError(f"지원하지 않는 answer_type: {answer_type!r}")


def _index_by_question_id(items: Any, label: str) -> dict:
    if not isinstance(items, list) or not items:
        raise ValueError(f"{label}.answers는 비어 있지 않은 배열이어야 합니다.")
    indexed: dict = {}
    for item in items:
        if not isinstance(item, dict) or "question_id" not in item:
            raise ValueError(f"{label}.answers 항목에 question_id가 없습니다.")
        qid = item["question_id"]
        if qid in indexed:
            raise ValueError(f"{label}.answers에 중복 question_id가 있습니다: {qid}")
        indexed[qid] = item
    return indexed


def _feedback(value_ok: bool, evidence_ok: bool) -> str:
    if value_ok and evidence_ok:
        return "정답 및 근거 일치"
    if value_ok:
        return "근거 다시 확인"
    if evidence_ok:
        return "정답 다시 확인"
    return "정답 및 근거 다시 확인"


def grade_answer(student: dict, answer: dict) -> dict:
    """학생 답안을 교수용 정답과 비교해 채점 결과 dict를 반환한다.

    입력 오류(구조 불일치, 다른 case_id, 중복 question_id, 모르는 question_id)는 ValueError.
    """
    if not isinstance(student, dict) or not isinstance(answer, dict):
        raise ValueError("student와 answer는 dict여야 합니다.")
    if not student.get("case_id") or student.get("case_id") != answer.get("case_id"):
        raise ValueError("학생 답안과 정답의 case_id가 다릅니다.")

    expected_by_id = _index_by_question_id(answer.get("answers"), "answer")
    student_by_id = _index_by_question_id(student.get("answers"), "student")

    unknown = set(student_by_id) - set(expected_by_id)
    if unknown:
        raise ValueError(f"정답에 없는 question_id가 제출되었습니다: {sorted(unknown)}")

    per_question = TOTAL_SCORE / len(expected_by_id)
    items = []
    total = 0.0
    for qid, expected in expected_by_id.items():
        submitted = student_by_id.get(qid)
        if submitted is None:
            value_ok = evidence_ok = False
            feedback = "답안 누락"
        else:
            value_ok = _value_correct(
                expected.get("answer_type"),
                expected.get("expected_value"),
                submitted.get("submitted_value"),
            )
            evidence_ok = _same_text(
                expected.get("evidence_type"), submitted.get("evidence_type")
            ) and _same_text(
                expected.get("evidence_reference"), submitted.get("evidence_reference")
            )
            feedback = _feedback(value_ok, evidence_ok)

        score = per_question * (
            (VALUE_RATIO if value_ok else 0.0) + (EVIDENCE_RATIO if evidence_ok else 0.0)
        )
        total += score
        items.append(
            {
                "question_id": qid,
                "value_correct": value_ok,
                "evidence_correct": evidence_ok,
                "score": round(score, 2),
                "max_score": round(per_question, 2),
                "feedback": feedback,
            }
        )

    return {
        "case_id": answer["case_id"],
        "total_score": round(total, 2),
        "max_score": TOTAL_SCORE,
        "items": items,
    }
