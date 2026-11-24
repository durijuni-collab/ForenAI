
import re


# 지원하는 파일 작업
ALLOWED_ACTIONS = {
    "create",
    "copy",
    "move",
    "rename",
    "recycle"
}

# 지원하는 난이도
ALLOWED_DIFFICULTIES = {
    "easy",
    "medium",
    "hard"
}

# 지원하는 정답 유형
ALLOWED_ANSWER_TYPES = {
    "filename",
    "filepath",
    "timestamp"
}

# 필수 사건 정보
REQUIRED_KEYS = {
    "case_title",
    "description",
    "objective",
    "difficulty",
    "actions",
    "questions"
}

# Windows 예약 파일명
RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5",
    "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5",
    "LPT6", "LPT7", "LPT8", "LPT9",
    "COM¹", "COM²", "COM³",
    "LPT¹", "LPT²", "LPT³",
    "CONIN$", "CONOUT$"
}


# 양의 정수 검사
def validate_id(value, label):

    if type(value) is not int or value <= 0:
        raise ValueError(
            f"{label}는 양의 정수여야 합니다."
        )


# 파일 경로 검사
def validate_path(path):

    if not isinstance(path, str) or not path.strip():
        raise ValueError("파일 경로가 비어 있거나 잘못되었습니다.")

    if path.startswith(("/", "\\")):
        raise ValueError(f"절대 경로 사용 금지: {path}")

    if "\\" in path:
        raise ValueError(
            f"경로 구분자는 /를 사용해야 합니다: {path}"
        )

    if re.search(r'[<>:"|?*\x00-\x1f]', path):
        raise ValueError(f"허용되지 않는 경로 문자: {path}")

    parts = path.split("/")

    for part in parts:

        if part in ("", ".", ".."):
            raise ValueError(f"잘못된 상대 경로: {path}")

        if part != part.strip() or part.endswith("."):
            raise ValueError(
                f"잘못된 파일 또는 폴더 이름: {part}"
            )

        name = part.split(".")[0].rstrip().upper()

        if name in RESERVED_NAMES:
            raise ValueError(
                f"Windows 예약 이름 사용 금지: {part}"
            )

    # 이번 프로젝트의 실습 파일 형식
    if not path.lower().endswith(".txt"):
        raise ValueError(
            f"현재는 .txt 파일만 지원합니다: {path}"
        )

    return path.casefold()


# 파일 생성 및 목적지 충돌 검사
def check_destination(path, existing_files, directories):

    if path in existing_files:
        raise ValueError(
            f"이미 존재하는 파일입니다: {path}"
        )

    if path in directories:
        raise ValueError(
            f"폴더와 파일 경로가 충돌합니다: {path}"
        )

    parts = path.split("/")

    for index in range(1, len(parts)):

        parent = "/".join(parts[:index])

        if parent in existing_files:
            raise ValueError(
                f"상위 경로가 파일과 충돌합니다: {parent}"
            )


# 생성될 상위 폴더 기록
def register_directories(path, directories):

    parts = path.split("/")

    for index in range(1, len(parts)):
        directories.add("/".join(parts[:index]))


# 사건 기본 정보 검사
def validate_metadata(scenario):

    if not isinstance(scenario, dict):
        raise ValueError("사건 데이터는 Dictionary여야 합니다.")

    missing_keys = REQUIRED_KEYS - scenario.keys()

    if missing_keys:
        raise ValueError(
            f"필수 항목 누락: {sorted(missing_keys)}"
        )

    for key in ["case_title", "description", "objective"]:

        value = scenario[key]

        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"{key}는 비어 있지 않은 문자열이어야 합니다."
            )

    difficulty = scenario["difficulty"]

    if (
        not isinstance(difficulty, str)
        or difficulty not in ALLOWED_DIFFICULTIES
    ):
        raise ValueError("잘못된 난이도입니다.")

    for key in ["actions", "questions"]:

        if not isinstance(scenario[key], list):
            raise ValueError(f"{key}는 리스트여야 합니다.")

        if not scenario[key]:
            raise ValueError(f"{key}가 비어 있습니다.")


