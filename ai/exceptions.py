
class AIError(Exception):
    """AI 기능의 기본 오류"""
    pass


class AIConfigError(AIError):
    """환경변수 및 API 설정 오류"""
    pass


class AIInputError(AIError):
    """사용자 입력 오류"""
    pass


class AIConnectionError(AIError):
    """API 서버 연결 오류"""
    pass


class AIAuthenticationError(AIError):
    """API 인증 오류"""
    pass


class AIRateLimitError(AIError):
    """API 사용량 제한 오류"""
    pass


class AIGenerationError(AIError):
    """AI 사건 생성 오류"""
    pass
