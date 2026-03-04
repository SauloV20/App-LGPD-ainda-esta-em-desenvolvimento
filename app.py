import os
import json
import secrets
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect, session,
    flash, url_for, jsonify, send_file, abort, Blueprint
)
import io

from auth import auth, login_required
from scanner import scan_text, extract_text_from_file, check_rate_limit, PLAN_LIMITS
from database import get_db, close_db
from csrf import generate_csrf_token, csrf_protect
from payments import payments, STRIPE_PUBLISHABLE_KEY

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10MB
app.teardown_appcontext(close_db)

app.register_blueprint(auth)
app.register_blueprint(payments)


# ── Template helpers ──────────────────────────────────────────────────────────

@app.template_filter("from_json")
def from_json_filter(value):
    try:
        return json.loads(value)
    except Exception:
        return []

@app.context_processor
def inject_globals():
    return {
        "csrf_token":            generate_csrf_token,
        "stripe_publishable_key": STRIPE_PUBLISHABLE_KEY,
        "now":                   datetime.now(),
    }


# ── Main Blueprint ────────────────────────────────────────────────────────────

main = Blueprint("main", __name__)


@main.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("main.landing"))


@main.route("/landing")
def landing():
    return render_template("landing.html")


@main.route("/pricing")
def pricing():
    user = None
    if "user_id" in session:
        db   = get_db()
        user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    return render_template("pricing.html", user=user)


@main.route("/dashboard")
@login_required
def dashboard():
    db    = get_db()
    user  = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    scans = db.execute(
        "SELECT * FROM scans WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
        (session["user_id"],)
    ).fetchall()
    stats = db.execute("""
        SELECT
            COUNT(*) as total_scans,
            COALESCE(SUM(total_matches), 0) as total_matches,
            COUNT(CASE WHEN risk_level IN ('alto','crítico') THEN 1 END) as high_risk_scans,
            COUNT(CASE WHEN risk_level = 'crítico' THEN 1 END) as critical_scans
        FROM scans WHERE user_id = ?
    """, (session["user_id"],)).fetchone()

    chart_scans = db.execute(
        "SELECT created_at, total_matches, risk_level FROM scans WHERE user_id = ? ORDER BY created_at DESC LIMIT 7",
        (session["user_id"],)
    ).fetchall()

    type_freq = db.execute("""
        SELECT data_type, COUNT(*) as cnt
        FROM scan_items
        WHERE scan_id IN (SELECT id FROM scans WHERE user_id = ?)
        GROUP BY data_type ORDER BY cnt DESC LIMIT 6
    """, (session["user_id"],)).fetchall()

    limit = PLAN_LIMITS.get(user["plan"], 20)
    _, used, _ = check_rate_limit(session["user_id"], user["plan"])

    return render_template("dashboard.html",
        user=user, scans=scans, stats=stats,
        chart_scans=[dict(r) for r in reversed(chart_scans)],
        type_freq=type_freq,
        limit=limit, used=used,
    )


@main.route("/scan", methods=["GET", "POST"])
@login_required
@csrf_protect
def scan():
    db   = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()

    if request.method == "POST":
        allowed, used, limit = check_rate_limit(session["user_id"], user["plan"])
        if not allowed:
            flash(f"Limite mensal atingido ({limit} scans para o plano {user['plan']}). Faça upgrade.", "error")
            return redirect(url_for("main.pricing"))

        filename = request.form.get("filename", "").strip() or "Scan Manual"
        file     = request.files.get("file")

        if file and file.filename:
            ext = file.filename.rsplit(".", 1)[-1].lower()
            if ext not in ("txt", "pdf", "docx"):
                flash("Formato não suportado. Use .txt, .pdf ou .docx", "error")
                return render_template("scan.html", user=user, limit=PLAN_LIMITS.get(user["plan"],20), used=0)
            text, source_type = extract_text_from_file(file)
            if not filename or filename == "Scan Manual":
                filename = file.filename
        else:
            text        = request.form.get("text", "").strip()
            source_type = "text"

        if not text:
            flash("Nenhum conteúdo para analisar.", "error")
            return render_template("scan.html", user=user, limit=PLAN_LIMITS.get(user["plan"],20), used=0)

        if len(text) > 100000:
            flash("Conteúdo muito longo. Limite: 100.000 caracteres.", "error")
            return render_template("scan.html", user=user, limit=PLAN_LIMITS.get(user["plan"],20), used=0)

        result = scan_text(session["user_id"], filename, text, source_type)
        return redirect(url_for("main.scan_detail", scan_id=result["scan_id"]))

    limit = PLAN_LIMITS.get(user["plan"], 20)
    _, used, _ = check_rate_limit(session["user_id"], user["plan"])
    return render_template("scan.html", user=user, limit=limit, used=used)


@main.route("/scan/<int:scan_id>")
@login_required
def scan_detail(scan_id):
    db   = get_db()
    scan = db.execute(
        "SELECT * FROM scans WHERE id = ? AND user_id = ?",
        (scan_id, session["user_id"])
    ).fetchone()
    if not scan:
        flash("Scan não encontrado.", "error")
        return redirect(url_for("main.dashboard"))
    details = json.loads(scan["details"]) if scan["details"] else []
    return render_template("scan_detail.html", scan=scan, details=details)


@main.route("/scan/<int:scan_id>/delete", methods=["POST"])
@login_required
@csrf_protect
def delete_scan(scan_id):
    db = get_db()
    db.execute("DELETE FROM scans WHERE id = ? AND user_id = ?", (scan_id, session["user_id"]))
    db.commit()
    flash("Scan excluído.", "success")
    return redirect(url_for("main.history"))


