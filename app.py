from flask import Flask, request, jsonify
import requests
import random
import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

app = Flask(__name__)

# Mattermost 설정
MATTERMOST_TOKEN = os.getenv('MATTERMOST_TOKEN', 'nptcwj16efyddc1xct6s5ckq7a')
WEATHER_API_KEY = os.getenv('WEATHER_API_KEY', '')  # OpenWeatherMap API 키
GIPHY_API_KEY = os.getenv('GIPHY_API_KEY', '')  # Giphy API 키
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyBFbRNnt6xNdWvV6RGrra5RdLt15N3byNw')  # Gemini API 키

# Gemini AI 설정
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # 최신 Gemini 모델 사용
    gemini_model = genai.GenerativeModel('models/gemini-2.5-flash')

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
    if command == '!날씨':
        return handle_weather(data)
    elif command == '!번역':
        return handle_translate(data)
    elif command == '!점심':
        return handle_lunch(data)
    elif command == '!주사위':
        return handle_dice(data)
    elif command == '!gif':
        return handle_gif(data)
    elif command == '!help':
        return handle_help(data)
    elif text.startswith('?'):
        # ? 로 시작하는 질문은 Gemini AI로 처리
        return handle_gemini(data)

    return jsonify({"text": "알 수 없는 명령어입니다. !help를 입력하여 도움말을 확인하세요."}), 200


def handle_weather(data):
    """날씨 정보 조회"""
    text = data.get('text', '').strip()
    parts = text.split(maxsplit=1)

    if len(parts) < 2:
        return jsonify({
            "text": "사용법: !날씨 [도시명]\n예시: !날씨 서울"
        }), 200

    city = parts[1]

    if not WEATHER_API_KEY:
        return jsonify({
            "text": "날씨 API 키가 설정되지 않았습니다."
        }), 200

    try:
        # OpenWeatherMap API 호출
        url = f"http://api.openweathermap.org/data/2.5/weather"
        params = {
            'q': city,
            'appid': WEATHER_API_KEY,
            'units': 'metric',
            'lang': 'kr'
        }
        response = requests.get(url, params=params, timeout=5)

        if response.status_code == 200:
            weather_data = response.json()
            temp = weather_data['main']['temp']
            feels_like = weather_data['main']['feels_like']
            description = weather_data['weather'][0]['description']
            humidity = weather_data['main']['humidity']

            message = f"🌤️ **{city} 날씨 정보**\n"
            message += f"- 기온: {temp}°C (체감: {feels_like}°C)\n"
            message += f"- 날씨: {description}\n"
            message += f"- 습도: {humidity}%"

            return jsonify({"text": message, "response_type": "in_channel"}), 200
        else:
            return jsonify({
                "text": f"날씨 정보를 가져올 수 없습니다. 도시명을 확인해주세요."
            }), 200
    except Exception as e:
        return jsonify({
            "text": f"오류가 발생했습니다: {str(e)}"
        }), 200


def handle_translate(data):
    """번역 기능 (간단한 예시)"""
    text = data.get('text', '').strip()
    parts = text.split(maxsplit=1)

    if len(parts) < 2:
        return jsonify({
            "text": "사용법: !번역 [텍스트]\n예시: !번역 Hello World"
        }), 200

    to_translate = parts[1]

    # 실제 번역 API를 사용하려면 Google Translate API 등을 연동해야 합니다
    # 여기서는 간단한 데모용 응답만 제공
    return jsonify({
        "text": f"🌐 번역 요청: '{to_translate}'\n\n번역 기능을 사용하려면 Google Translate API 또는 Papago API를 연동해주세요."
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


def handle_gif(data):
    """GIF 검색"""
    text = data.get('text', '').strip()
    parts = text.split(maxsplit=1)

    if len(parts) < 2:
        return jsonify({
            "text": "사용법: !gif [검색어]\n예시: !gif 고양이"
        }), 200

    search_term = parts[1]

    if not GIPHY_API_KEY:
        return jsonify({
            "text": "GIF 검색을 위한 Giphy API 키가 설정되지 않았습니다."
        }), 200

    try:
        # Giphy API 호출
        url = "https://api.giphy.com/v1/gifs/search"
        params = {
            'api_key': GIPHY_API_KEY,
            'q': search_term,
            'limit': 1,
            'rating': 'g'
        }
        response = requests.get(url, params=params, timeout=5)

        if response.status_code == 200:
            data_response = response.json()
            if data_response['data']:
                gif_url = data_response['data'][0]['images']['original']['url']
                return jsonify({
                    "text": f"🎬 **{search_term}** GIF\n{gif_url}",
                    "response_type": "in_channel"
                }), 200
            else:
                return jsonify({
                    "text": f"'{search_term}'에 대한 GIF를 찾을 수 없습니다."
                }), 200
        else:
            return jsonify({
                "text": "GIF 검색 중 오류가 발생했습니다."
            }), 200
    except Exception as e:
        return jsonify({
            "text": f"오류가 발생했습니다: {str(e)}"
        }), 200


def handle_gemini(data):
    """Gemini AI를 사용한 질문 응답"""
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

    try:
        # Gemini AI에 질문 전송
        response = gemini_model.generate_content(question)

        if response.text:
            return jsonify({
                "text": f"🤖 **Gemini AI**\n\n{response.text}",
                "response_type": "in_channel"
            }), 200
        else:
            return jsonify({
                "text": "답변을 생성할 수 없습니다."
            }), 200
    except Exception as e:
        return jsonify({
            "text": f"오류가 발생했습니다: {str(e)}"
        }), 200


def handle_help(data):
    """도움말"""
    help_text = """
📖 **Mattermost Bot 도움말**

**사용 가능한 명령어:**
- `!날씨 [도시명]` - 날씨 정보 조회
- `!번역 [텍스트]` - 번역 (API 연동 필요)
- `!점심` - 점심 메뉴 랜덤 추천
- `!주사위 [면 수]` - 주사위 굴리기 (기본 6면)
- `!gif [검색어]` - GIF 검색
- `?[질문내용]` - Gemini AI에게 질문하기
- `!help` - 이 도움말 보기

**예시:**
- `!날씨 서울`
- `!번역 Hello World`
- `!점심`
- `!주사위 20`
- `!gif 고양이`
- `?파이썬에서 리스트와 튜플의 차이는?`
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
    app.run(host='0.0.0.0', port=5000, debug=True)
