# Software Store — 프로그램 판매 웹사이트

Flask 로 만든 소프트웨어 판매 사이트입니다. 상품 목록 → 장바구니 → 주문서 → **결제창** →
결제 완료 후 **라이선스 키 발급 + 다운로드** 까지 한 흐름으로 동작합니다.

| 기능 | 설명 |
|---|---|
| 상품 목록 / 상세 | `products.json` 에서 읽음 (이름·가격·설명·기능·배포 파일) |
| 장바구니 | 세션 기반, 수량(=라이선스 수) 변경 |
| 결제창 | `mock`(테스트 카드 결제창) 또는 `toss`(토스페이먼츠 결제위젯: 카드·간편결제·계좌이체 등) |
| 결제 검증 | 금액은 항상 서버에서 계산하고, 승인 전에 주문 금액과 비교 |
| 주문 완료 | 라이선스 키(HMAC) 자동 발급, 주문별 비밀 링크로 파일 다운로드 |
| 관리자 | `/admin` — 주문 목록·상태·매출 (`ADMIN_PASSWORD` 설정 시에만 열림) |

## Windows 에서 실행

1. [python.org](https://www.python.org/downloads/windows/) 에서 **Python 3.10 이상(64-bit)** 을 설치합니다.
   설치 첫 화면에서 **"Add python.exe to PATH"** 를 체크하세요.
   (Microsoft Store 의 python 바로가기만 있는 상태라면 venv 생성이 실패할 수 있습니다.)
2. `SoftwareStore` 폴더에서 **`run_store.bat` 을 더블클릭**합니다.
   * 첫 실행 때 `.venv` 가상환경을 만들고 필요한 패키지(Flask, waitress)를 설치합니다 (1–2분, 인터넷 필요).
   * 설정 파일 `store.env` 가 자동으로 만들어지고, 브라우저에서 `http://127.0.0.1:5000` 이 열립니다.
   * 창을 닫거나 `Ctrl+C` 를 누르면 서버가 멈춥니다.
3. 설정(결제 방식, 토스 키, 관리자 비밀번호, 포트 등)은 **`store.env` 를 메모장으로 열어** 바꾼 뒤
   `run_store.bat` 을 다시 실행하면 적용됩니다.

다른 PC·인터넷에서 접속하게 하려면:

* `store.env` 에서 `HOST=0.0.0.0` 으로 바꿉니다.
* 처음 실행할 때 뜨는 **Windows Defender 방화벽** 창에서 "허용" 을 누르거나, 관리자 PowerShell 에서
  `New-NetFirewallRule -DisplayName "Software Store" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow`
* 인터넷에 공개할 때는 공유기 포트포워딩과 HTTPS(예: [Caddy](https://caddyserver.com) 리버스 프록시,
  `caddy reverse-proxy --from 내도메인.com --to 127.0.0.1:5000`) 가 필요합니다. 결제 페이지는 HTTPS 로 운영하세요.

PC 를 켤 때 자동으로 시작하려면 **작업 스케줄러** → 기본 작업 만들기 → 트리거 "컴퓨터 시작 시" →
동작 "프로그램 시작" 에 `run_store.bat` 경로를 넣고, `store.env` 에 `OPEN_BROWSER=0` 을 설정합니다.

## 명령줄로 실행 (Windows / Linux / macOS 공통)

```bash
cd SoftwareStore
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python serve.py                    # 운영용 서버(waitress) — Windows 에서도 동작
python app.py                      # 개발용 서버 (FLASK_DEBUG=1 이면 코드 변경 시 자동 재시작)
python -m pytest -q tests          # 테스트
```

## 상품 등록

1. `products.json` 에 항목을 추가합니다 (`id`, `name`, `short`, `description`, `features`, `version`,
   `platform`, `price`(원), `file`, `badge`).
2. 배포 파일(설치 파일·zip)을 `files/` 폴더에 넣고, 파일 이름을 `"file"` 에 적습니다.
   파일이 없으면 주문 페이지에 "파일 준비 중" 으로 표시됩니다.

## 실제 결제 연결 (토스페이먼츠)

1. [토스페이먼츠 개발자센터](https://developers.tosspayments.com) 에서 가입 후 **결제위젯 연동 키**
   (클라이언트 키 `test_gck_…` / 시크릿 키 `test_gsk_…`) 를 발급받습니다. API 개별 연동 키(`ck`)는 위젯에서 동작하지 않습니다.
2. `store.env` 를 메모장으로 열어 아래처럼 바꾸고 다시 실행합니다 (환경변수로 설정해도 됩니다. 환경변수가 우선).

```ini
PAYMENT_PROVIDER=toss
TOSS_CLIENT_KEY=test_gck_xxxxxxxx
TOSS_SECRET_KEY=test_gsk_xxxxxxxx
ADMIN_PASSWORD=원하는비밀번호
```

   시크릿 키는 브라우저나 git 에 노출되면 안 됩니다 (`store.env` 는 `.gitignore` 에 들어 있습니다).

테스트 키로 충분히 확인한 다음, 전자결제 계약이 끝나면 라이브 키(`live_gck_…`/`live_gsk_…`)로 바꿉니다.

| 환경변수 | 기본값 | 설명 |
|---|---|---|
| `PAYMENT_PROVIDER` | `mock` | `mock` 또는 `toss` |
| `TOSS_CLIENT_KEY`, `TOSS_SECRET_KEY` | — | 토스 결제위젯 키 |
| `SECRET_KEY` | 자동 생성(`.secret_key`) | 세션·라이선스 키 서명. 바꾸면 기존 라이선스 키 표시값이 달라짐 |
| `ADMIN_PASSWORD` | — | 비어 있으면 `/admin` 비활성 |
| `STORE_NAME` | `Software Store` | 사이트 이름 |
| `STORE_DB` | `store.db` | SQLite 주문 DB 경로 |
| `HOST`, `PORT` | `127.0.0.1`, `5000` | 서버 주소 |
| `OPEN_BROWSER` | `1` | `serve.py` 시작 시 브라우저 열기 |
| `THREADS` | `8` | waitress 작업 스레드 수 |

## 운영 시 주의

* 운영할 때는 `python app.py`(개발용) 대신 `serve.py`(waitress) 를 쓰고 HTTPS 를 켜세요.
  Linux 서버라면 `gunicorn -w 2 -b 0.0.0.0:8000 "app:create_app()"` 도 됩니다.
* `templates/terms.html` 의 약관·환불정책·**사업자 정보**(상호, 사업자등록번호, 통신판매업 신고번호 등)는
  예시이므로 실제 내용으로 바꿔야 합니다 (전자상거래법 표시 의무).
* 결제 완료 이메일 발송, 환불(결제 취소 API)은 아직 포함되지 않았습니다. 환불은 토스페이먼츠 상점관리자에서 처리할 수 있습니다.
