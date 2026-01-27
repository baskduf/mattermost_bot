from flask import Flask, request, jsonify
import requests
import random
import os
import threading
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
import google.generativeai as genai

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

import re
import time
from playwright.sync_api import sync_playwright

load_dotenv()

# 한국 시간대 (UTC+9)
KST = timezone(timedelta(hours=9))

app = Flask(__name__)

# Mattermost 설정
MATTERMOST_TOKEN = os.getenv('MATTERMOST_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')  # Gemini API 키
MATTERMOST_INCOMING_WEBHOOK = os.getenv('MATTERMOST_INCOMING_WEBHOOK')

# SSAFY 로그인 설정
SSAFY_USER_ID = os.getenv('SSAFY_USER_ID')
SSAFY_USER_PW = os.getenv('SSAFY_USER_PW')

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

# 점심 메뉴 API 설정
LUNCH_API_URL = "https://m.planeatchoice.net/v2/portal/dailyMenu"
LUNCH_API_PARAMS = {
    "listType": "card",
    "busiCd": "RH3_K_001",
    "compCd": "K_KR_011",
    "storCd": "CAF38",
    "mealCd": "2"
}


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
        return handle_meal(data, '2', '점심')
    elif command == '!저녁':
        return handle_meal(data, '3', '저녁')
    elif command == '!주사위':
        return handle_dice(data)
    elif command == '!사다리':
        return handle_ladder(data)
    elif command == '!요약':
        return handle_summary(data)
    elif command == '!코드':
        return handle_code_review(data)
    elif command == '!취업':
        return handle_job(data)
    elif command == '!수업':
        return handle_class(data, today_only=True)
    elif command == '!이번주수업':
        return handle_class(data, today_only=False)
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


def fetch_meal_menu(date_str=None, meal_cd='2'):
    """외부 API에서 식단 메뉴 가져오기 (meal_cd: 2=점심, 3=저녁)"""
    if not date_str:
        date_str = datetime.now(KST).strftime('%Y-%m-%d')

    url = f"https://m.planeatchoice.net/v2/portal/dailyMenu?listType=card&saleDt={date_str}&busiCd=RH3_K_001&compCd=K_KR_011&storCd=CAF38&mealCd={meal_cd}"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        menus = []
        for item in data.get('ds', []):
            corner = item.get('cnrNm', '')
            menu_name = item.get('itemNmDp', '')
            calories = item.get('totCalorie', 0)
            sold_out = item.get('soldOutYn', 'N') == 'Y'

            # 이미지 URL (숨김 플래그 확인)
            image_url = None
            if item.get('hidePictureYn', 'N') != 'Y' and item.get('fileUpload'):
                image_url = item['fileUpload'][0].get('url', '').replace('http://planeatchoice.net/', 'https://m.planeatchoice.net/')

            # 반찬 목록 (숨김 플래그 확인)
            side_dishes = []
            if item.get('hideSubMenuYn', 'N') != 'Y':
                for sub in item.get('dailySubMenuDtos', []):
                    side_dishes.append({
                        'name': sub.get('subItemNmDp', ''),
                        'calories': sub.get('calorie', 0)
                    })

            # 테이크아웃 이용안내 같은 항목 제외
            if menu_name and '이용안내' not in menu_name:
                menus.append({
                    'corner': corner,
                    'name': menu_name,
                    'calories': calories,
                    'sold_out': sold_out,
                    'image': image_url,
                    'side_dishes': side_dishes
                })

        return menus
    except Exception as e:
        print(f"Error fetching meal menu: {e}")
        return None


