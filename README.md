# 🛡️ ShieldScan — LGPD Scanner SaaS

Ferramenta web para identificação automática de dados pessoais em textos,
com base na legislação LGPD (Lei Geral de Proteção de Dados — Lei 13.709/2018).

---

## ✨ Funcionalidades

| Feature | Descrição |
|---|---|
| 🔐 Autenticação | Cadastro, login por usuário ou e-mail, logout seguro |
| 🔍 Scanner LGPD | Detecção de 13 tipos de dados pessoais |
| ✅ Validação real | CPF e CNPJ validados por dígitos verificadores |
| 🎯 Nível de risco | Classificação: baixo / médio / alto / crítico |
| 📊 Dashboard | Estatísticas gerais da conta |
| 📋 Histórico | Todos os scans com detalhes |
| 👤 Perfil | Informações da conta |
| 🛢️ SQLite | Banco de dados local, sem dependências externas |

## 🕵️ Tipos de Dados Detectados

- CPF *(com validação de dígitos verificadores)*
- CNPJ *(com validação de dígitos verificadores)*
- RG
- E-mail
- Telefone
- Data de nascimento
- CEP
- **Cartão de crédito** *(risco crítico)*
- Endereço IP
- Passaporte
- Título de eleitor
- PIS/PASEP
- **Chave Pix (UUID)** *(risco crítico)*

---

## 🚀 Como rodar

### 1. Instalar dependências
```bash
pip install -r requirements.txt
```

### 2. Inicializar banco de dados
```bash
python init_db.py
```

### 3. Rodar a aplicação
```bash
python app.py
```

### 4. Acessar
```
http://127.0.0.1:7777
```

---

## 📁 Estrutura do projeto

```
lgpd_saas/
├── app.py              # Aplicação Flask + rotas principais
├── auth.py             # Blueprint de autenticação
├── scanner.py          # Motor de detecção LGPD
├── database.py         # Conexão SQLite com Flask g
├── init_db.py          # Criação das tabelas
├── requirements.txt
│
├── templates/
│   ├── base.html       # Base HTML
│   ├── app_base.html   # Base com sidebar (páginas autenticadas)
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── scan.html
│   ├── scan_detail.html
│   ├── history.html
│   └── profile.html
│
└── static/
    └── style.css       # Design system completo
```

---

## 🔒 Segurança implementada

- Senhas com hash bcrypt (werkzeug)
- `secret_key` via variável de ambiente `SECRET_KEY`
- Conexões de banco fechadas corretamente via `teardown_appcontext`
- Proteção contra SQL injection via parâmetros preparados
- Validação de campos no servidor
- Tratamento de `IntegrityError` para usuários duplicados
- Sessão isolada por usuário nos scans

## ⚙️ Variáveis de ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `SECRET_KEY` | aleatório a cada restart | Chave de sessão Flask |

---

## 🗺️ Próximos passos sugeridos

- [ ] Upload de arquivos (.txt, .pdf, .docx)
- [ ] Exportar relatório em PDF
- [ ] API REST com autenticação por token
- [ ] Rate limiting por plano
- [ ] Anonimização automática dos dados encontrados
- [ ] Notificações por e-mail em scans críticos
