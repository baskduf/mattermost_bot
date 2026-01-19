from flask import Flask, request, jsonify
import requests
import random
import os
import threading
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

app = Flask(__name__)

# Mattermost 설정
MATTERMOST_TOKEN = os.getenv('MATTERMOST_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')  # Gemini API 키
MATTERMOST_INCOMING_WEBHOOK = os.getenv('MATTERMOST_INCOMING_WEBHOOK')

# Gemini AI 설정
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # 무료 티어에서 가장 많이 사용 가능한 모델
    gemini_model = genai.GenerativeModel(
        'gemini-2.5-flash-lite',
        generation_config={
            'max_output_tokens': 300,  # 더 짧게 조정하여 응답 속도 향상
            'temperature': 0.5,        # 일관된 답변을 위해 온도를 조금 낮춤
        },
        system_instruction="너는 SSAFY의 Mattermost 챗봇이야. 친절하지만 아주 짧고 명확하게 답변해. 한글 위주로 답변하고, 3문장 이내로 요약해줘."
    )

# 점심 메뉴 리스트
LUNCH_MENU = [
    "🍜 라면", "🍕 피자", "🍔 햄버거", "🍱 도시락",
    "🍛 카레", "🍝 스파게티", "🥗 샐러드", "🍗 치킨",
    "🍣 초밥", "🥙 랩", "🌮 타코", "🍲 찌개",
    "🥘 비빔밥", "🍜 우동", "🍖 갈비", "🥩 스테이크"
]


def send_mattermost_response(response_url, text):
    """Mattermost에 응답 전송"""
    payload = {
        "text": text,
        "response_type": "in_channel"
    }
    try:
        requests.post(response_url, json=payload)
    except Exception as e:
        print(f"Error sending response: {e}")


@app.route('/webhook', methods=['POST'])
def webhook():
    """메인 웹훅 엔드포인트"""
    print("=" * 50)
    print("Webhook received!")
    print(f"Request method: {request.method}")
    print(f"Request headers: {dict(request.headers)}")
    print(f"Request form data: {request.form.to_dict()}")
    print("=" * 50)

    data = request.form.to_dict()

    # 토큰 검증
    token = data.get('token', '')
    print(f"Received token: {token}")
    print(f"Expected token: {MATTERMOST_TOKEN}")
    if token != MATTERMOST_TOKEN:
        print("Token validation failed!")
        return jsonify({"error": "Invalid token"}), 403

    text = data.get('text', '').strip()
    command = text.split()[0] if text else ''
    print(f"Received text: {text}")
    print(f"Parsed command: {command}")

    # 트리거 단어 확인
    if command == '!번역':
        return handle_translate(data)
    elif command == '!점심':
        return handle_lunch(data)
    elif command == '!주사위':
        return handle_dice(data)
    elif command == '!사다리':
        return handle_ladder(data)
    elif command == '!요약':
        return handle_summary(data)
    elif command == '!코드':
        return handle_code_review(data)
    elif command == '!help':
        return handle_help(data)
    elif text.startswith('?'):
        # ? 로 시작하는 질문은 Gemini AI로 처리
        return handle_gemini(data)

    return jsonify({"text": "알 수 없는 명령어입니다. !help를 입력하여 도움말을 확인하세요."}), 200


def generate_summary(content):
    """백그라운드에서 Gemini로 요약 후 Incoming Webhook으로 전송"""
    try:
        prompt = f"""다음 강의 내용/메모를 깔끔하게 정리해줘.

규칙:
- 핵심 내용을 bullet point로 정리
- 중요한 개념은 **굵게** 표시
- 불필요한 내용은 제거하고 핵심만
- 이해하기 쉽게 다듬어줘

내용:
{content}"""
        response = gemini_model.generate_content(prompt)
        if response.text:
            send_to_incoming_webhook(f"📝 **요약 결과**\n\n{response.text}")
        else:
            send_to_incoming_webhook("❌ 요약을 생성할 수 없습니다.")
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg:
            send_to_incoming_webhook("⚠️ 현재 요청이 너무 많아 잠시 쉬고 있습니다. 1분 후 다시 시도해주세요! 🙏")
        else:
            send_to_incoming_webhook(f"❌ 요약 오류: {error_msg}")


