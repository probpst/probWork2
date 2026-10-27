"""Software Store — 프로그램 판매 웹사이트 (Flask).

결제 방식은 환경변수 PAYMENT_PROVIDER 로 선택한다.
  * mock (기본값): 실제 돈이 오가지 않는 테스트용 카드 결제창
  * toss         : 토스페이먼츠 결제위젯 (TOSS_CLIENT_KEY / TOSS_SECRET_KEY 필요)

가격은 항상 서버의 products.json 에서 계산하며, 결제 승인 전에 금액을 다시 확인한다.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   send_from_directory, session, url_for)

BASE_DIR = Path(__file__).resolve().parent
TOSS_CONFIRM_URL = "https://api.tosspayments.com/v1/payments/confirm"
MOCK_DECLINE_CARD = "4000000000000002"


def load_env_file(path=BASE_DIR / "store.env"):
    """store.env 의 KEY=VALUE 줄을 환경변수로 읽는다 (이미 설정된 값이 우선).

    Windows 에서 환경변수를 직접 설정하지 않고 메모장으로 설정을 바꿀 수 있게 하기 위함.
    메모장이 붙이는 BOM 을 고려해 utf-8-sig 로 읽는다.
    """
    path = Path(path)
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


def persistent_secret():
    """SECRET_KEY 가 없으면 한 번 만들어 파일에 저장한다 (재시작해도 세션·라이선스 키 유지)."""
    path = BASE_DIR / ".secret_key"
    if not path.exists():
        path.write_text(secrets.token_hex(32), encoding="ascii")
    return path.read_text(encoding="ascii").strip()


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY") or persistent_secret(),
        STORE_NAME=os.environ.get("STORE_NAME", "Software Store"),
        DATABASE=os.environ.get("STORE_DB", str(BASE_DIR / "store.db")),
        PRODUCTS_FILE=os.environ.get("PRODUCTS_FILE", str(BASE_DIR / "products.json")),
        FILES_DIR=os.environ.get("FILES_DIR", str(BASE_DIR / "files")),
        PAYMENT_PROVIDER=os.environ.get("PAYMENT_PROVIDER", "mock").lower(),
        TOSS_CLIENT_KEY=os.environ.get("TOSS_CLIENT_KEY", ""),
        TOSS_SECRET_KEY=os.environ.get("TOSS_SECRET_KEY", ""),
        ADMIN_PASSWORD=os.environ.get("ADMIN_PASSWORD", ""),
    )
    if config:
        app.config.update(config)
    if app.config["PAYMENT_PROVIDER"] not in ("mock", "toss"):
        raise ValueError("PAYMENT_PROVIDER must be 'mock' or 'toss'")
    if app.config["PAYMENT_PROVIDER"] == "toss" and not (
            app.config["TOSS_CLIENT_KEY"] and app.config["TOSS_SECRET_KEY"]):
        raise ValueError("PAYMENT_PROVIDER=toss requires TOSS_CLIENT_KEY and TOSS_SECRET_KEY")

    init_db(app)
    register_routes(app)
    app.teardown_appcontext(close_db)
    app.jinja_env.filters["won"] = lambda v: f"{int(v):,}원"
    return app


# --------------------------------------------------------------------------- data

def load_products(app):
    with open(app.config["PRODUCTS_FILE"], encoding="utf-8") as f:
        return {p["id"]: p for p in json.load(f)}


def get_db():
    if "db" not in g:
        from flask import current_app
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    db = sqlite3.connect(app.config["DATABASE"])
    db.executescript("""
        CREATE TABLE IF NOT EXISTS orders (
            id            TEXT PRIMARY KEY,
            access_token  TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            email         TEXT NOT NULL,
            items         TEXT NOT NULL,          -- JSON [{id,name,price,qty}]
            amount        INTEGER NOT NULL,
            status        TEXT NOT NULL,          -- PENDING / PAID / FAILED
            provider      TEXT NOT NULL,
            payment_key   TEXT,
            method        TEXT,
            created_at    TEXT NOT NULL,
            paid_at       TEXT
        );
    """)
    db.commit()
    db.close()


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_order(order_id):
    row = get_db().execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if row is None:
        abort(404)
    order = dict(row)
    order["items"] = json.loads(order["items"])
    return order


def mark_paid(order_id, payment_key, method):
    db = get_db()
    db.execute("UPDATE orders SET status='PAID', payment_key=?, method=?, paid_at=? "
               "WHERE id=? AND status='PENDING'", (payment_key, method, now_iso(), order_id))
    db.commit()


def mark_failed(order_id):
    db = get_db()
    db.execute("UPDATE orders SET status='FAILED' WHERE id=? AND status='PENDING'", (order_id,))
    db.commit()


def license_key(secret, order_id, product_id, seat):
    digest = hmac.new(secret.encode(), f"{order_id}:{product_id}:{seat}".encode(),
                      hashlib.sha256).digest()
    code = base64.b32encode(digest).decode()[:20]
    return "-".join(code[i:i + 5] for i in range(0, 20, 5))


def luhn_ok(number):
    digits = [int(c) for c in number]
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


# --------------------------------------------------------------------------- routes

def register_routes(app):

    def cart():
        return session.setdefault("cart", {})

    def cart_lines():
        products = load_products(app)
        lines = []
        for pid, qty in cart().items():
            if pid in products:
                p = products[pid]
                lines.append({"id": pid, "name": p["name"], "price": int(p["price"]),
                              "qty": int(qty), "subtotal": int(p["price"]) * int(qty)})
        return lines

    def csrf_token():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return session["csrf"]

    @app.before_request
    def check_csrf():
        if request.method == "POST":
            sent = request.form.get("csrf", "")
            if not hmac.compare_digest(sent, session.get("csrf", "")):
                abort(400, "잘못된 요청입니다 (CSRF).")

    @app.context_processor
    def inject():
        return {"csrf_token": csrf_token, "store_name": app.config["STORE_NAME"],
                "cart_count": sum(cart().values()), "provider": app.config["PAYMENT_PROVIDER"]}

    def can_view(order):
        token = request.args.get("t", "")
        return (hmac.compare_digest(token, order["access_token"])
                or order["id"] in session.get("my_orders", []))

    # ---- catalogue

    @app.get("/")
    def index():
        return render_template("index.html", products=load_products(app).values())

    @app.get("/product/<pid>")
    def product(pid):
        p = load_products(app).get(pid) or abort(404)
        return render_template("product.html", p=p)

    # ---- cart

    @app.post("/cart/add/<pid>")
    def cart_add(pid):
        if pid not in load_products(app):
            abort(404)
        qty = max(1, min(99, request.form.get("qty", 1, type=int) or 1))
        c = cart()
        c[pid] = min(99, c.get(pid, 0) + qty)
        session.modified = True
        flash("장바구니에 담았습니다.")
        return redirect(url_for("cart_view"))

    @app.post("/cart/update")
    def cart_update():
        c = cart()
        for pid in list(c):
            qty = request.form.get(f"qty_{pid}", type=int)
            if qty is not None:
                if qty <= 0:
                    c.pop(pid)
                else:
                    c[pid] = min(99, qty)
        session.modified = True
        return redirect(url_for("cart_view"))

    @app.get("/cart")
    def cart_view():
        lines = cart_lines()
        return render_template("cart.html", lines=lines, total=sum(l["subtotal"] for l in lines))

    # ---- checkout

    @app.route("/checkout", methods=["GET", "POST"])
    def checkout():
        lines = cart_lines()
        if not lines:
            flash("장바구니가 비어 있습니다.")
            return redirect(url_for("index"))
        total = sum(l["subtotal"] for l in lines)
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip()
            if not name or "@" not in email or not request.form.get("agree"):
                flash("이름, 이메일을 입력하고 약관에 동의해 주세요.")
                return render_template("checkout.html", lines=lines, total=total,
                                       name=name, email=email)
            order_id = "ORD-" + datetime.now().strftime("%Y%m%d") + "-" + secrets.token_hex(6)
            token = secrets.token_urlsafe(24)
            items = [{k: l[k] for k in ("id", "name", "price", "qty")} for l in lines]
            db = get_db()
            db.execute("INSERT INTO orders (id, access_token, customer_name, email, items, amount,"
                       " status, provider, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                       (order_id, token, name, email, json.dumps(items, ensure_ascii=False),
                        total, "PENDING", app.config["PAYMENT_PROVIDER"], now_iso()))
            db.commit()
            session.setdefault("my_orders", []).append(order_id)
            session.modified = True
            return redirect(url_for("pay", order_id=order_id))
        return render_template("checkout.html", lines=lines, total=total, name="", email="")

    def order_name(order):
        first = order["items"][0]["name"]
        n = sum(i["qty"] for i in order["items"])
        return first if n == 1 else f"{first} 외 {n - 1}건"

    @app.get("/pay/<order_id>")
    def pay(order_id):
        order = get_order(order_id)
        if not can_view(order):
            abort(403)
        if order["status"] == "PAID":
            return redirect(url_for("order_view", order_id=order_id, t=order["access_token"]))
        if order["status"] != "PENDING":
            flash("이 주문은 결제할 수 없습니다. 다시 주문해 주세요.")
            return redirect(url_for("cart_view"))
        if app.config["PAYMENT_PROVIDER"] == "toss":
            return render_template(
                "pay_toss.html", order=order, order_name=order_name(order),
                client_key=app.config["TOSS_CLIENT_KEY"],
                success_url=url_for("toss_success", _external=True),
                fail_url=url_for("pay_fail", _external=True))
        return render_template("pay_mock.html", order=order, order_name=order_name(order))

    # ---- mock provider (no real money)

    @app.post("/pay/mock/<order_id>")
    def mock_pay(order_id):
        if app.config["PAYMENT_PROVIDER"] != "mock":
            abort(404)
        order = get_order(order_id)
        if not can_view(order) or order["status"] != "PENDING":
            abort(403)
        card = "".join(c for c in request.form.get("card", "") if c.isdigit())
        exp = request.form.get("exp", "").strip()
        cvc = request.form.get("cvc", "").strip()
        error = None
        if not (13 <= len(card) <= 19 and luhn_ok(card)):
            error = "카드 번호가 올바르지 않습니다."
        elif len(exp) != 5 or exp[2] != "/" or not (exp[:2] + exp[3:]).isdigit() \
                or not 1 <= int(exp[:2]) <= 12:
            error = "유효기간을 MM/YY 형식으로 입력해 주세요."
        elif not (cvc.isdigit() and len(cvc) in (3, 4)):
            error = "CVC 를 확인해 주세요."
        elif card == MOCK_DECLINE_CARD:
            mark_failed(order_id)
            return redirect(url_for("pay_fail", code="CARD_DECLINED",
                                    message="카드사에서 승인을 거절했습니다 (테스트).",
                                    orderId=order_id))
        if error:
            flash(error)
            return redirect(url_for("pay", order_id=order_id))
        mark_paid(order_id, "mock_" + secrets.token_hex(8), f"카드 (**** {card[-4:]})")
        return finish(order_id)

    # ---- Toss Payments

    @app.get("/pay/toss/success")
    def toss_success():
        if app.config["PAYMENT_PROVIDER"] != "toss":
            abort(404)
        payment_key = request.args.get("paymentKey", "")
        order_id = request.args.get("orderId", "")
        amount = request.args.get("amount", type=int)
        order = get_order(order_id)
        if order["status"] == "PAID":
            return finish(order_id)
        # 위젯에서 넘어온 금액이 주문 금액과 같은지 반드시 서버에서 확인한다.
        if order["status"] != "PENDING" or amount != order["amount"]:
            mark_failed(order_id)
            return redirect(url_for("pay_fail", code="AMOUNT_MISMATCH",
                                    message="결제 금액이 주문 금액과 다릅니다.", orderId=order_id))
        ok, data = toss_confirm(payment_key, order_id, amount)
        if not ok:
            mark_failed(order_id)
            return redirect(url_for("pay_fail", code=data.get("code", "CONFIRM_FAILED"),
                                    message=data.get("message", "결제 승인에 실패했습니다."),
                                    orderId=order_id))
        mark_paid(order_id, payment_key, data.get("method", "토스페이먼츠"))
        return finish(order_id)

    def toss_confirm(payment_key, order_id, amount):
        auth = base64.b64encode((app.config["TOSS_SECRET_KEY"] + ":").encode()).decode()
        req = urllib.request.Request(
            TOSS_CONFIRM_URL, method="POST",
            data=json.dumps({"paymentKey": payment_key, "orderId": order_id,
                             "amount": amount}).encode(),
            headers={"Authorization": "Basic " + auth, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return True, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            try:
                return False, json.loads(e.read())
            except ValueError:
                return False, {"message": f"HTTP {e.code}"}
        except urllib.error.URLError as e:
            return False, {"code": "NETWORK_ERROR", "message": str(e.reason)}

    @app.get("/pay/fail")
    def pay_fail():
        order_id = request.args.get("orderId")
        if order_id:
            row = get_db().execute("SELECT status FROM orders WHERE id=?", (order_id,)).fetchone()
            if row and row["status"] == "PENDING":
                mark_failed(order_id)
        return render_template("fail.html", code=request.args.get("code", ""),
                               message=request.args.get("message", "결제가 취소되었습니다."))

    def finish(order_id):
        order = get_order(order_id)
        session["cart"] = {}
        return redirect(url_for("order_view", order_id=order_id, t=order["access_token"]))

    # ---- order / downloads

    def order_licenses(order):
        out = []
        for item in order["items"]:
            for seat in range(1, item["qty"] + 1):
                out.append({"product": item["name"], "id": item["id"],
                            "key": license_key(app.config["SECRET_KEY"], order["id"],
                                               item["id"], seat)})
        return out

    @app.get("/orders/<order_id>")
    def order_view(order_id):
        order = get_order(order_id)
        if not can_view(order):
            abort(403)
        products = load_products(app)
        downloads = []
        if order["status"] == "PAID":
            for item in order["items"]:
                fname = products.get(item["id"], {}).get("file", "")
                available = bool(fname) and (Path(app.config["FILES_DIR"]) / fname).is_file()
                downloads.append({"id": item["id"], "name": item["name"], "file": fname,
                                  "available": available})
        return render_template("order.html", order=order, downloads=downloads,
                               licenses=order_licenses(order) if order["status"] == "PAID" else [])

    @app.get("/download/<order_id>/<pid>")
    def download(order_id, pid):
        order = get_order(order_id)
        if not can_view(order) or order["status"] != "PAID":
            abort(403)
        if pid not in {i["id"] for i in order["items"]}:
            abort(404)
        fname = load_products(app).get(pid, {}).get("file") or abort(404)
        return send_from_directory(app.config["FILES_DIR"], fname, as_attachment=True)

    # ---- admin

    def admin_required(view):
        @wraps(view)
        def wrapped(*a, **kw):
            if not app.config["ADMIN_PASSWORD"]:
                abort(404)
            if not session.get("admin"):
                return redirect(url_for("admin_login"))
            return view(*a, **kw)
        return wrapped

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if not app.config["ADMIN_PASSWORD"]:
            abort(404)
        if request.method == "POST":
            if hmac.compare_digest(request.form.get("password", ""), app.config["ADMIN_PASSWORD"]):
                session["admin"] = True
                return redirect(url_for("admin"))
            flash("비밀번호가 틀렸습니다.")
        return render_template("admin_login.html")

    @app.get("/admin")
    @admin_required
    def admin():
        rows = get_db().execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT 500").fetchall()
        orders = [dict(r, items=json.loads(r["items"])) for r in rows]
        revenue = sum(o["amount"] for o in orders if o["status"] == "PAID")
        return render_template("admin.html", orders=orders, revenue=revenue)

    @app.post("/admin/logout")
    def admin_logout():
        session.pop("admin", None)
        return redirect(url_for("index"))

    @app.get("/terms")
    def terms():
        return render_template("terms.html")


if __name__ == "__main__":
    # 개발용 서버. 실제 운영(Windows 포함)은 serve.py (waitress) 를 사용한다.
    load_env_file()
    app = create_app()
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 5000)),
            debug=os.environ.get("FLASK_DEBUG") == "1")
