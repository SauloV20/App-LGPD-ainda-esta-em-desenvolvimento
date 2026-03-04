"""
Integração com Stripe para gerenciamento de assinaturas.

Variáveis de ambiente necessárias:
  STRIPE_SECRET_KEY      - Chave secreta da API Stripe (sk_live_... ou sk_test_...)
  STRIPE_PUBLISHABLE_KEY - Chave pública (pk_live_... ou pk_test_...)
  STRIPE_WEBHOOK_SECRET  - Segredo do webhook (whsec_...)
  STRIPE_PRO_PRICE_ID    - Price ID do plano Pro (price_...)
  STRIPE_ENT_PRICE_ID    - Price ID do plano Enterprise (price_...)
  APP_URL                - URL base da aplicação (ex: https://shieldscan.com.br)
"""

import os
from flask import Blueprint, request, redirect, url_for, session, flash, jsonify, render_template
from database import get_db
from auth import login_required
from csrf import csrf_protect

try:
    import stripe
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
    STRIPE_AVAILABLE = bool(stripe.api_key)
except ImportError:
    stripe = None
    STRIPE_AVAILABLE = False

STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
WEBHOOK_SECRET         = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
APP_URL                = os.environ.get("APP_URL", "http://localhost:7777")

# IDs dos preços no Stripe (criar no dashboard stripe.com)
PRICE_IDS = {
    "pro":        os.environ.get("STRIPE_PRO_PRICE_ID", ""),
    "enterprise": os.environ.get("STRIPE_ENT_PRICE_ID", ""),
}

PLAN_NAMES = {
    "free":       "Free",
    "pro":        "Pro",
    "enterprise": "Enterprise",
}

payments = Blueprint("payments", __name__, url_prefix="/billing")


# ── Checkout ──────────────────────────────────────────────────────────────────

@payments.route("/checkout/<plan>")
@login_required
def checkout(plan):
    """Redireciona para o checkout do Stripe."""
    if plan not in PRICE_IDS or not PRICE_IDS[plan]:
        flash("Plano inválido ou não configurado.", "error")
        return redirect(url_for("main.pricing"))

    if not STRIPE_AVAILABLE or not stripe.api_key:
        flash("Pagamentos não configurados ainda. Entre em contato conosco.", "error")
        return redirect(url_for("main.pricing"))

    db   = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()

    try:
        # Criar ou recuperar customer no Stripe
        customer_id = user["stripe_customer_id"] if user["stripe_customer_id"] else None

        if not customer_id:
            customer = stripe.Customer.create(
                email=user["email"],
                name=user["username"],
                metadata={"user_id": user["id"]},
            )
            customer_id = customer.id
            db.execute(
                "UPDATE users SET stripe_customer_id = ? WHERE id = ?",
                (customer_id, user["id"])
            )
            db.commit()

        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": PRICE_IDS[plan], "quantity": 1}],
            mode="subscription",
            success_url=f"{APP_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{APP_URL}/pricing",
            metadata={"user_id": user["id"], "plan": plan},
            subscription_data={
                "metadata": {"user_id": user["id"], "plan": plan}
            },
            locale="pt-BR",
        )
        return redirect(checkout_session.url, code=303)

    except stripe.StripeError as e:
        flash(f"Erro ao iniciar pagamento: {e.user_message}", "error")
        return redirect(url_for("main.pricing"))


@payments.route("/success")
@login_required
def success():
    session_id = request.args.get("session_id")
    return render_template("billing/success.html", session_id=session_id)


@payments.route("/cancel-subscription", methods=["POST"])
@login_required
@csrf_protect
def cancel_subscription():
    db   = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()

    if not user["stripe_subscription_id"]:
        flash("Nenhuma assinatura ativa.", "error")
        return redirect(url_for("main.profile"))

    try:
        stripe.Subscription.modify(
            user["stripe_subscription_id"],
            cancel_at_period_end=True,
        )
        db.execute(
            "UPDATE users SET subscription_status = 'canceling' WHERE id = ?",
            (session["user_id"],)
        )
        db.commit()
        flash("Assinatura cancelada. Você terá acesso até o fim do período atual.", "success")
    except stripe.StripeError as e:
        flash(f"Erro ao cancelar: {e.user_message}", "error")

    return redirect(url_for("main.profile"))