def handle_summary(data):
    """강의 내용 요약 기능"""
    text = data.get('text', '').strip()
    parts = text.split(maxsplit=1)

    if len(parts) < 2:
        return jsonify({
            "text": "📝 **사용법:** `!요약 [내용]`\n\n**예시:**\n`!요약 오늘 배운 내용: 파이썬 리스트 컴프리헨션, 제너레이터, 데코레이터...`"
        }), 200

    content = parts[1]

    if not GEMINI_API_KEY:
        return jsonify({"text": "Gemini API 키가 설정되지 않았습니다."}), 200

    thread = threading.Thread(target=generate_summary, args=(content,))
    thread.start()

    return jsonify({
        "text": "⏳ **내용을 정리하고 있습니다...**",
        "response_type": "in_channel"
    }), 200


def generate_code_review(code):
    """백그라운드에서 Gemini로 코드 리뷰 후 Incoming Webhook으로 전송"""
    try:
        prompt = f"""다음 코드를 리뷰해줘.

분석 항목:
1. **점수**: 100점 만점 (가독성, 효율성, 안전성 종합)
2. **잘한 점**: 좋은 부분 간단히
3. **개선 제안**: 더 나은 방법이 있다면 코드와 함께
4. **한줄평**: 전체적인 평가

코드:
```
{code}
```"""
        response = gemini_model.generate_content(prompt)
        if response.text:
            send_to_incoming_webhook(f"💻 **코드 리뷰 결과**\n\n{response.text}")
        else:
            send_to_incoming_webhook("❌ 코드 리뷰를 생성할 수 없습니다.")
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg:
            send_to_incoming_webhook("⚠️ 현재 요청이 너무 많아 잠시 쉬고 있습니다. 1분 후 다시 시도해주세요! 🙏")
        else:
            send_to_incoming_webhook(f"❌ 코드 리뷰 오류: {error_msg}")


def handle_code_review(data):
    """코드 리뷰 기능"""
    text = data.get('text', '').strip()
    parts = text.split(maxsplit=1)

    if len(parts) < 2:
        return jsonify({
            "text": "💻 **사용법:** `!코드 [코드]`\n\n**예시:**\n`!코드 def hello(): print('hello')`"
        }), 200

    code = parts[1]

    if not GEMINI_API_KEY:
        return jsonify({"text": "Gemini API 키가 설정되지 않았습니다."}), 200

    thread = threading.Thread(target=generate_code_review, args=(code,))
    thread.start()

    return jsonify({
        "text": "⏳ **코드를 분석하고 있습니다...**",
        "response_type": "in_channel"
    }), 200


def generate_translation(to_translate):
    """백그라운드에서 Gemini로 번역 후 Incoming Webhook으로 전송"""
    try:
        prompt = f"다음 텍스트를 번역해줘. 영어면 한국어로, 한국어면 영어로 번역해. 번역 결과만 출력해:\n\n{to_translate}"
        response = gemini_model.generate_content(prompt)
        if response.text:
            send_to_incoming_webhook(f"🌐 **번역 결과**\n\n**원문:** {to_translate}\n\n**번역:** {response.text}")
        else:
            send_to_incoming_webhook("❌ 번역을 생성할 수 없습니다.")
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg:
            send_to_incoming_webhook("⚠️ 현재 요청이 너무 많아 잠시 쉬고 있습니다. 1분 후 다시 시도해주세요! 🙏")
        else:
            send_to_incoming_webhook(f"❌ 번역 오류: {error_msg}")


