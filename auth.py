from flask import Blueprint, render_template, request, redirect, session, flash, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from sqlite3 import IntegrityError
from functools import wraps
from database import get_db
from csrf import generate_csrf_token, csrf_protect
import re

auth = Blueprint("auth", __name__)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Faça login para continuar.", "error")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[\w\.-]+@[\w\.-]+\.\w{2,}$", email))


@auth.route("/register", methods=["GET", "POST"])
@csrf_protect
def register():
    if "user_id" in session:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm", "")

        errors = []
        if not username or len(username) < 3:
            errors.append("Usuário deve ter ao menos 3 caracteres.")
        if not re.match(r"^[\w]+$", username):
            errors.append("Usuário deve conter apenas letras, números e _.")
        if not is_valid_email(email):
            errors.append("E-mail inválido.")
        if len(password) < 6:
            errors.append("Senha deve ter ao menos 6 caracteres.")
        if password != confirm:
            errors.append("As senhas não conferem.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("register.html", username=username, email=email,
                                   csrf_token=generate_csrf_token())

        try:
            db = get_db()
            db.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                (username, email, generate_password_hash(password))
            )
            db.commit()
            flash("Conta criada com sucesso! Faça login.", "success")
            return redirect(url_for("auth.login"))
        except IntegrityError:
            flash("Usuário ou e-mail já cadastrado.", "error")
            return render_template("register.html", username=username, email=email,
                                   csrf_token=generate_csrf_token())

    return render_template("register.html", csrf_token=generate_csrf_token())


@auth.route("/login", methods=["GET", "POST"])
@csrf_protect
def login():
    if "user_id" in session:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password   = request.form.get("password", "")

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ? OR email = ?",
            (identifier, identifier)
        ).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"]  = user["id"]
            session["username"] = user["username"]
            session["plan"]     = user["plan"]
            flash(f"Bem-vindo, {user['username']}!", "success")
            return redirect(url_for("main.dashboard"))

        flash("Credenciais inválidas.", "error")

    return render_template("login.html", csrf_token=generate_csrf_token())


@auth.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@auth.route("/change-password", methods=["GET", "POST"])
@login_required
@csrf_protect
def change_password():
    if request.method == "POST":
        current  = request.form.get("current_password", "")
        new_pass = request.form.get("new_password", "")
        confirm  = request.form.get("confirm_password", "")

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()

        if not check_password_hash(user["password_hash"], current):
            flash("Senha atual incorreta.", "error")
        elif len(new_pass) < 6:
            flash("Nova senha deve ter ao menos 6 caracteres.", "error")
        elif new_pass != confirm:
            flash("As senhas não conferem.", "error")
        else:
            db.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (generate_password_hash(new_pass), session["user_id"])
            )
            db.commit()
            flash("Senha alterada com sucesso!", "success")
            return redirect(url_for("main.profile"))

    return render_template("change_password.html", csrf_token=generate_csrf_token())
