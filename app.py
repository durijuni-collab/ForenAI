"""app.py - ForenAI Streamlit 서비스 (C 담당)

실행: streamlit run app.py
호출 순서는 명세서 6장 그대로:
generate_scenario -> validate_scenario -> execute_scenario(내부에서 collect_evidence)
-> generate_answer -> generate_package
A/B 모듈이 없으면 service/mock_backend.py 의 mock 을 쓰고, 화면에 경고를 표시한다.
"""
from __future__ import annotations

import json
import os
from datetime import timedelta, timezone
from pathlib import Path

import streamlit as st

from service.answer_generator import generate_answer
from service.grading import grade_answer, parse_iso_utc
from service.package_generator import generate_package

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "outputs")
KST = timezone(timedelta(hours=9))  # UI 시각은 KST로 표시 (명세서 5장)

# ---------------------------------------------------------------- A/B 모듈 로드
MOCK_NOTES: list[str] = []
try:
    from ai.ai_generator import generate_scenario
    from ai.scenario_validator import validate_scenario
except ImportError as exc:
    from service.mock_backend import mock_generate_scenario as generate_scenario
    from service.mock_backend import mock_validate_scenario as validate_scenario

    MOCK_NOTES.append(f"A(AI) 모듈을 불러오지 못해 mock 사용 중: {exc}")

try:
    from forensic.vm_controller import execute_scenario
except ImportError as exc:
    from service.mock_backend import mock_execute_scenario as execute_scenario

    MOCK_NOTES.append(f"B(포렌식) 모듈을 불러오지 못해 mock 사용 중: {exc}")

try:  # 선택 기능: Autopsy MCP 어댑터 (B 구현, 12/5까지)
    from mcp_tools.autopsy_connector import query_evidence
except ImportError:
    query_evidence = None

STATUS_LABEL = {"verified": "검증됨", "not_found": "일치 기록 없음", "unavailable": "미검증(연결 불가)"}


# ---------------------------------------------------------------- 보조 함수
def to_kst(iso_text: str) -> str:
    try:
        return parse_iso_utc(iso_text).astimezone(KST).strftime("%Y-%m-%d %H:%M:%S KST")
    except ValueError:
        return iso_text


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def list_cases() -> list[str]:
    root = Path(OUTPUT_DIR)
    if not root.is_dir():
        return []
    return sorted(
        p.name
        for p in root.iterdir()
        if (p / "student" / "questions.json").is_file() and (p / "teacher" / "answers.json").is_file()
    )


def run_pipeline(objective: str, difficulty: str, progress) -> dict:
    progress("1/5 사건 계획 생성 중")
    scenario = generate_scenario(objective, difficulty)
    progress("2/5 계획 검증 중")
    scenario = validate_scenario(scenario)
    progress("3/5 VM 실행 및 증거 수집 중")
    result = execute_scenario(scenario)
    if result["status"] != "success":
        raise RuntimeError(result["error"] or "VM 작업 실패")
    progress("4/5 정답 생성 중")
    answer = generate_answer(scenario, result)
    progress("5/5 자료 패키지 생성 중")
    packages = generate_package(scenario, result)
    return {"scenario": scenario, "result": result, "answer": answer, "packages": packages}


def verify_with_mcp(case_id: str, answer: dict, student: dict):
    """원본 근거 조회. 연결이 없으면 '미검증'으로 돌려준다 (mock 을 성공으로 위장하지 않는다)."""
    if query_evidence is None:
        return {"status": "unavailable", "records": [], "error": "Autopsy MCP 어댑터가 연결되지 않았습니다."}
    types = {a["question_id"]: a["answer_type"] for a in answer["answers"]}
    path = ts = None
    for item in student["answers"]:
        kind = types.get(item["question_id"])
        if kind in ("filename", "filepath") and path is None:
            path = item["submitted_value"]
        if kind == "timestamp" and ts is None:
            ts = item["submitted_value"]
    if not path:
        return None
    try:
        return query_evidence(case_id, path, ts)
    except Exception as exc:  # noqa: BLE001 - 연결 실패는 미검증으로 표시
        return {"status": "unavailable", "records": [], "error": str(exc)}


# ---------------------------------------------------------------- 화면
st.set_page_config(page_title="ForenAI", layout="wide")
st.title("ForenAI - AI 디지털 포렌식 실습 케이스 생성기")
for note in MOCK_NOTES:
    st.warning(f"MOCK 모드: {note}. 이 자료는 실제 증거가 아닙니다.")

menu = st.sidebar.radio("메뉴", ["1. 사건 생성", "2. 생성 결과", "3. 채점", "4. 사건 이력"])


