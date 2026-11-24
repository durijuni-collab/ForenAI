
import os
import json
import re
from pathlib import Path

from dotenv import load_dotenv

from openai import (
    OpenAI,
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    PermissionDeniedError,
    RateLimitError,
    APIStatusError
)

from ai.scenario_validator import validate_scenario
from ai.question_validator import normalize_questions

from ai.exceptions import (
    AIError,
    AIConfigError,
    AIInputError,
    AIConnectionError,
    AIAuthenticationError,
    AIRateLimitError,
    AIGenerationError
)


ROOT = Path(__file__).resolve().parent.parent

load_dotenv(ROOT / ".env")

MAX_RETRIES = 3
MAX_OBJECTIVE_LENGTH = 1000

ALLOWED_DIFFICULTIES = {
    "easy",
    "medium",
    "hard"
}

REQUIRED_KEYS = {
    "case_title",
    "description",
    "objective",
    "difficulty",
    "actions",
    "questions"
}


# 사용자 입력 검사
def validate_input(objective, difficulty):

    if not isinstance(objective, str):
        raise AIInputError(
            "실습 목표는 문자열이어야 합니다."
        )

    objective = objective.strip()

    if not objective:
        raise AIInputError(
            "실습 목표를 입력해주세요."
        )

    if len(objective) > MAX_OBJECTIVE_LENGTH:
        raise AIInputError(
            f"실습 목표는 {MAX_OBJECTIVE_LENGTH}자 "
            "이하로 입력해주세요."
        )

    if (
        not isinstance(difficulty, str)
        or difficulty not in ALLOWED_DIFFICULTIES
    ):
        raise AIInputError(
            "난이도는 easy, medium, hard 중 "
            "하나여야 합니다."
        )

    # 현재 지원하지 않는 실습 주제
    unsupported = [
        "USB 연결 기록",
        "USB 연결 시각",
        "브라우저 방문 기록",
        "인터넷 방문 기록",
        "레지스트리 수정",
        "악성코드 실행",
        "영구 삭제"
    ]

    normalized_objective = re.sub(
        r"\s+",
        "",
        objective.lower()
    )

    for keyword in unsupported:

        normalized_keyword = re.sub(
            r"\s+",
            "",
            keyword.lower()
        )

        if normalized_keyword in normalized_objective:

            raise AIInputError(
                f"현재 지원하지 않는 실습 주제입니다: "
                f"{keyword}"
            )

    return objective


# API 환경변수 검사
def get_api_config():

    api_key = os.getenv("HAIGPT_API_KEY", "").strip()
    base_url = os.getenv("HAIGPT_BASE_URL", "").strip()
    model = os.getenv("HAIGPT_MODEL", "").strip()

    if not all([api_key, base_url, model]):

        raise AIConfigError(
            "HaiGPT 환경변수가 설정되지 않았습니다."
        )

    if not api_key.isascii():

        raise AIConfigError(
            "API 키에 잘못된 문자가 포함되어 있습니다."
        )

    if any(char.isspace() for char in api_key):

        raise AIConfigError(
            "API 키에 공백이 포함되어 있습니다."
        )

    return api_key, base_url, model


# JSON 데이터 추출
def extract_json(text):

    if not text or not text.strip():

        raise ValueError(
            "AI 응답이 비어 있습니다."
        )

    text = text.strip()

    # 순수 JSON
    try:

        data = json.loads(text)

        if isinstance(data, dict):
            return data

    except json.JSONDecodeError:
        pass

    # 마크다운 및 추가 설명이 포함된 경우
    decoder = json.JSONDecoder()

    for index, char in enumerate(text):

        if char == "{":

            try:

                data, _ = decoder.raw_decode(
                    text[index:]
                )

                if (
                    isinstance(data, dict)
                    and REQUIRED_KEYS.issubset(data)
                ):
                    return data

            except json.JSONDecodeError:
                continue

    raise ValueError(
        "AI 응답에서 올바른 JSON을 찾을 수 없습니다."
    )


