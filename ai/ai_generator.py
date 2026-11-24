import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

API_KEY = os.getenv("HAIGPT_API_KEY")
BASE_URL = os.getenv("HAIGPT_BASE_URL")
MODEL = os.getenv("HAIGPT_MODEL")


def test_connection():
    if not all([API_KEY, BASE_URL, MODEL]):
        raise ValueError("HaiGPT 환경변수를 확인해주세요.")

    client = OpenAI(
        api_key=API_KEY,
        base_url=BASE_URL
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": "디지털 포렌식에 대해 간단히 설명해줘."
            }
        ]
    )

    return response.choices[0].message.content


if __name__ == "__main__":
    print(test_connection())