def handle_translate(data):
    """번역 기능 (Gemini AI 사용)"""
    text = data.get('text', '').strip()
    parts = text.split(maxsplit=1)

    if len(parts) < 2:
        return jsonify({
            "text": "사용법: !번역 [텍스트]\n예시: !번역 Hello World"
        }), 200

    to_translate = parts[1]

    if not GEMINI_API_KEY:
        return jsonify({
            "text": "Gemini API 키가 설정되지 않았습니다."
        }), 200

    # 백그라운드 스레드에서 번역 실행
    thread = threading.Thread(target=generate_translation, args=(to_translate,))
    thread.start()

    return jsonify({
        "text": f"⏳ **번역 중입니다...**\n\n원문: {to_translate}",
        "response_type": "in_channel"
    }), 200


def handle_lunch(data):
    """점심 메뉴 추천"""
    menu = random.choice(LUNCH_MENU)
    return jsonify({
        "text": f"🍽️ **오늘의 점심 메뉴 추천**\n\n{menu}",
        "response_type": "in_channel"
    }), 200


def handle_dice(data):
    """주사위 굴리기"""
    text = data.get('text', '').strip()
    parts = text.split()

    # 기본값: 6면 주사위
    sides = 6

    if len(parts) > 1:
        try:
            sides = int(parts[1])
            if sides < 2 or sides > 100:
                sides = 6
        except ValueError:
            sides = 6

    result = random.randint(1, sides)
    return jsonify({
        "text": f"🎲 주사위 결과: **{result}** (1~{sides})",
        "response_type": "in_channel"
    }), 200


def handle_ladder(data):
    """사다리 게임"""
    import re
    text = data.get('text', '').strip()

    # [참가자들] [결과들] 형식 파싱
    pattern = r'!사다리\s+\[([^\]]+)\]\s+\[([^\]]+)\]'
    match = re.match(pattern, text)

    if not match:
        return jsonify({
            "text": "사용법: !사다리 [참가자1,참가자2,...] [결과1,결과2,...]\n예시: !사다리 [최원빈,김채운] [당첨,꽝]"
        }), 200

    participants = [p.strip() for p in match.group(1).split(',')]
    results = [r.strip() for r in match.group(2).split(',')]

    if len(participants) != len(results):
        return jsonify({
            "text": "⚠️ 참가자 수와 결과 수가 일치해야 합니다!"
        }), 200

    if len(participants) < 2:
        return jsonify({
            "text": "⚠️ 최소 2명 이상의 참가자가 필요합니다!"
        }), 200

    # 결과를 랜덤하게 섞기
    shuffled_results = results.copy()
    random.shuffle(shuffled_results)

    # 사다리 UI 생성
    num = len(participants)

    # 헤더 (참가자 이름)
    max_name_len = max(len(p) for p in participants)
    col_width = max(max_name_len, 6) + 2

    ladder_ui = "🪜 **사다리 게임 결과**\n\n"
    ladder_ui += "```\n"

    # 참가자 이름 출력
    header = ""
    for p in participants:
        header += p.center(col_width)
    ladder_ui += header + "\n"

    # 시작선
    ladder_ui += "  " + ("┃" + " " * (col_width - 2)) * num + "\n"

    # 사다리 본체 (랜덤 가로선)
    for row in range(5):
        line = "  "
        for i in range(num):
            if i < num - 1 and random.random() > 0.5:
                line += "┃" + "━" * (col_width - 2)
            else:
                line += "┃" + " " * (col_width - 2)
        line += "\n"
        ladder_ui += line

    # 끝선
    ladder_ui += "  " + ("┃" + " " * (col_width - 2)) * num + "\n"

    # 결과 출력
    result_line = ""
    for r in shuffled_results:
        result_line += r.center(col_width)
    ladder_ui += result_line + "\n"
    ladder_ui += "```\n\n"

    # 매칭 결과
    ladder_ui += "📋 **매칭 결과**\n"
    for i, (p, r) in enumerate(zip(participants, shuffled_results)):
        emoji = "🎉" if "당첨" in r or "승" in r else "👤"
        ladder_ui += f"{emoji} **{p}** → {r}\n"

    return jsonify({
        "text": ladder_ui,
        "response_type": "in_channel"
    }), 200


