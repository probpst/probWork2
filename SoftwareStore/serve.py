"""운영용 서버 실행 (Windows / Linux / macOS 공통).

gunicorn 은 Windows 에서 동작하지 않으므로 순수 파이썬 WSGI 서버인 waitress 를 쓴다.
설정은 같은 폴더의 store.env 또는 환경변수에서 읽는다.

    python serve.py
"""
import os
import webbrowser

from waitress import serve

import app as store


def main():
    store.load_env_file()
    application = store.create_app()
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 5000))
    url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '::') else host}:{port}"
    print(f"{application.config['STORE_NAME']} running at {url}  "
          f"(payment: {application.config['PAYMENT_PROVIDER']})  - Ctrl+C to stop")
    if os.environ.get("OPEN_BROWSER", "1") == "1":
        webbrowser.open(url)
    serve(application, host=host, port=port, threads=int(os.environ.get("THREADS", 8)))


if __name__ == "__main__":
    main()
