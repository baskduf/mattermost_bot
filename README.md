# Mattermost Bot (Flask)

Mattermost의 Outgoing Webhook을 사용한 Flask 기반 봇 애플리케이션입니다.

## 기능

이 봇은 다음과 같은 기능을 제공합니다:

- **!날씨 [도시명]** - 특정 도시의 날씨 정보 조회
- **!번역 [텍스트]** - 텍스트 번역 (API 연동 필요)
- **!점심** - 랜덤 점심 메뉴 추천
- **!주사위 [면 수]** - 주사위 굴리기 (기본 6면)
- **!gif [검색어]** - GIF 이미지 검색
- **?[질문내용]** - Gemini AI에게 질문하기
- **!help** - 도움말 표시

## 설치 방법

### 1. 필수 요구사항

- Python 3.8 이상
- pip

### 2. 패키지 설치

```bash
cd mattermost_bot
pip install -r requirements.txt
```

### 3. 환경 변수 설정

프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 다음 내용을 추가합니다:

```env
# Mattermost 토큰
MATTERMOST_TOKEN=your_mattermost_token_here

# OpenWeatherMap API 키 (날씨 기능용)
WEATHER_API_KEY=your_openweathermap_api_key

# Giphy API 키 (GIF 검색용)
GIPHY_API_KEY=your_giphy_api_key

# Google Gemini API 키 (AI 챗봇용)
GEMINI_API_KEY=your_gemini_api_key
```

#### API 키 발급 방법

**OpenWeatherMap API**
1. [OpenWeatherMap](https://openweathermap.org/api) 접속
2. 회원 가입 후 API 키 발급
3. `.env` 파일의 `WEATHER_API_KEY`에 입력

**Giphy API**
1. [Giphy Developers](https://developers.giphy.com/) 접속
2. 앱 생성 후 API 키 발급
3. `.env` 파일의 `GIPHY_API_KEY`에 입력

**Google Gemini API**
1. [Google AI Studio](https://makersuite.google.com/app/apikey) 접속
2. Google 계정으로 로그인
3. "Get API key" 버튼 클릭하여 API 키 생성
4. `.env` 파일의 `GEMINI_API_KEY`에 입력

### 4. 애플리케이션 실행

```bash
python app.py
```

서버가 `http://localhost:5000`에서 실행됩니다.

## Mattermost 설정

### 1. Outgoing Webhook 생성

1. Mattermost에 로그인
2. 설정 > 통합 > Outgoing Webhooks
3. 새 Outgoing Webhook 추가
4. 다음 정보 입력:
   - **트리거 단어**: !날씨, !번역, !점심, !주사위, !gif, !help
   - **트리거 조건**: 첫 번째 단어가 트리거 단어와 정확히 일치할 때
   - **콜백 URL**: `http://localhost:5000/webhook` (또는 공개 서버 URL)
   - **Content-Type**: application/x-www-form-urlencoded

### 2. 공개 URL 설정 (선택사항)

로컬 개발 환경에서 Mattermost와 연동하려면 ngrok 같은 터널링 서비스를 사용할 수 있습니다:

```bash
# ngrok 설치 후
ngrok http 5000
```

생성된 공개 URL을 Mattermost의 콜백 URL에 입력합니다.

## 사용 예시

Mattermost 채널에서 다음과 같이 명령어를 입력합니다:

```
!날씨 서울
!점심
!주사위 20
!gif 고양이
?파이썬에서 리스트와 튜플의 차이는?
!help
```

## 프로젝트 구조

```
mattermost_bot/
├── app.py              # 메인 Flask 애플리케이션
├── requirements.txt    # Python 패키지 의존성
├── .env               # 환경 변수 (직접 생성)
└── README.md          # 프로젝트 문서
```

## API 엔드포인트

- `POST /webhook` - Mattermost Outgoing Webhook 수신
- `GET /health` - 헬스 체크

## 문제 해결

### 봇이 응답하지 않는 경우

1. Flask 서버가 실행 중인지 확인
2. Mattermost의 토큰이 올바른지 확인
3. 콜백 URL이 정확한지 확인
4. 트리거 단어가 정확히 일치하는지 확인

### 날씨/GIF/Gemini 기능이 작동하지 않는 경우

1. `.env` 파일에 API 키가 올바르게 설정되었는지 확인
2. API 키의 유효성 확인
3. 인터넷 연결 상태 확인

### Gemini AI 응답이 느린 경우

Gemini AI는 외부 API를 호출하므로 응답 시간이 몇 초 소요될 수 있습니다. 이는 정상적인 동작입니다.

## 라이선스

MIT License

## 기여

버그 리포트나 기능 제안은 이슈로 등록해주세요.
