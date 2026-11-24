
from collections import Counter


# 작업별 지원 가능한 정답 유형
SUPPORTED_ANSWER_TYPES = {
    "create": {"filename", "filepath", "timestamp"},
    "copy": {"filename", "filepath"},
    "move": {"filename", "filepath"},
    "rename": {"filename", "filepath"},
    "recycle": {"filename", "filepath", "timestamp"}
}


# 작업별 실습 문제 문장
QUESTION_TEMPLATES = {
    "create": {
        "filename": "생성된 파일의 이름은 무엇인가?",
        "filepath": "생성된 파일의 경로는 무엇인가?",
        "timestamp": "파일이 생성된 시각은 언제인가?"
    },

    "copy": {
        "filename": "복사본 파일의 이름은 무엇인가?",
        "filepath": "복사본 파일의 경로는 무엇인가?"
    },

    "move": {
        "filename": "이동 후 파일의 이름은 무엇인가?",
        "filepath": "이동 후 파일의 경로는 무엇인가?"
    },

    "rename": {
        "filename": "변경 후 파일의 이름은 무엇인가?",
        "filepath": "이름 변경 후 파일의 경로는 무엇인가?"
    },

    "recycle": {
        "filename": "휴지통으로 이동된 파일의 이름은 무엇인가?",
        "filepath": "휴지통으로 이동되기 전 파일의 경로는 무엇인가?",
        "timestamp": "파일이 휴지통으로 이동된 시각은 언제인가?"
    }
}


ACTION_LABELS = {
    "create": "파일 생성",
    "copy": "파일 복사",
    "move": "파일 이동",
    "rename": "파일 이름 변경",
    "recycle": "휴지통 이동"
}


# 문제와 작업 계획의 참조 관계 검사
def validate_question_references(scenario):

    actions = {
        action["id"]: action
        for action in scenario["actions"]
    }

    used_questions = set()

    for question in scenario["questions"]:

        question_id = question["id"]
        action_id = question["action_id"]
        answer_type = question["answer_type"]

        # 참조하는 작업이 존재하는지 검사
        if action_id not in actions:

            raise ValueError(
                f"문제 {question_id}: "
                f"존재하지 않는 작업 ID {action_id}"
            )

        action = actions[action_id]
        action_type = action["action"]

        # 지원하지 않는 작업 검사
        if action_type not in SUPPORTED_ANSWER_TYPES:

            raise ValueError(
                f"지원하지 않는 작업: {action_type}"
            )

        # 작업과 정답 유형의 일치 여부 검사
        if answer_type not in SUPPORTED_ANSWER_TYPES[action_type]:

            raise ValueError(
                f"문제 {question_id}: "
                f"{action_type} 작업에서는 "
                f"{answer_type} 정답 유형을 지원하지 않습니다."
            )

        # 동일한 작업에 대한 중복 문제 검사
        question_key = (action_id, answer_type)

        if question_key in used_questions:

            raise ValueError(
                f"문제 {question_id}: 중복된 실습 문제입니다."
            )

        used_questions.add(question_key)

    return scenario


# 작업 종류에 맞는 표준 문제 생성
def generate_question_text(action_type, answer_type):

    if action_type not in QUESTION_TEMPLATES:
        raise ValueError("지원하지 않는 작업입니다.")

    templates = QUESTION_TEMPLATES[action_type]

    if answer_type not in templates:
        raise ValueError("지원하지 않는 정답 유형입니다.")

    return templates[answer_type]


# 실습 문제 표준화
def normalize_questions(scenario):

    validate_question_references(scenario)

    action_counts = Counter(
        action["action"]
        for action in scenario["actions"]
    )

    action_positions = {}
    current_counts = Counter()

    actions = {}

    for action in scenario["actions"]:

        action_type = action["action"]

        current_counts[action_type] += 1

        action_positions[action["id"]] = (
            current_counts[action_type]
        )

        actions[action["id"]] = action

    for question in scenario["questions"]:

        action_id = question["action_id"]
        answer_type = question["answer_type"]

        action = actions[action_id]
        action_type = action["action"]

        text = generate_question_text(
            action_type,
            answer_type
        )

        # 같은 종류의 작업이 여러 개라면 순서 표시
        if action_counts[action_type] > 1:

            position = action_positions[action_id]
            label = ACTION_LABELS[action_type]

            text = f"{position}번째 {label} 작업: {text}"

        question["question"] = text

    return scenario
