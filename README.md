# SSAFY Mattermost Bot

SSAFY 교육생을 위한 Mattermost 챗봇입니다. AI 질문, 식단 조회, 수업 일정, 취업 정보 등 다양한 기능을 제공합니다.

## 주요 기능

### AI 기능
| 명령어 | 설명 |
|:------|:-----|
| `?질문` | Gemini AI에게 질문하기 |
| `!요약 [내용]` | 강의/메모 내용 정리 |
| `!코드 [코드]` | 코드 리뷰 & 100점 만점 점수 |
| `!번역 [텍스트]` | 영어↔한국어 번역 |

### 식단 조회
| 명령어 | 설명 |
|:------|:-----|
| `!점심` | 오늘 구미캠퍼스 점심 메뉴 |
| `!점심 01-20` | 특정 날짜 점심 메뉴 |
| `!저녁` | 오늘 구미캠퍼스 저녁 메뉴 |
| `!저녁 01-20` | 특정 날짜 저녁 메뉴 |

### SSAFY 수업 일정
| 명령어 | 설명 |
|:------|:-----|
| `!수업` | 오늘 수업 일정 조회 |
| `!이번주수업` | 이번 주 전체 수업 조회 |

### 취업 정보
| 명령어 | 설명 |
|:------|:-----|
| `!취업` | IT/인터넷 인턴 채용 정보 (링커리어) |

### 재미 기능
| 명령어 | 설명 |
|:------|:-----|
| `!주사위 [N]` | N면 주사위 굴리기 (기본 6면) |
| `!사다리 [이름들] [결과들]` | 사다리 타기 |
| `!help` | 도움말 표시 |

## 설치 방법

### 1. 필수 요구사항

- Python 3.11 이상
- pip

### 2. 패키지 설치

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. 환경 변수 설정

`.env.example`을 참고하여 `.env` 파일을 생성합니다:

```env
# Mattermost 설정
MATTERMOST_TOKEN=your_mattermost_token_here
MATTERMOST_INCOMING_WEBHOOK=https://your-mattermost-server/hooks/your_webhook_id

# Google Gemini API 키
GEMINI_API_KEY=your_gemini_api_key_here

# SSAFY 계정 정보 (수업 일정 조회용)
SSAFY_USER_ID=your_email@example.com
SSAFY_USER_PW=your_password
```

### 4. 애플리케이션 실행

```bash
python app.py
```

서버가 `http://localhost:5000`에서 실행됩니다.

## Mattermost 설정

### Outgoing Webhook 생성

1. Mattermost 시스템 콘솔 > 통합 > Outgoing Webhooks
2. 새 Outgoing Webhook 추가:
   - **트리거 단어**: `!번역`, `!점심`, `!저녁`, `!주사위`, `!사다리`, `!요약`, `!코드`, `!취업`, `!수업`, `!이번주수업`, `!help`, `?`
   - **콜백 URL**: `http://your-server/webhook`

### Incoming Webhook 생성

AI 기능 등 비동기 응답을 위해 Incoming Webhook이 필요합니다:

1. Mattermost 시스템 콘솔 > 통합 > Incoming Webhooks
2. 새 Incoming Webhook 추가
3. 생성된 URL을 `.env`의 `MATTERMOST_INCOMING_WEBHOOK`에 설정

## AWS Elastic Beanstalk 배포

### 배포 명령어

```bash
eb deploy
```

### 환경 변수 설정

```bash
eb setenv MATTERMOST_TOKEN=xxx MATTERMOST_INCOMING_WEBHOOK=xxx GEMINI_API_KEY=xxx SSAFY_USER_ID=xxx SSAFY_USER_PW=xxx
```

### 배포 구성 파일

- `.ebextensions/` - Chrome, Playwright 의존성 설치
- `.platform/hooks/postdeploy/` - Playwright 브라우저 설치

## 프로젝트 구조

```
mattermost_bot/
├── app.py                          # 메인 Flask 애플리케이션
├── requirements.txt                # Python 패키지 의존성
├── .env                            # 환경 변수 (직접 생성)
├── .env.example                    # 환경 변수 예시
├── .ebextensions/                  # AWS EB 설정
│   ├── 01_flask.config
│   ├── 04_chrome.config
│   └── 05_playwright.config
├── .platform/
│   └── hooks/postdeploy/
│       └── 01_install_playwright.sh
└── README.md
```

## API 엔드포인트

| 엔드포인트 | 메서드 | 설명 |
|:----------|:------|:-----|
| `/webhook` | POST | Mattermost Outgoing Webhook 수신 |
| `/health` | GET | 헬스 체크 |

## 기술 스택

- **Backend**: Flask 3.0
- **AI**: Google Gemini API (gemini-2.5-flash-lite)
- **크롤링**:
  - Selenium + Chrome (취업 정보)
  - Playwright + Chromium (SSAFY 수업 일정)
- **배포**: AWS Elastic Beanstalk (Amazon Linux 2023)

## 문제 해결

### AI 기능 응답이 없는 경우
- Gemini API 키 확인
- Incoming Webhook URL 확인
- 요청 제한(429 에러)일 수 있음 - 1분 후 재시도

### 수업 조회가 안 되는 경우
- SSAFY 계정 정보 확인
- Playwright 브라우저 설치 여부 확인

### 취업 정보 조회가 안 되는 경우
- Chrome/ChromeDriver 설치 여부 확인

## 라이선스

MIT License