def send_to_incoming_webhook(text):
    """Incoming Webhook으로 메시지 전송"""
    payload = {"text": text}
    try:
        requests.post(MATTERMOST_INCOMING_WEBHOOK, json=payload)
    except Exception as e:
        print(f"Error sending to incoming webhook: {e}")


def generate_gemini_response(question):
    """백그라운드에서 Gemini 응답 생성 후 Incoming Webhook으로 전송"""
    try:
        response = gemini_model.generate_content(question)
        if response.text:
            send_to_incoming_webhook(f"🤖 **Gemini AI**\n\n**질문:** {question}\n\n**답변:**\n{response.text}")
        else:
            send_to_incoming_webhook("❌ 답변을 생성할 수 없습니다.")
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg:
            send_to_incoming_webhook("⚠️ 현재 질문이 너무 많아 잠시 쉬고 있습니다. 1분 후 다시 시도해주세요! 🙏")
        else:
            send_to_incoming_webhook(f"❌ 오류가 발생했습니다: {error_msg}")


def handle_gemini(data):
    """Gemini AI를 사용한 질문 응답 (비동기)"""
    text = data.get('text', '').strip()

    # ? 제거하고 질문 추출
    question = text[1:].strip() if text.startswith('?') else text

    if not question:
        return jsonify({
            "text": "사용법: ?질문내용\n예시: ?파이썬에서 리스트와 튜플의 차이는?"
        }), 200

    if not GEMINI_API_KEY:
        return jsonify({
            "text": "Gemini API 키가 설정되지 않았습니다."
        }), 200

    # 백그라운드 스레드에서 Gemini 응답 생성
    thread = threading.Thread(target=generate_gemini_response, args=(question,))
    thread.start()

    # 즉시 응답 반환
    return jsonify({
        "text": f"⏳ **AI 답변을 생성중입니다...**\n\n질문: {question}",
        "response_type": "in_channel"
    }), 200


def handle_help(data):
    """도움말"""
    help_text = """
## 🤖 SSAFY Bot 도움말

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### 🧠 AI 기능
| 명령어 | 설명 |
|:------|:-----|
| `?질문` | AI에게 질문하기 |
| `!요약 내용` | 강의/메모 내용 정리 |
| `!코드 코드` | 코드 리뷰 & 점수 |
| `!번역 텍스트` | 영↔한 번역 |

### 🎮 재미 기능
| 명령어 | 설명 |
|:------|:-----|
| `!점심` | 오늘 뭐 먹지? 🍽️ |
| `!주사위 [N]` | N면 주사위 (기본 6) |
| `!사다리 [이름들] [결과들]` | 사다리 타기 |

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### 📌 사용 예시
```
?파이썬 데코레이터가 뭐야?
!요약 오늘 배운거: 리스트컴프리헨션, 제너레이터...
!코드 def add(a,b): return a+b
!번역 Hello World
!사다리 [철수,영희,민수] [당첨,꽝,꽝]
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 **Tip:** AI 기능은 응답에 몇 초 걸릴 수 있어요!
"""
    return jsonify({
        "text": help_text,
        "response_type": "in_channel"
    }), 200


@app.route('/health', methods=['GET'])
def health():
    """헬스 체크 엔드포인트"""
    return jsonify({"status": "ok"}), 200


if __name__ == '__main__':
    # Get port from environment variable (Elastic Beanstalk uses 8080)
    port = int(os.getenv('PORT', 5000))
    # Disable debug in production
    debug = os.getenv('FLASK_ENV', 'production') != 'production'
    app.run(host='0.0.0.0', port=port, debug=debug)
