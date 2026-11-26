"""service/mock_backend.py - A/B 모듈이 없을 때만 쓰는 임시 mock (C 개발용)

주의: 이 파일의 결과는 실제 AI 계획/VM 실행/디스크 증거가 아니다.
app.py 는 mock 사용 시 화면에 반드시 경고를 표시한다.
A/B 코드가 develop 에 병합되면 app.py 의 import 가 자동으로 실제 함수를 사용한다.
"""
from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

_EXAMPLE = Path(__file__).resolve().parents[1] / "schemas" / "scenario_example.json"


def mock_generate_scenario(objective: str, difficulty: str = "easy") -> dict:
    scenario = json.loads(_EXAMPLE.read_text(encoding="utf-8"))
    scenario = deepcopy(scenario)
    scenario["objective"] = objective or scenario["objective"]
    scenario["difficulty"] = difficulty
    return scenario


def mock_validate_scenario(scenario: dict) -> dict:
    for field in ("case_title", "description", "objective", "difficulty", "actions", "questions"):
        if not scenario.get(field):
            raise ValueError(f"[mock 검증] 필수 필드가 비어 있습니다: {field}")
    return scenario


def mock_execute_scenario(scenario: dict) -> dict:
    """가짜 증거 파일을 만들고 명세서 5장 구조의 결과 dict 를 반환한다. (실제 증거 아님)"""
    now = datetime.now(timezone.utc)
    case_id = f"mock_{now:%Y%m%d%H%M%S}"
    out_root = os.environ.get("OUTPUT_DIR", "outputs")
    raw = Path(out_root) / case_id / "evidence.raw"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_bytes(b"MOCK EVIDENCE - NOT A REAL DISK IMAGE")
    sha256 = hashlib.sha256(raw.read_bytes()).hexdigest()

    results = []
    for action in scenario["actions"]:
        is_recycle = action["action"] == "recycle"
        results.append(
            {
                "action_id": action["id"],
                "action": action["action"],
                "filename": Path(action.get("destination") or action["path"]).name,
                "path": action.get("destination") or action["path"],
                "destination": action.get("destination"),
                "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ") if is_recycle else None,
                "status": "success",
                "evidence_type": "recycle_bin" if is_recycle else None,
                "evidence_reference": "MOCK:$Recycle.Bin/(mock)" if is_recycle else None,
            }
        )
    return {
        "case_id": case_id,
        "status": "success",
        "results": results,
        "evidence_path": raw.as_posix(),
        "sha256": sha256,
        "error": None,
    }
