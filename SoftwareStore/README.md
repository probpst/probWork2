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

## 실행

```bash
cd SoftwareStore
pip install -r requirements.txt
python app.py                      # http://127.0.0.1:5000  (테스트 결제 모드)
python -m pytest -q tests          # 테스트
```

테스트 모드 카드: `4242 4242 4242 4242` → 승인, `4000 0000 0000 0002` → 거절 (유효기간·CVC 는 아무 값).

## 상품 등록

1. `products.json` 에 항목을 추가합니다 (`id`, `name`, `short`, `description`, `features`, `version`,
   `platform`, `price`(원), `file`, `badge`).
2. 배포 파일(설치 파일·zip)을 `files/` 폴더에 넣고, 파일 이름을 `"file"` 에 적습니다.
   파일이 없으면 주문 페이지에 "파일 준비 중" 으로 표시됩니다.

## 실제 결제 연결 (토스페이먼츠)

1. [토스페이먼츠 개발자센터](https://developers.tosspayments.com) 에서 가입 후 **결제위젯 연동 키**
   (클라이언트 키 `test_gck_…` / 시크릿 키 `test_gsk_…`) 를 발급받습니다. API 개별 연동 키(`ck`)는 위젯에서 동작하지 않습니다.
2. 환경변수를 설정하고 실행합니다.

```bash
export PAYMENT_PROVIDER=toss
export TOSS_CLIENT_KEY=test_gck_xxxxxxxx
export TOSS_SECRET_KEY=test_gsk_xxxxxxxx      # 절대 브라우저/깃에 노출하지 말 것
export SECRET_KEY=$(python -c "import secrets;print(secrets.token_hex(32))")
export ADMIN_PASSWORD=원하는비밀번호
python app.py
```

테스트 키로 충분히 확인한 다음, 전자결제 계약이 끝나면 라이브 키(`live_gck_…`/`live_gsk_…`)로 바꿉니다.

| 환경변수 | 기본값 | 설명 |
|---|---|---|
| `PAYMENT_PROVIDER` | `mock` | `mock` 또는 `toss` |
| `TOSS_CLIENT_KEY`, `TOSS_SECRET_KEY` | — | 토스 결제위젯 키 |
| `SECRET_KEY` | 자동 생성(`.secret_key`) | 세션·라이선스 키 서명. 바꾸면 기존 라이선스 키 표시값이 달라짐 |
| `ADMIN_PASSWORD` | — | 비어 있으면 `/admin` 비활성 |
| `STORE_NAME` | `Software Store` | 사이트 이름 |
| `STORE_DB` | `store.db` | SQLite 주문 DB 경로 |
| `HOST`, `PORT` | `127.0.0.1`, `5000` | 개발 서버 주소 |

## 운영 시 주의

* 운영 서버에서는 `python app.py` 대신 WSGI 서버를 쓰고 HTTPS 를 켜세요:
  `gunicorn -w 2 -b 0.0.0.0:8000 "app:create_app()"` + Nginx/Caddy(HTTPS).
* `templates/terms.html` 의 약관·환불정책·**사업자 정보**(상호, 사업자등록번호, 통신판매업 신고번호 등)는
  예시이므로 실제 내용으로 바꿔야 합니다 (전자상거래법 표시 의무).
* 결제 완료 이메일 발송, 환불(결제 취소 API)은 아직 포함되지 않았습니다. 환불은 토스페이먼츠 상점관리자에서 처리할 수 있습니다.