# 파일 작업 목록 검사
def validate_actions(actions):

    action_ids = set()

    # 가상 파일 상태
    existing_files = set()
    directories = set()

    for item in actions:

        if not isinstance(item, dict):
            raise ValueError(
                "각 작업은 Dictionary여야 합니다."
            )

        required = {"id", "action", "path"}

        if not required.issubset(item):
            raise ValueError("파일 작업의 필수 항목이 누락되었습니다.")

        action_id = item["id"]
        action = item["action"]

        validate_id(action_id, "작업 ID")

        if action_id in action_ids:
            raise ValueError(
                f"중복된 작업 ID: {action_id}"
            )

        action_ids.add(action_id)

        if (
            not isinstance(action, str)
            or action not in ALLOWED_ACTIONS
        ):
            raise ValueError(
                f"지원하지 않는 작업: {action}"
            )

        path = validate_path(item["path"])

        # 파일 생성
        if action == "create":

            if "content" not in item:
                raise ValueError(
                    f"작업 {action_id}: content 누락"
                )

            if not isinstance(item["content"], str):
                raise ValueError(
                    f"작업 {action_id}: content는 문자열이어야 합니다."
                )

            check_destination(
                path,
                existing_files,
                directories
            )

            register_directories(path, directories)

            existing_files.add(path)

        # 파일 복사, 이동, 이름 변경
        elif action in {"copy", "move", "rename"}:

            if path not in existing_files:
                raise ValueError(
                    f"존재하지 않는 원본 파일: {path}"
                )

            if "destination" not in item:
                raise ValueError(
                    f"작업 {action_id}: destination 누락"
                )

            destination = validate_path(
                item["destination"]
            )

            if path == destination:
                raise ValueError(
                    "원본과 목적지 경로가 동일합니다."
                )

            check_destination(
                destination,
                existing_files,
                directories
            )

            # rename은 동일 폴더에서만 허용
            if action == "rename":

                source_parent = path.rpartition("/")[0]

                destination_parent = (
                    destination.rpartition("/")[0]
                )

                if source_parent != destination_parent:
                    raise ValueError(
                        "rename은 같은 폴더에서만 가능합니다."
                    )

            register_directories(
                destination,
                directories
            )

            # move와 rename은 원본 제거
            if action in {"move", "rename"}:
                existing_files.remove(path)

            # copy는 원본을 유지하고 목적지 추가
            existing_files.add(destination)

        # 휴지통 이동
        elif action == "recycle":

            if path not in existing_files:
                raise ValueError(
                    f"휴지통으로 이동할 파일이 없습니다: {path}"
                )

            existing_files.remove(path)

    return action_ids


# 실습 문제 검사
def validate_questions(questions, action_ids):

    question_ids = set()

    for question in questions:

        if not isinstance(question, dict):
            raise ValueError(
                "각 문제는 Dictionary여야 합니다."
            )

        required = {
            "id",
            "question",
            "answer_type",
            "action_id"
        }

        if not required.issubset(question):
            raise ValueError(
                "실습 문제의 필수 항목이 누락되었습니다."
            )

        question_id = question["id"]
        action_id = question["action_id"]

        validate_id(question_id, "문제 ID")
        validate_id(action_id, "참조 작업 ID")

        if question_id in question_ids:
            raise ValueError(
                f"중복된 문제 ID: {question_id}"
            )

        question_ids.add(question_id)

        text = question["question"]

        if not isinstance(text, str) or not text.strip():
            raise ValueError("문제 내용이 비어 있습니다.")

        answer_type = question["answer_type"]

        if (
            not isinstance(answer_type, str)
            or answer_type not in ALLOWED_ANSWER_TYPES
        ):
            raise ValueError(
                f"지원하지 않는 정답 유형: {answer_type}"
            )

        if action_id not in action_ids:
            raise ValueError(
                f"존재하지 않는 작업 참조: {action_id}"
            )


# 전체 사건 유효성 검사
def validate_scenario(scenario):

    validate_metadata(scenario)

    action_ids = validate_actions(
        scenario["actions"]
    )

    validate_questions(
        scenario["questions"],
        action_ids
    )

    return scenario