def handle_meal(data, meal_cd, meal_name):
    """식단 메뉴 조회 (점심/저녁 통합)"""
    text = data.get('text', '').strip()
    parts = text.split()

    # 날짜 파싱 (MM-DD 또는 YYYY-MM-DD 형식)
    date_str = None
    if len(parts) > 1:
        date_input = parts[1]
        try:
            if len(date_input) <= 5:  # MM-DD 형식
                year = datetime.now(KST).year
                date_str = f"{year}-{date_input}"
            else:
                date_str = date_input
            # 날짜 형식 검증
            datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({
                "text": f"⚠️ 날짜 형식이 올바르지 않습니다.\n\n**사용법:** `!{meal_name}` 또는 `!{meal_name} 01-20`"
            }), 200

    menus = fetch_meal_menu(date_str, meal_cd)

    if menus is None:
        return jsonify({
            "text": f"❌ {meal_name} 메뉴를 가져오는데 실패했습니다."
        }), 200

    if not menus:
        display_date = date_str or datetime.now(KST).strftime('%Y-%m-%d')
        return jsonify({
            "text": f"📭 **{display_date}** {meal_name} 메뉴가 없습니다."
        }), 200

    # 메뉴 포맷팅
    display_date = date_str or datetime.now(KST).strftime('%Y-%m-%d')
    emoji = "🍽️" if meal_cd == '2' else "🌙"
    menu_text = f"## {emoji} {display_date} {meal_name} 메뉴\n\n"
    menu_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    # 코너별로 그룹화
    corners = {}
    for menu in menus:
        corner = menu['corner']
        if corner not in corners:
            corners[corner] = []
        corners[corner].append(menu)

    attachments = []
    for corner, items in corners.items():
        menu_text += f"### 📍 {corner}\n"
        for item in items:
            sold_out_mark = " ~~(품절)~~" if item['sold_out'] else ""
            menu_text += f"- **{item['name']}**{sold_out_mark} ({item['calories']}kcal)\n"
            # 반찬 목록
            if item.get('side_dishes'):
                side_names = ', '.join(sub['name'] for sub in item['side_dishes'])
                menu_text += f"  - 반찬: {side_names}\n"
            # 이미지를 attachment로 추가
            if item.get('image'):
                attachments.append({
                    "title": f"{corner} - {item['name']}",
                    "image_url": item['image']
                })
        menu_text += "\n"

    menu_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    menu_text += f"💡 다른 날짜 조회: `!{meal_name} 01-20`"

    response = {
        "text": menu_text,
        "response_type": "in_channel"
    }
    if attachments:
        response["attachments"] = attachments

    return jsonify(response), 200


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


def crawl_linkareer_jobs():
    """링커리어에서 IT/인터넷 인턴 채용 정보 크롤링"""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-images")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    chrome_options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.page_load_strategy = 'eager'

    driver = webdriver.Chrome(options=chrome_options)

    try:
        url = "https://linkareer.com/list/intern?filterBy_activityTypeID=5&filterBy_categoryIDs=58&filterBy_jobTypes=INTERN&filterBy_status=OPEN&orderBy_direction=DESC&orderBy_field=RECENT&page=1"
        driver.get(url)

        wait = WebDriverWait(driver, 20)
        # 채용 링크가 최소 1개 이상 나타날 때까지 대기
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a.recruit-link")))
        # 추가 로딩을 위해 잠시 대기
        import time
        time.sleep(2)

        links = driver.find_elements(By.CSS_SELECTOR, "a.recruit-link")
        if not links:
            links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/activity/']")

        results = []
        for link in links:
            try:
                href = link.get_attribute("href")
                text = link.text.strip()

                if not href or "/activity/" not in href:
                    continue

                lines = text.split('\n')
                title = lines[0] if lines else "제목 없음"
                category = lines[1] if len(lines) > 1 else ""

                results.append({
                    "title": title,
                    "category": category,
                    "link": href
                })

                if len(results) >= 10:
                    break
            except Exception:
                continue

        return results

    finally:
        driver.quit()


