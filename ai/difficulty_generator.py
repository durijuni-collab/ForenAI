
# 난이도별 생성 기준
DIFFICULTY_RULES = {
    "easy": {
        "file_count": 3,
        "min_actions": 4,
        "max_actions": 5,
        "question_count": 2,
        "min_noise": 0,
        "max_noise": 0
    },
    "medium": {
        "file_count": 5,
        "min_actions": 7,
        "max_actions": 10,
        "question_count": 3,
        "min_noise": 1,
        "max_noise": 2
    },
    "hard": {
        "file_count": 7,
        "min_actions": 11,
        "max_actions": 15,
        "question_count": 4,
        "min_noise": 3,
        "max_noise": 4
    }
}


# 난이도별 설정 반환
def get_difficulty_rules(difficulty):

    if difficulty not in DIFFICULTY_RULES:
        raise ValueError("지원하지 않는 난이도입니다.")

    return DIFFICULTY_RULES[difficulty].copy()


# 난이도별 생성 결과 검사
def validate_difficulty(scenario, difficulty):

    rules = get_difficulty_rules(difficulty)

    if scenario["difficulty"] != difficulty:
        raise ValueError("요청한 난이도와 일치하지 않습니다.")

    actions = scenario["actions"]
    questions = scenario["questions"]

    file_count = sum(
        action["action"] == "create"
        for action in actions
    )

    if file_count != rules["file_count"]:
        raise ValueError(
            f"파일 생성 작업은 {rules['file_count']}개여야 합니다. "
            f"현재: {file_count}개"
        )

    action_count = len(actions)

    if not (
        rules["min_actions"]
        <= action_count
        <= rules["max_actions"]
    ):
        raise ValueError(
            f"전체 작업 수는 "
            f"{rules['min_actions']}~{rules['max_actions']}개여야 합니다. "
            f"현재: {action_count}개"
        )

    question_count = len(questions)

    if question_count != rules["question_count"]:
        raise ValueError(
            f"실습 문제는 {rules['question_count']}개여야 합니다. "
            f"현재: {question_count}개"
        )

    return scenario


# 난이도별 프롬프트 생성
def build_difficulty_prompt(difficulty):

    rules = get_difficulty_rules(difficulty)

    return (
        f"난이도: {difficulty}\n"
        f"파일 생성 작업: 정확히 {rules['file_count']}개\n"
        f"전체 작업: {rules['min_actions']}~"
        f"{rules['max_actions']}개\n"
        f"실습 문제: 정확히 {rules['question_count']}개\n"
        f"무관한 정상 작업: {rules['min_noise']}~"
        f"{rules['max_noise']}개\n"
        "사용자의 학습 목표를 유지하세요.\n"
        "파일명과 파일 내용을 다양하게 생성하세요.\n"
        "기존 JSON 필드명은 변경하지 마세요."
    )


# 난이도별 사건 생성
def generate_variant(objective, difficulty="easy"):

    from ai.ai_generator import generate_scenario

    return generate_scenario(objective, difficulty)
