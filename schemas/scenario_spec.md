# AI 사건 설계 데이터 규격

## 1. 데이터 전달 방식

- AI 응답: JSON
- Python 함수 반환값: Dictionary
- 파일 인코딩: UTF-8
- 시간 저장 기준: UTC
- 파일 경로: 지정된 실습 폴더 기준 상대 경로

## 2. 지원 작업

| action | 설명 | 필수 필드 |
|---|---|---|
| create | 파일 생성 | id, path, content |
| copy | 파일 복사 | id, path, destination |
| move | 파일 이동 | id, path, destination |
| rename | 파일 이름 변경 | id, path, destination |
| recycle | 휴지통 이동 | id, path |

## 3. 난이도

- easy: 초급
- medium: 중급
- hard: 고급

## 4. 정답 유형

- filename: 파일 이름
- filepath: 파일 경로
- timestamp: 작업 시각

## 5. 데이터 생성 규칙

- 작업 ID는 중복되지 않아야 한다.
- 작업은 배열에 작성된 순서대로 실행한다.
- 존재하지 않는 파일을 대상으로 작업할 수 없다.
- 실습 폴더 외부의 경로를 사용할 수 없다.
- 절대 경로 및 상위 폴더 접근을 금지한다.
- 문제의 action_id는 실제 작업 ID를 참조해야 한다.
- 실제 작업 시각은 AI가 임의로 생성하지 않는다.
- 정답은 VM 실행 결과 및 실제 증거를 기반으로 생성한다.

## 6. 공통 함수

- generate_scenario(objective, difficulty)
- validate_scenario(scenario)
- execute_scenario(scenario)
- generate_answer(scenario, result)

## 7. 데이터 예시

scenario_example.json 참고