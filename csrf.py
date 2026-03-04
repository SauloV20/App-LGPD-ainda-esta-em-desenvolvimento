import secrets
import hashlib
from functools import wraps
from flask import session, request, abort


def generate_csrf_token() -> str:
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


def validate_csrf():
    token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    if not token or token != session.get("csrf_token"):
        abort(403)


def csrf_protect(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            validate_csrf()
        return f(*args, **kwargs)
    return decorated
