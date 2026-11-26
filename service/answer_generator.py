"""service/answer_generator.py - 교수용 정답 생성 (C 담당)

명세서 6장 기준
- questions.action_id 와 results.action_id 를 매칭한다.
- filename -> filename, filepath -> path, timestamp -> timestamp
- 정답 대상 작업은 success 이고, 정답값/evidence_type/evidence_reference 가 모두 있어야 한다.
- 하나라도 없으면 ValueError (성공 배포 중단). 실행 로그로 증거를 대체하지 않는다.
"""
from __future__ import annotations

from typing import Any

from service.grading import ANSWER_TYPES, parse_iso_utc

_VALUE_FIELD = {"filename": "filename", "filepath": "path", "timestamp": "timestamp"}


def _non_empty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def generate_answer(scenario: dict, result: dict) -> dict:
    """정답 dict {"case_id", "answers": [...]} 를 반환한다. 검증 실패 시 ValueError."""
    if not isinstance(scenario, dict) or not isinstance(result, dict):
        raise ValueError("scenario와 result는 dict여야 합니다.")
    if result.get("status") != "success":
        raise ValueError(result.get("error") or "실행 결과가 success가 아닙니다.")
    case_id = result.get("case_id")
    if not _non_empty(case_id):
        raise ValueError("result.case_id가 비어 있습니다.")

    questions = scenario.get("questions")
    if not isinstance(questions, list) or not questions:
        raise ValueError("scenario.questions가 비어 있습니다.")
    results = result.get("results")
    if not isinstance(results, list) or not results:
        raise ValueError("result.results가 비어 있습니다.")

    by_action: dict = {}
    for entry in results:
        action_id = entry.get("action_id") if isinstance(entry, dict) else None
        if action_id in by_action:
            raise ValueError(f"results에 중복 action_id가 있습니다: {action_id}")
        by_action[action_id] = entry

    answers = []
    for question in questions:
        qid = question.get("id")
        answer_type = question.get("answer_type")
        if answer_type not in ANSWER_TYPES:
            raise ValueError(f"질문 {qid}: 지원하지 않는 answer_type {answer_type!r}")
        entry = by_action.get(question.get("action_id"))
        if entry is None:
            raise ValueError(f"질문 {qid}: 대응하는 실행 결과(action_id)가 없습니다.")
        if entry.get("status") != "success":
            raise ValueError(f"질문 {qid}: 대상 작업이 성공 상태가 아닙니다.")

        expected = entry.get(_VALUE_FIELD[answer_type])
        if not _non_empty(expected):
            raise ValueError(f"질문 {qid}: 정답값({_VALUE_FIELD[answer_type]})이 없습니다.")
        if answer_type == "timestamp":
            parse_iso_utc(expected)  # 시간대 포함 ISO 8601 인지 확인
        if not _non_empty(entry.get("evidence_type")) or not _non_empty(
            entry.get("evidence_reference")
        ):
            raise ValueError(f"질문 {qid}: 실제 증거(evidence_type/reference)가 확인되지 않았습니다.")

        answers.append(
            {
                "question_id": qid,
                "answer_type": answer_type,
                "expected_value": expected,
                "evidence_type": entry["evidence_type"],
                "evidence_reference": entry["evidence_reference"],
            }
        )

    return {"case_id": case_id, "answers": answers}