# 프롬프트 파일 불러오기
def load_prompt():

    prompt_path = (
        ROOT / "prompts" / "scenario_prompt.md"
    )

    example_path = (
        ROOT / "schemas" / "scenario_example.json"
    )

    try:

        prompt = prompt_path.read_text(
            encoding="utf-8-sig"
        )

        example = example_path.read_text(
            encoding="utf-8-sig"
        )

        example_data = json.loads(example)

        if not isinstance(example_data, dict):
            raise ValueError("JSON 예시는 객체여야 합니다.")

    except (OSError, ValueError) as error:

        raise AIConfigError(
            "프롬프트 또는 JSON 예시 파일을 "
            "확인해주세요."
        ) from error

    return (
        prompt
        + "\n\nJSON 출력 예시:\n"
        + example
        + "\n\n필드 이름을 변경하지 마세요."
        + "\n반드시 JSON 객체만 반환하세요."
        + "\n필수 항목:"
        + "\ncase_title, description, objective,"
        + "\ndifficulty, actions, questions"
    )


# HaiGPT API 호출 및 오류 처리
def request_ai(client, model, messages):

    try:

        response = client.chat.completions.create(
            model=model,
            messages=messages
        )

        if not response.choices:

            raise AIGenerationError(
                "HaiGPT에서 응답을 반환하지 않았습니다."
            )

        return response.choices[0].message.content or ""

    except AuthenticationError:

        raise AIAuthenticationError(
            "HaiGPT API 인증에 실패했습니다. "
            "API 키를 확인해주세요."
        ) from None

    except PermissionDeniedError:

        raise AIAuthenticationError(
            "해당 AI 모델의 사용 권한이 없습니다."
        ) from None

    except RateLimitError:

        raise AIRateLimitError(
            "HaiGPT 사용량 또는 요청 제한을 "
            "초과했습니다."
        ) from None

    except APITimeoutError:

        raise AIConnectionError(
            "HaiGPT 응답 시간이 초과되었습니다."
        ) from None

    except APIConnectionError:

        raise AIConnectionError(
            "HaiGPT 서버에 연결할 수 없습니다."
        ) from None

    except APIStatusError as error:

        raise AIGenerationError(
            f"HaiGPT 요청 실패 "
            f"(HTTP {error.status_code})"
        ) from None


# AI 사건 설계
def generate_scenario(objective, difficulty="easy"):

    objective = validate_input(
        objective,
        difficulty
    )

    api_key, base_url, model = get_api_config()

    system_prompt = load_prompt()

    user_prompt = (
        f"실습 목표: {objective}\n"
        f"난이도: {difficulty}\n\n"
        "지정된 JSON 구조를 그대로 사용하세요.\n"
        "필드 이름을 변경하지 마세요.\n"
        "case_title, description, objective, "
        "difficulty, actions, questions를 "
        "반드시 포함하세요."
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

    with OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=120.0,
        max_retries=0
    ) as client:

        for attempt in range(MAX_RETRIES):

            result = request_ai(
                client,
                model,
                messages
            )

            try:

                scenario = extract_json(result)

                # 상세 유효성 검사
                scenario = validate_scenario(scenario)

                # 요청 난이도와 일치하는지 확인
                if scenario["difficulty"] != difficulty:

                    raise ValueError(
                        "요청한 난이도와 일치하지 않습니다."
                    )

                # 실습 문제 표준화
                scenario = normalize_questions(
                    scenario
                )

                return scenario

            except ValueError as error:

                last_error = error

                messages.append({
                    "role": "assistant",
                    "content": result
                })

                messages.append({
                    "role": "user",
                    "content": (
                        f"이전 응답의 오류: {error}\n"
                        "오류를 수정하여 다시 생성하세요.\n"
                        "정해진 JSON 구조를 유지하세요.\n"
                        f"실습 목표: {objective}\n"
                        f"난이도: {difficulty}\n"
                        "JSON 객체만 반환하세요."
                    )
                })

    raise AIGenerationError(
        f"AI 사건 설계에 {MAX_RETRIES}회 실패했습니다. "
        f"마지막 오류: {last_error}"
    )


# 터미널 실행용
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

    except AIError as error:

        print(f"\n오류 발생: {error}")

        raise SystemExit(1)