@payments.route("/portal")
@login_required
def customer_portal():
    """Redireciona para o portal do cliente Stripe (gerenciar cartão, faturas, etc)."""
    db   = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()

    if not user["stripe_customer_id"]:
        flash("Nenhuma assinatura encontrada.", "error")
        return redirect(url_for("main.profile"))

    try:
        portal = stripe.billing_portal.Session.create(
            customer=user["stripe_customer_id"],
            return_url=f"{APP_URL}/profile",
        )
        return redirect(portal.url, code=303)
    except stripe.StripeError as e:
        flash(f"Erro ao abrir portal: {e.user_message}", "error")
        return redirect(url_for("main.profile"))


# ── Webhook ───────────────────────────────────────────────────────────────────

@payments.route("/webhook", methods=["POST"])
def webhook():
    """
    Recebe eventos do Stripe e atualiza o banco de dados.
    Configurar no Stripe Dashboard → Webhooks → Add endpoint:
      URL: https://seudominio.com/billing/webhook
      Eventos: customer.subscription.created, updated, deleted
               checkout.session.completed
               invoice.payment_failed
    """
    payload    = request.get_data()
    sig_header = request.headers.get("Stripe-Signature")

    if not WEBHOOK_SECRET:
        # Modo dev: processar sem verificar assinatura
        event = request.get_json()
    else:
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
        except (ValueError, stripe.SignatureVerificationError):
            return jsonify({"error": "Invalid signature"}), 400

    _handle_event(event)
    return jsonify({"status": "ok"})


def _handle_event(event):
    db        = get_db()
    event_type = event["type"]
    data       = event["data"]["object"]

    if event_type == "checkout.session.completed":
        user_id = data.get("metadata", {}).get("user_id")
        plan    = data.get("metadata", {}).get("plan")
        sub_id  = data.get("subscription")
        if user_id and plan:
            db.execute(
                """UPDATE users SET plan = ?, stripe_subscription_id = ?,
                   subscription_status = 'active' WHERE id = ?""",
                (plan, sub_id, user_id)
            )
            db.commit()

    elif event_type in ("customer.subscription.updated",):
        sub     = data
        user    = db.execute(
            "SELECT * FROM users WHERE stripe_subscription_id = ?", (sub["id"],)
        ).fetchone()
        if not user:
            return
        status = sub["status"]
        plan   = sub.get("metadata", {}).get("plan", user["plan"])
        if status == "active":
            db.execute(
                "UPDATE users SET plan = ?, subscription_status = 'active' WHERE id = ?",
                (plan, user["id"])
            )
        elif status in ("canceled", "unpaid", "past_due"):
            db.execute(
                "UPDATE users SET plan = 'free', subscription_status = ? WHERE id = ?",
                (status, user["id"])
            )
        db.commit()

    elif event_type == "customer.subscription.deleted":
        sub  = data
        user = db.execute(
            "SELECT * FROM users WHERE stripe_subscription_id = ?", (sub["id"],)
        ).fetchone()
        if user:
            db.execute(
                """UPDATE users SET plan = 'free', stripe_subscription_id = NULL,
                   subscription_status = 'canceled' WHERE id = ?""",
                (user["id"],)
            )
            db.commit()

    elif event_type == "invoice.payment_failed":
        customer_id = data.get("customer")
        user = db.execute(
            "SELECT * FROM users WHERE stripe_customer_id = ?", (customer_id,)
        ).fetchone()
        if user:
            db.execute(
                "UPDATE users SET subscription_status = 'past_due' WHERE id = ?",
                (user["id"],)
            )
            db.commit()