def page_create():
    st.subheader("사건 생성")
    objective = st.text_area("실습 목표", placeholder="예: 삭제된 파일명과 이동 시각 확인")
    difficulty = st.selectbox("난이도", ["easy", "medium", "hard"])
    if st.button("사건 생성", type="primary"):
        if not objective.strip():
            st.error("실습 목표를 입력하세요.")
            return
        status = st.empty()
        try:
            st.session_state["case"] = run_pipeline(objective.strip(), difficulty, status.info)
            status.success("생성 완료. '2. 생성 결과' 메뉴에서 확인하세요.")
        except Exception as exc:  # noqa: BLE001 - 모든 실패는 오류로 표시하고 배포 중단
            st.session_state.pop("case", None)
            status.empty()
            st.error(f"사건 생성 실패 (자료 배포 중단): {exc}")


def page_result():
    case = st.session_state.get("case")
    if not case:
        st.info("먼저 '1. 사건 생성'에서 사건을 만드세요.")
        return
    scenario, result, answer = case["scenario"], case["result"], case["answer"]
    st.subheader(f"{scenario['case_title']}  (case_id: {result['case_id']})")
    st.write(scenario["description"])
    st.caption(f"목표: {scenario['objective']} / 난이도: {scenario['difficulty']}")

    st.markdown("#### 문제 목록")
    for q in scenario["questions"]:
        st.write(f"{q['id']}. {q['question']}")

    st.markdown("#### 교수용 정답지")
    rows = []
    for a in answer["answers"]:
        value = a["expected_value"]
        shown = f"{value}  ({to_kst(value)})" if a["answer_type"] == "timestamp" else value
        rows.append({"문제": a["question_id"], "유형": a["answer_type"], "정답": shown,
                     "근거 종류": a["evidence_type"], "근거 식별자": a["evidence_reference"]})
    st.dataframe(rows, use_container_width=True)

    st.markdown("#### 증거 정보 (교수용)")
    st.code(f"경로: {result['evidence_path']}\nSHA-256: {result['sha256']}")

    col1, col2 = st.columns(2)
    for col, label, key, name in (
        (col1, "학생용 ZIP 다운로드", "student_zip", "student_case.zip"),
        (col2, "교수용 ZIP 다운로드", "teacher_zip", "teacher_answer.zip"),
    ):
        data = Path(case["packages"][key]).read_bytes()
        col.download_button(label, data=data, file_name=name, mime="application/zip")
    st.caption("학생에게는 학생용 ZIP만 배포하세요.")


def page_grade():
    cases = list_cases()
    if not cases:
        st.info("채점할 사건이 없습니다. 먼저 사건을 생성하세요.")
        return
    case_id = st.selectbox("사건 선택", cases)
    root = Path(OUTPUT_DIR) / case_id
    questions = read_json(root / "student" / "questions.json")
    answer = read_json(root / "teacher" / "answers.json")

    st.subheader(f"학생 답안 입력 - {questions['case_title']}")
    st.caption("시각은 시간대가 포함된 ISO 8601로 입력 (예: 2026-11-24T09:30:15Z 또는 2026-11-24T18:30:15+09:00)")
    items = []
    for q in questions["questions"]:
        st.markdown(f"**{q['id']}. {q['question']}**")
        key = f"{case_id}_{q['id']}"
        value = st.text_input("답", key=f"{key}_v")
        etype = st.text_input("근거 종류 (evidence_type)", key=f"{key}_t")
        eref = st.text_input("근거 식별자 (evidence_reference)", key=f"{key}_r")
        items.append({"question_id": q["id"], "submitted_value": value,
                      "evidence_type": etype, "evidence_reference": eref})

    if st.button("채점", type="primary"):
        student = {"case_id": case_id, "answers": items}
        try:
            graded = grade_answer(student, answer)
        except ValueError as exc:
            st.error(f"채점 입력 오류: {exc}")
            return
        st.metric("총점", f"{graded['total_score']:.2f} / {graded['max_score']}")
        st.dataframe(graded["items"], use_container_width=True)

        mcp = verify_with_mcp(case_id, answer, student)
        if mcp is not None:
            st.markdown("#### 원본 근거 조회 (Autopsy MCP)")
            st.write(f"상태: {STATUS_LABEL.get(mcp['status'], mcp['status'])}")
            if mcp.get("error"):
                st.caption(mcp["error"])
            if mcp.get("records"):
                st.dataframe(mcp["records"], use_container_width=True)


def page_history():
    st.subheader("사건 이력")
    cases = list_cases()
    if not cases:
        st.info("생성된 사건이 없습니다.")
        return
    for cid in cases:
        info = read_json(Path(OUTPUT_DIR) / cid / "student" / "questions.json")
        st.write(f"- {cid}: {info['case_title']} ({info['difficulty']})")


{"1. 사건 생성": page_create, "2. 생성 결과": page_result,
 "3. 채점": page_grade, "4. 사건 이력": page_history}[menu]()
