from ai.scenario_validator import validate_scenario
import os
import json
from pathlib import Path


from dotenv import load_dotenv
from openai import OpenAI


# 프로젝트 최상위 경로
ROOT = Path(__file__).resolve().parent.parent

# 환경변수 불러오기
load_dotenv(ROOT / ".env")

API_KEY = os.getenv("HAIGPT_API_KEY")
BASE_URL = os.getenv("HAIGPT_BASE_URL")
MODEL = os.getenv("HAIGPT_MODEL")

MAX_RETRIES = 3

REQUIRED_KEYS = {
    "case_title",
    "description",
    "objective",
    "difficulty",
    "actions",
    "questions"
}


# AI 응답에서 JSON 추출
def extract_json(text):

    if not text or not text.strip():
        raise ValueError("AI 응답이 비어 있습니다.")

    text = text.strip()

    # 순수 JSON인 경우
    try:
        data = json.loads(text)

        if isinstance(data, dict):
            return data

    except json.JSONDecodeError:
        pass

    # 마크다운 또는 설명이 포함된 경우
    decoder = json.JSONDecoder()

    for index, char in enumerate(text):

        if char == "{":

            try:
                data, _ = decoder.raw_decode(text[index:])

                if isinstance(data, dict):
                    return data

            except json.JSONDecodeError:
                continue

    raise ValueError("AI 응답에서 JSON을 찾을 수 없습니다.")


# 기본 JSON 구조 검사
def validate_basic_structure(scenario, difficulty):

    missing_keys = REQUIRED_KEYS - scenario.keys()

    if missing_keys:
        raise ValueError(
            f"필수 항목 누락: {', '.join(sorted(missing_keys))}"
        )

    for key in ["case_title", "description", "objective"]:

        if not isinstance(scenario[key], str):
            raise ValueError(f"{key}는 문자열이어야 합니다.")

        if not scenario[key].strip():
            raise ValueError(f"{key}가 비어 있습니다.")

    if scenario["difficulty"] != difficulty:
        raise ValueError("요청한 난이도와 일치하지 않습니다.")

    if not isinstance(scenario["actions"], list):
        raise ValueError("actions는 리스트여야 합니다.")

    if not scenario["actions"]:
        raise ValueError("작업 목록이 비어 있습니다.")

    if not isinstance(scenario["questions"], list):
        raise ValueError("questions는 리스트여야 합니다.")

    if not scenario["questions"]:
        raise ValueError("실습 문제 목록이 비어 있습니다.")

    for action in scenario["actions"]:

        if not isinstance(action, dict):
            raise ValueError("각 작업은 JSON 객체여야 합니다.")

        if not {"id", "action", "path"}.issubset(action):
            raise ValueError("작업의 필수 항목이 누락되었습니다.")

    for question in scenario["questions"]:

        if not isinstance(question, dict):
            raise ValueError("각 문제는 JSON 객체여야 합니다.")

        if not {
            "id",
            "question",
            "answer_type",
            "action_id"
        }.issubset(question):

            raise ValueError("실습 문제의 필수 항목이 누락되었습니다.")

    return scenario


# AI 사건 설계 함수
def generate_scenario(objective, difficulty="easy"):

    # 환경변수 확인
    if not all([API_KEY, BASE_URL, MODEL]):
        raise ValueError("HaiGPT 환경변수를 확인해주세요.")

    if not API_KEY.isascii():
        raise ValueError("API 키에 잘못된 문자가 포함되어 있습니다.")

    # 사용자 입력 확인
    if not objective.strip():
        raise ValueError("실습 목표를 입력해주세요.")

    if difficulty not in ["easy", "medium", "hard"]:
        raise ValueError("올바른 난이도를 입력해주세요.")

    # HaiGPT API 연결
    client = OpenAI(
        api_key=API_KEY,
        base_url=BASE_URL,
        timeout=120.0
    )

    # 프롬프트 파일 불러오기
    prompt = (
        ROOT / "prompts" / "scenario_prompt.md"
    ).read_text(encoding="utf-8")

    # JSON 예시 파일 불러오기
    example = (
        ROOT / "schemas" / "scenario_example.json"
    ).read_text(encoding="utf-8")

    # 시스템 프롬프트 구성
    system_prompt = (
        prompt
        + "\n\n===== JSON 출력 예시 =====\n"
        + example
        + "\n\n===== 필수 출력 규칙 =====\n"
        + "반드시 예시와 동일한 JSON 구조를 사용하세요.\n"
        + "필드 이름을 변경하지 마세요.\n"
        + "case_title, description, objective, difficulty, "
        + "actions, questions를 반드시 포함하세요.\n"
        + "title, tasks, hint, answer_format은 사용하지 마세요.\n"
        + "actions에는 실행 가능한 작업 객체를 작성하세요.\n"
        + "questions에는 실습 문제 객체를 작성하세요.\n"
        + "JSON 외의 설명은 출력하지 마세요."
    )

    # 사용자 프롬프트 구성
    user_prompt = (
        f"실습 목표: {objective}\n"
        f"난이도: {difficulty}\n\n"
        "위 실습 목표를 기반으로 디지털 포렌식 사건을 설계하세요.\n"
        "시스템 프롬프트의 JSON 구조를 그대로 사용하세요.\n"
        "case_title, description, objective, difficulty, "
        "actions, questions를 반드시 포함하세요.\n"
        "필드 이름을 변경하지 마세요.\n"
        "유효한 JSON 객체만 반환하세요."
    )

    messages = [
        {
            "role": "system",
            "content": system_prompt
        },
        {
            "role": "user",
            "content": user_prompt
        }
    ]

    last_error = None

    # 최대 3회 생성 시도
    for attempt in range(MAX_RETRIES):

        print(
            f"\nAI 사건 생성 중... "
            f"({attempt + 1}/{MAX_RETRIES})"
        )

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages
        )

        result = response.choices[0].message.content or ""

        try:

            # JSON 데이터 추출
            scenario = extract_json(result)

            # 기본 데이터 구조 검사
            scenario = validate_basic_structure(
                scenario,
                difficulty
            )
            # 상세 유효성 검사
            scenario = validate_scenario(scenario)


            return scenario

        except ValueError as error:

            last_error = error

            print(f"\nJSON 검증 실패: {error}")

            print("\n===== AI 원본 응답 =====")
            print(result)
            print("========================")

            # 이전 AI 응답 저장
            messages.append({
                "role": "assistant",
                "content": result
            })

            # 잘못된 부분을 수정하도록 요청
            messages.append({
                "role": "user",
                "content": (
                    f"이전 응답에 다음 문제가 있습니다: {error}\n\n"
                    "아래 JSON 예시와 동일한 필드 이름 및 "
                    "데이터 구조를 사용하여 다시 생성하세요.\n\n"
                    + example
                    + "\n\n실습 목표: "
                    + objective
                    + "\n난이도: "
                    + difficulty
                    + "\nJSON 객체만 반환하세요."
                )
            })

    raise ValueError(
        f"AI 사건 설계 생성에 실패했습니다: {last_error}"
    )


# 직접 실행할 경우
if __name__ == "__main__":

    print("===== ForenAI 사건 설계 시스템 =====")

    objective = input("\n실습 목표를 입력하세요: ")

    try:

        scenario = generate_scenario(
            objective,
            difficulty="easy"
        )

        print("\n===== AI 사건 설계 결과 =====")

        print(
            json.dumps(
                scenario,
                ensure_ascii=False,
                indent=4
            )
        )

        print("\nAI 사건 설계 성공!")

    except Exception as error:

        print(f"\n오류 발생: {error}")

        raise SystemExit(1)