def fetch_job_info():
    """백그라운드에서 채용 정보 크롤링 후 Incoming Webhook으로 전송"""
    try:
        results = crawl_linkareer_jobs()

        if not results:
            send_to_incoming_webhook("❌ 채용 정보를 가져오지 못했습니다.")
            return

        job_text = "## 💼 IT/인터넷 인턴 채용 정보\n\n"
        job_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        for i, item in enumerate(results, 1):
            job_text += f"**{i}. [{item['title']}]({item['link']})**\n"
            if item['category']:
                job_text += f"   📂 {item['category']}\n"
            job_text += "\n"

        job_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        job_text += f"🔗 [링커리어에서 더보기](https://linkareer.com/list/intern?filterBy_categoryIDs=58&filterBy_status=OPEN)"

        send_to_incoming_webhook(job_text)

    except Exception as e:
        error_msg = str(e)
        print(f"Job crawling error: {error_msg}")
        if "Chrome" in error_msg or "chromedriver" in error_msg.lower():
            send_to_incoming_webhook("❌ 서버에 Chrome이 설치되어 있지 않습니다. 관리자에게 문의하세요.")
        else:
            send_to_incoming_webhook(f"❌ 채용 정보 크롤링 오류: {error_msg}")


def handle_job(data):
    """취업 정보 조회 기능"""
    thread = threading.Thread(target=fetch_job_info)
    thread.start()

    return jsonify({
        "text": "⏳ **IT/인터넷 인턴 채용 정보를 가져오는 중입니다...**\n\n크롤링에 시간이 걸릴 수 있습니다.",
        "response_type": "in_channel"
    }), 200


def crawl_ssafy_curriculum():
    """SSAFY에서 이번 주 커리큘럼 정보 크롤링 (Playwright 사용)"""
    base_url = "https://edu.ssafy.com"
    login_btn = "#wrap > div > div > div.section > form > div > div.field-set.log-in > div.form-btn > a"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        try:
            # 1. 로그인
            page.goto(f"{base_url}/comm/login/SecurityLoginForm.do")
            page.fill("#userId", SSAFY_USER_ID)
            page.fill("#userPwd", SSAFY_USER_PW)
            page.click(login_btn)

            # 2. 로딩 대기
            page.wait_for_load_state("networkidle")
            time.sleep(2)

            # 3. 팝업 정리
            for p_obj in context.pages[1:]:
                p_obj.close()

            # 4. 커리큘럼 추출
            curriculum = []
            selector = "ul.course > li"

            try:
                page.wait_for_selector(selector, timeout=10000)
                day_elements = page.query_selector_all(selector)

                for el in day_elements:
                    day_info = {}

                    # 날짜
                    date_el = el.query_selector('span.date')
                    if date_el:
                        day_info['date'] = date_el.inner_text().strip()

                    # 오늘 여부
                    if 'today' in (el.get_attribute('class') or ''):
                        day_info['is_today'] = True

                    # 시간
                    time_el = el.query_selector('dt')
                    if time_el:
                        day_info['time'] = time_el.inner_text().strip()

                    # 카테고리
                    cate_el = el.query_selector('span.cate')
                    if cate_el:
                        day_info['category'] = cate_el.inner_text().strip()

                    # 과목명
                    course_el = el.query_selector('span.course-name')
                    if course_el:
                        day_info['course'] = course_el.inner_text().strip()

                    # 세부 주제
                    subj_el = el.query_selector('span.subj')
                    if subj_el:
                        day_info['subject'] = subj_el.inner_text().strip()

                    # 강사명
                    name_el = el.query_selector('span.name')
                    if name_el:
                        day_info['instructor'] = name_el.inner_text().strip()

                    # 강의실
                    room_el = el.query_selector('span.class-room')
                    if room_el:
                        day_info['room'] = room_el.inner_text().strip()

                    # 라이브/다시보기 URL
                    live_el = el.query_selector('.liveDirect')
                    if live_el:
                        day_info['live_url'] = live_el.get_attribute('data-req')

                    # 교재 ID
                    matl_el = el.query_selector("[onclick*='fnMatlPopup']")
                    if matl_el:
                        onclick = matl_el.get_attribute('onclick')
                        match = re.search(r"fnMatlPopup\('(\d+)'\)", onclick)
                        if match:
                            day_info['material_id'] = match.group(1)

                    if day_info:
                        curriculum.append(day_info)

            except Exception as e:
                print(f"커리큘럼 추출 중 오류: {e}")

            return curriculum

        finally:
            browser.close()


