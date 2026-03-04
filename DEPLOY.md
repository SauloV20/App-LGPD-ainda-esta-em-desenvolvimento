# 🚀 Guia de Deploy — ShieldScan

## Opção 1: Railway (recomendado — mais simples)

### 1. Criar conta
Acesse https://railway.app e crie conta com GitHub.

### 2. Subir o código no GitHub
```bash
git init
git add .
git commit -m "ShieldScan v1.0"
git remote add origin https://github.com/SEU_USUARIO/shieldscan.git
git push -u origin main
```

### 3. Criar projeto no Railway
- Clique em **New Project → Deploy from GitHub repo**
- Selecione o repositório `shieldscan`
- Railway detecta automaticamente o `Procfile`

### 4. Configurar variáveis de ambiente
No painel do Railway → Variables, adicione:

| Variável | Valor |
|----------|-------|
| `SECRET_KEY` | (gere com `python -c "import secrets; print(secrets.token_hex(32))"`) |
| `STRIPE_SECRET_KEY` | `sk_live_...` |
| `STRIPE_PUBLISHABLE_KEY` | `pk_live_...` |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` |
| `STRIPE_PRO_PRICE_ID` | `price_...` |
| `STRIPE_ENT_PRICE_ID` | `price_...` |
| `APP_URL` | `https://seuapp.railway.app` |
| `FLASK_ENV` | `production` |

### 5. Domínio
Em **Settings → Domains**, adicione seu domínio personalizado.

---

## Opção 2: Render.com

### 1. Criar conta em https://render.com

### 2. New → Web Service → Connect GitHub

### 3. Configurações:
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `python init_db.py && gunicorn app:app --bind 0.0.0.0:$PORT --workers 2`

### 4. Adicionar variáveis de ambiente (mesmo da tabela acima)

---

## Configurar Stripe

### 1. Criar conta em https://stripe.com/br

### 2. Criar produtos
- Dashboard → Products → Add Product
- **Produto 1:** ShieldScan Pro — R$ 49/mês (recorrente)
  - Copie o **Price ID** → `STRIPE_PRO_PRICE_ID`
- **Produto 2:** ShieldScan Enterprise — R$ 199/mês (recorrente)
  - Copie o **Price ID** → `STRIPE_ENT_PRICE_ID`

### 3. Obter chaves de API
- Dashboard → Developers → API keys
- Copie `Secret key` → `STRIPE_SECRET_KEY`
- Copie `Publishable key` → `STRIPE_PUBLISHABLE_KEY`

### 4. Configurar webhook
- Dashboard → Developers → Webhooks → Add endpoint
- **URL:** `https://seudominio.com/billing/webhook`
- **Eventos a escutar:**
  - `checkout.session.completed`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`
  - `invoice.payment_failed`
- Copie o **Signing secret** → `STRIPE_WEBHOOK_SECRET`

### 5. Testar localmente com Stripe CLI
```bash
# Instalar Stripe CLI: https://stripe.com/docs/stripe-cli
stripe login
stripe listen --forward-to localhost:7777/billing/webhook
```

---

## Checklist pré-lançamento

- [ ] `SECRET_KEY` definido e seguro
- [ ] Stripe em modo **Live** (não test)
- [ ] Webhook configurado e testado
- [ ] Domínio com HTTPS ativo
- [ ] `init_db.py` rodou no servidor
- [ ] Testar fluxo completo: cadastro → scan → checkout → dashboard

---

## Rodar localmente com variáveis de ambiente

Crie um arquivo `.env` (baseado em `.env.example`) e rode:

```bash
# Windows PowerShell
$env:SECRET_KEY="sua-chave"
$env:STRIPE_SECRET_KEY="sk_test_..."
python app.py

# Linux/Mac
export SECRET_KEY="sua-chave"
export STRIPE_SECRET_KEY="sk_test_..."
python app.py
```
