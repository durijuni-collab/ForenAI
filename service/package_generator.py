"""service/package_generator.py - 학생용/교수용 자료 패키지 생성 (C 담당)

명세서 7장 기준 저장 구조 (경로는 프로젝트 루트 기준 상대 경로)
outputs/{case_id}/
  scenario.json, execution_result.json, evidence.raw
  student/questions.json, teacher/answers.json
  student_case.zip, teacher_answer.zip

- 학생 ZIP : student/questions.json + evidence.raw 만 포함
- 교수 ZIP : teacher/answers.json + scenario.json + execution_result.json
- 정답/작업 계획/실행 결과는 학생 ZIP에 절대 넣지 않는다.
- 유효한 이미지(파일 존재, 64자리 SHA-256 일치)가 없으면 배포 자료를 만들지 않는다.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import zipfile
from pathlib import Path

from service.answer_generator import generate_answer

_CASE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _student_questions(scenario: dict, case_id: str) -> dict:
    for field in ("case_title", "description", "objective", "difficulty"):
        if not isinstance(scenario.get(field), str) or not scenario[field].strip():
            raise ValueError(f"scenario.{field}가 비어 있습니다.")
    questions = scenario.get("questions")
    if not isinstance(questions, list) or not questions:
        raise ValueError("scenario.questions가 비어 있습니다.")
    return {
        "case_id": case_id,
        "case_title": scenario["case_title"],
        "description": scenario["description"],
        "objective": scenario["objective"],
        "difficulty": scenario["difficulty"],
        # 학생에게는 id와 question 문장만 제공 (answer_type, action_id 제외)
        "questions": [{"id": q["id"], "question": q["question"]} for q in questions],
    }


def generate_package(
    scenario: dict,
    result: dict,
    output_dir: str | None = None,
    base_dir: str | os.PathLike = ".",
    verify_hash: bool = True,
) -> dict:
    """학생/교수 ZIP을 만들고 {"student_zip", "teacher_zip"} (상대 경로)을 반환한다.

    검증 실패는 ValueError. 실패하면 ZIP을 만들지 않는다.
    """
    # 1) 검증 (파일을 쓰기 전에 모두 끝낸다)
    answer = generate_answer(scenario, result)  # 증거 없으면 여기서 예외
    case_id = result["case_id"]
    if not _CASE_ID_RE.fullmatch(case_id):
        raise ValueError(f"안전하지 않은 case_id 입니다: {case_id!r}")

    base = Path(base_dir).resolve()
    out_root = output_dir or os.environ.get("OUTPUT_DIR", "outputs")
    case_dir = base / out_root / case_id

    sha256 = result.get("sha256")
    if not isinstance(sha256, str) or not _SHA256_RE.fullmatch(sha256):
        raise ValueError("유효한 64자리 SHA-256이 없습니다.")

    evidence_rel = result.get("evidence_path")
    if not isinstance(evidence_rel, str) or not evidence_rel.strip():
        raise ValueError("result.evidence_path가 비어 있습니다.")
    evidence_src = (base / evidence_rel).resolve()
    if not evidence_src.is_relative_to(base):
        raise ValueError("evidence_path가 프로젝트 루트 밖을 가리킵니다.")
    if not evidence_src.is_file():
        raise ValueError(f"증거 이미지 파일이 없습니다: {evidence_rel}")
    if verify_hash and _sha256_of(evidence_src).lower() != sha256.lower():
        raise ValueError("증거 이미지의 SHA-256이 실행 결과와 일치하지 않습니다.")

    student_questions = _student_questions(scenario, case_id)

    # 2) 산출물 저장
    case_dir.mkdir(parents=True, exist_ok=True)
    evidence_dst = case_dir / "evidence.raw"
    if evidence_src != evidence_dst.resolve():
        shutil.copyfile(evidence_src, evidence_dst)

    _write_json(case_dir / "scenario.json", scenario)
    _write_json(case_dir / "execution_result.json", result)
    _write_json(case_dir / "student" / "questions.json", student_questions)
    _write_json(case_dir / "teacher" / "answers.json", answer)

    # 3) ZIP 생성 (학생 / 교수 분리)
    student_zip = case_dir / "student_case.zip"
    with zipfile.ZipFile(student_zip, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(case_dir / "student" / "questions.json", "student/questions.json")
        archive.write(evidence_dst, "evidence.raw")

    teacher_zip = case_dir / "teacher_answer.zip"
    with zipfile.ZipFile(teacher_zip, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(case_dir / "teacher" / "answers.json", "teacher/answers.json")
        archive.write(case_dir / "scenario.json", "scenario.json")
        archive.write(case_dir / "execution_result.json", "execution_result.json")

    return {
        "student_zip": student_zip.relative_to(base).as_posix(),
        "teacher_zip": teacher_zip.relative_to(base).as_posix(),
    }