def fetch_ssafy_curriculum(today_only=False):
    """백그라운드에서 SSAFY 커리큘럼 크롤링 후 Incoming Webhook으로 전송"""
    try:
        curriculum = crawl_ssafy_curriculum()

        if not curriculum:
            send_to_incoming_webhook("❌ 수업 정보를 가져오지 못했습니다.")
            return

        # 오늘 수업만 필터링
        if today_only:
            curriculum = [day for day in curriculum if day.get('is_today')]
            if not curriculum:
                send_to_incoming_webhook("📭 오늘은 수업이 없습니다.")
                return
            title = "📚 오늘의 SSAFY 수업"
        else:
            title = "📚 이번 주 SSAFY 수업 일정"

        class_text = f"## {title}\n\n"
        class_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        for day in curriculum:
            today_mark = " ⭐**오늘**" if day.get('is_today') else ""
            class_text += f"### 📅 {day.get('date', '날짜없음')}{today_mark}\n"
            class_text += f"- **시간:** {day.get('time', '-')}\n"
            class_text += f"- **분류:** {day.get('category', '-')}\n"
            class_text += f"- **과목:** {day.get('course', '-')} - {day.get('subject', '-')}\n"
            class_text += f"- **강사:** {day.get('instructor', '-')} | **강의실:** {day.get('room', '-')}\n"

            if day.get('live_url'):
                class_text += f"- 🎬 [다시보기]({day['live_url']})\n"
            if day.get('material_id'):
                material_url = f"https://edu.ssafy.com/edu/lectureroom/openlearning/mainMatlPopup.do?clssAcctoTmtbSeq={day['material_id']}"
                class_text += f"- 📖 [교재]({material_url})\n"

            class_text += "\n"

        class_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        class_text += "💡 (교재링크는 수시로 변경되오니 재발급 해주세요)"

        send_to_incoming_webhook(class_text)

    except Exception as e:
        error_msg = str(e)
        print(f"SSAFY crawling error: {error_msg}")
        if "playwright" in error_msg.lower():
            send_to_incoming_webhook("❌ 서버에 Playwright가 설치되어 있지 않습니다. 관리자에게 문의하세요.")
        else:
            send_to_incoming_webhook(f"❌ 수업 정보 크롤링 오류: {error_msg}")


def handle_class(data, today_only=False):
    """SSAFY 수업 일정 조회 기능"""
    if not SSAFY_USER_ID or not SSAFY_USER_PW:
        return jsonify({
            "text": "❌ SSAFY 계정 정보가 설정되지 않았습니다."
        }), 200

    thread = threading.Thread(target=fetch_ssafy_curriculum, args=(today_only,))
    thread.start()

    msg = "오늘 수업" if today_only else "이번 주 수업"
    return jsonify({
        "text": f"⏳ **SSAFY {msg} 정보를 가져오는 중입니다...**\n\n로그인 및 크롤링에 시간이 걸릴 수 있습니다.",
        "response_type": "in_channel"
    }), 200


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

### 🍽️ 식단 & 재미
| 명령어 | 설명 |
|:------|:-----|
| `!점심` | 오늘 구미 식단 조회 |
| `!점심 01-20` | 특정 날짜 식단 |
| `!주사위 [N]` | N면 주사위 (기본 6) |
| `!사다리 [이름들] [결과들]` | 사다리 타기 |

### 💼 취업 정보
| 명령어 | 설명 |
|:------|:-----|
| `!취업` | IT/인터넷 인턴 채용 정보 |

### 📚 SSAFY
| 명령어 | 설명 |
|:------|:-----|
| `!수업` | 오늘 수업 일정 조회 |
| `!이번주수업` | 이번 주 전체 수업 조회 |

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### 📌 사용 예시
```
?파이썬 데코레이터가 뭐야?
!요약 오늘 배운거: 리스트컴프리헨션, 제너레이터...
!코드 def add(a,b): return a+b
!번역 Hello World
!점심 01-20
!사다리 [철수,영희,민수] [당첨,꽝,꽝]
!취업
!수업
!이번주수업
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