@main.route("/scan/<int:scan_id>/export-pdf")
@login_required
def export_pdf(scan_id):
    db   = get_db()
    scan = db.execute(
        "SELECT * FROM scans WHERE id = ? AND user_id = ?",
        (scan_id, session["user_id"])
    ).fetchone()
    if not scan:
        abort(404)
    details  = json.loads(scan["details"]) if scan["details"] else []
    from pdf_report import generate_pdf_report
    pdf_bytes = generate_pdf_report(dict(scan), details, session["username"])
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"relatorio-lgpd-{scan_id}.pdf"
    )


@main.route("/scan/<int:scan_id>/anonymized")
@login_required
def view_anonymized(scan_id):
    db   = get_db()
    scan = db.execute(
        "SELECT * FROM scans WHERE id = ? AND user_id = ?",
        (scan_id, session["user_id"])
    ).fetchone()
    if not scan:
        abort(404)
    details = json.loads(scan["details"]) if scan["details"] else []
    return render_template("anonymized.html", scan=scan, details=details)


@main.route("/history")
@login_required
def history():
    db          = get_db()
    q           = request.args.get("q", "").strip()
    risk_filter = request.args.get("risk", "")
    page        = max(1, int(request.args.get("page", 1)))
    per_page    = 15
    offset      = (page - 1) * per_page

    base_where = "WHERE user_id = ?"
    params     = [session["user_id"]]

    if q:
        base_where += " AND filename LIKE ?"
        params.append(f"%{q}%")
    if risk_filter:
        base_where += " AND risk_level = ?"
        params.append(risk_filter)

    total = db.execute(f"SELECT COUNT(*) FROM scans {base_where}", params).fetchone()[0]
    scans = db.execute(
        f"SELECT * FROM scans {base_where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [per_page, offset]
    ).fetchall()

    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template("history.html",
        scans=scans, q=q, risk_filter=risk_filter,
        page=page, total_pages=total_pages, total=total,
    )


@main.route("/profile")
@login_required
def profile():
    db     = get_db()
    user   = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    tokens = db.execute(
        "SELECT * FROM api_tokens WHERE user_id = ? ORDER BY created_at DESC",
        (session["user_id"],)
    ).fetchall()
    limit = PLAN_LIMITS.get(user["plan"], 20)
    _, used, _ = check_rate_limit(session["user_id"], user["plan"])
    return render_template("profile.html", user=user, tokens=tokens, limit=limit, used=used)


@main.route("/token/create", methods=["POST"])
@login_required
@csrf_protect
def create_token():
    name  = request.form.get("token_name", "").strip() or "Meu Token"
    token = secrets.token_hex(32)
    db    = get_db()
    db.execute(
        "INSERT INTO api_tokens (user_id, token, name) VALUES (?, ?, ?)",
        (session["user_id"], token, name)
    )
    db.commit()
    flash(f"Token criado: {token}  (copie agora, não será exibido novamente)", "success")
    return redirect(url_for("main.profile"))


@main.route("/token/<int:token_id>/delete", methods=["POST"])
@login_required
@csrf_protect
def delete_token(token_id):
    db = get_db()
    db.execute("DELETE FROM api_tokens WHERE id = ? AND user_id = ?", (token_id, session["user_id"]))
    db.commit()
    flash("Token excluído.", "success")
    return redirect(url_for("main.profile"))


# ── API ───────────────────────────────────────────────────────────────────────

api = Blueprint("api", __name__, url_prefix="/api/v1")

def api_auth_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("X-API-Token") or request.args.get("token")
        if not token:
            return jsonify({"error": "Token não fornecido."}), 401
        db  = get_db()
        row = db.execute("SELECT * FROM api_tokens WHERE token = ?", (token,)).fetchone()
        if not row:
            return jsonify({"error": "Token inválido."}), 403
        db.execute("UPDATE api_tokens SET last_used = ? WHERE id = ?",
                   (datetime.now().isoformat(), row["id"]))
        db.commit()
        request.api_user_id = row["user_id"]
        return f(*args, **kwargs)
    return decorated


@api.route("/scan", methods=["POST"])
@api_auth_required
def api_scan():
    data     = request.get_json(silent=True) or {}
    text     = data.get("text", "")
    filename = data.get("filename", "API Scan")
    if not text:
        return jsonify({"error": "Campo 'text' obrigatório."}), 400
    db      = get_db()
    user    = db.execute("SELECT * FROM users WHERE id = ?", (request.api_user_id,)).fetchone()
    allowed, used, limit = check_rate_limit(request.api_user_id, user["plan"])
    if not allowed:
        return jsonify({"error": f"Limite mensal atingido ({limit} scans)."}), 429
    result = scan_text(request.api_user_id, filename, text, source_type="api")
    return jsonify({
        "scan_id":       result["scan_id"],
        "total_matches": result["total_matches"],
        "risk_level":    result["risk_level"],
        "results":       result["results"],
    })


@api.route("/scans", methods=["GET"])
@api_auth_required
def api_list_scans():
    db    = get_db()
    scans = db.execute(
        "SELECT id, filename, total_matches, risk_level, created_at FROM scans WHERE user_id = ? ORDER BY created_at DESC LIMIT 20",
        (request.api_user_id,)
    ).fetchall()
    return jsonify([dict(s) for s in scans])


app.register_blueprint(main)
app.register_blueprint(api)

if __name__ == "__main__":
    debug = os.environ.get("FLASK_ENV", "development") == "development"
    app.run(debug=debug, host="0.0.0.0", port=int(os.environ.get("PORT", 7777)))
