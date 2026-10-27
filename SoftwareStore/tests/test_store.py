import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as store  # noqa: E402


def make_client(tmp_path, **cfg):
    files = tmp_path / "files"
    files.mkdir()
    (files / "HullFormDesigner-0.1.0-Setup.exe").write_bytes(b"binary")
    config = {"TESTING": True, "SECRET_KEY": "test", "DATABASE": str(tmp_path / "t.db"),
              "FILES_DIR": str(files), "ADMIN_PASSWORD": "pw"}
    config.update(cfg)
    return store.create_app(config).test_client()


def csrf(client):
    client.get("/")
    with client.session_transaction() as s:
        return s["csrf"]


def place_order(client, pid="hullform-standard", qty=1):
    token = csrf(client)
    client.post(f"/cart/add/{pid}", data={"csrf": token, "qty": qty})
    r = client.post("/checkout", data={"csrf": token, "name": "홍길동",
                                       "email": "a@b.kr", "agree": "1"})
    assert r.status_code == 302
    return token, r.headers["Location"].rsplit("/", 1)[1]


@pytest.fixture
def client(tmp_path):
    return make_client(tmp_path)


def test_catalogue_and_csrf(client):
    assert "Hull Form Designer" in client.get("/").get_data(as_text=True)
    assert client.post("/cart/add/hullform-standard", data={"csrf": "bad"}).status_code == 400


def test_mock_purchase_gives_licences_and_download(client):
    token, order_id = place_order(client, qty=2)
    page = client.get(f"/pay/{order_id}").get_data(as_text=True)
    assert "1,980,000원" in page
    r = client.post(f"/pay/mock/{order_id}", data={"csrf": token, "card": "4242 4242 4242 4242",
                                                   "exp": "12/30", "cvc": "123"})
    order_url = r.headers["Location"]
    html = client.get(order_url).get_data(as_text=True)
    assert "결제가 완료되었습니다" in html
    assert len(re.findall(r"[A-Z2-7]{5}-[A-Z2-7]{5}-[A-Z2-7]{5}-[A-Z2-7]{5}", html)) == 2
    t = order_url.split("t=")[1]
    assert client.get(f"/download/{order_id}/hullform-standard?t={t}").data == b"binary"
    # 다른 브라우저(세션 없음)는 토큰 없이 볼 수 없다
    with client.session_transaction() as s:
        s.clear()
    assert client.get(f"/orders/{order_id}").status_code == 403
    assert client.get(f"/orders/{order_id}?t={t}").status_code == 200


def test_mock_decline_and_invalid_card(client):
    token, order_id = place_order(client)
    r = client.post(f"/pay/mock/{order_id}", data={"csrf": token, "card": "1234 5678 9012 3456",
                                                   "exp": "12/30", "cvc": "123"})
    assert r.headers["Location"].endswith(f"/pay/{order_id}")  # 재입력
    r = client.post(f"/pay/mock/{order_id}", data={"csrf": token, "card": "4000000000000002",
                                                   "exp": "12/30", "cvc": "123"})
    assert "/pay/fail" in r.headers["Location"]
    assert "FAILED" in client.get(f"/orders/{order_id}").get_data(as_text=True)


def test_price_comes_from_server(client):
    token = csrf(client)
    client.post("/cart/add/hullform-pro", data={"csrf": token, "qty": 1, "price": 1})
    client.post("/checkout", data={"csrf": token, "name": "x", "email": "a@b.kr", "agree": "1"})
    with client.session_transaction() as s:
        oid = s["my_orders"][0]
    assert "2,490,000원" in client.get(f"/pay/{oid}").get_data(as_text=True)


def test_toss_amount_mismatch_rejected(tmp_path, monkeypatch):
    c = make_client(tmp_path, PAYMENT_PROVIDER="toss", TOSS_CLIENT_KEY="ck", TOSS_SECRET_KEY="sk")
    _, oid = place_order(c)
    assert "js.tosspayments.com" in c.get(f"/pay/{oid}").get_data(as_text=True)
    called = []
    monkeypatch.setattr(store.urllib.request, "urlopen", lambda *a, **k: called.append(1))
    r = c.get(f"/pay/toss/success?paymentKey=pk&orderId={oid}&amount=100")
    assert "AMOUNT_MISMATCH" in r.headers["Location"] and not called


def test_toss_confirm_success(tmp_path, monkeypatch):
    c = make_client(tmp_path, PAYMENT_PROVIDER="toss", TOSS_CLIENT_KEY="ck", TOSS_SECRET_KEY="sk")
    _, oid = place_order(c)
    sent = {}

    class Resp:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return b'{"status":"DONE","method":"\\uce74\\ub4dc"}'

    def fake_urlopen(req, timeout):
        sent["auth"] = req.headers["Authorization"]
        sent["body"] = req.data
        return Resp()

    monkeypatch.setattr(store.urllib.request, "urlopen", fake_urlopen)
    r = c.get(f"/pay/toss/success?paymentKey=pk&orderId={oid}&amount=990000")
    assert "/orders/" in r.headers["Location"]
    assert sent["auth"] == "Basic c2s6"  # base64("sk:")
    assert b'"amount": 990000' in sent["body"]


def test_admin(client):
    place_order(client)
    assert client.get("/admin").status_code == 302
    token = csrf(client)
    client.post("/admin/login", data={"csrf": token, "password": "pw"})
    assert "홍길동" in client.get("/admin").get_data(as_text=True)


def test_env_file_with_notepad_bom(tmp_path, monkeypatch):
    env = tmp_path / "store.env"
    env.write_bytes("﻿# comment\nSTORE_NAME=\"내 상점\"\nPORT=8080\nADMIN_PASSWORD=\n".encode("utf-8"))
    for k in ("STORE_NAME", "PORT", "ADMIN_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("PORT", "9000")  # 이미 설정된 환경변수가 우선
    store.load_env_file(env)
    import os
    assert os.environ["STORE_NAME"] == "내 상점"
    assert os.environ["PORT"] == "9000"
    assert os.environ["ADMIN_PASSWORD"] == ""
