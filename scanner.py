import re
import json
import io
from database import get_db

# ── Planos e limites ─────────────────────────────────────────────────────────
PLAN_LIMITS = {
    "free":       20,
    "pro":        500,
    "enterprise": 999999,
}

# ── Padrões LGPD ─────────────────────────────────────────────────────────────
PATTERNS = {
    "CPF":               (r"\b\d{3}[\.\s]?\d{3}[\.\s]?\d{3}[-\s]?\d{2}\b",                          "alto"),
    "CNPJ":              (r"\b\d{2}[\.\s]?\d{3}[\.\s]?\d{3}[\/\s]?\d{4}[-\s]?\d{2}\b",              "alto"),
    "RG":                (r"\b\d{1,2}[\.\s]?\d{3}[\.\s]?\d{3}[-\s]?[\dXx]\b",                       "alto"),
    "Email":             (r"\b[\w\.-]+@[\w\.-]+\.\w{2,}\b",                                           "médio"),
    "Telefone":          (r"\(?\d{2}\)?\s?\d{4,5}[-\s]?\d{4}\b",                                     "médio"),
    "Data de Nascimento":(r"\b\d{2}[\/\-\.]\d{2}[\/\-\.]\d{4}\b",                                    "médio"),
    "CEP":               (r"\b\d{5}[-\s]?\d{3}\b",                                                    "baixo"),
    "Cartão de Crédito": (r"\b(?:\d{4}[\s\-]?){3}\d{4}\b",                                           "crítico"),
    "IP":                (r"\b(?:\d{1,3}\.){3}\d{1,3}\b",                                             "baixo"),
    "Passaporte":        (r"\b[A-Z]{2}\d{6}\b",                                                       "alto"),
    "Título de Eleitor": (r"\b\d{4}\s?\d{4}\s?\d{4}\b",                                              "alto"),
    "PIS/PASEP":         (r"\b\d{3}[\.\s]?\d{5}[\.\s]?\d{2}[-\s]?\d\b",                             "alto"),
    "Chave Pix":         (r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b", "crítico"),
}

RISK_ORDER = {"nenhum": 0, "baixo": 1, "médio": 2, "alto": 3, "crítico": 4}

RISK_COLORS = {
    "nenhum":   "#00ff88",
    "baixo":    "#00ff88",
    "médio":    "#ffd166",
    "alto":     "#ff8c42",
    "crítico":  "#ff4455",
}


# ── Validações ────────────────────────────────────────────────────────────────

def validate_cpf(cpf: str) -> bool:
    d = re.sub(r"\D", "", cpf)
    if len(d) != 11 or d == d[0] * 11:
        return False
    for i in range(2):
        total = sum(int(d[j]) * (10 + i - j) for j in range(9 + i))
        if (total * 10 % 11) % 10 != int(d[9 + i]):
            return False
    return True


def validate_cnpj(cnpj: str) -> bool:
    d = re.sub(r"\D", "", cnpj)
    if len(d) != 14 or d == d[0] * 14:
        return False
    w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    w2 = [6] + w1
    for w, pos in [(w1, 12), (w2, 13)]:
        r = sum(int(d[i]) * w[i] for i in range(len(w))) % 11
        if (0 if r < 2 else 11 - r) != int(d[pos]):
            return False
    return True


# ── Extração de texto de arquivos ─────────────────────────────────────────────

def extract_text_from_file(file_storage) -> tuple[str, str]:
    """Returns (text, source_type)"""
    filename = file_storage.filename.lower()

    if filename.endswith(".txt"):
        return file_storage.read().decode("utf-8", errors="ignore"), "txt"

    if filename.endswith(".pdf"):
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(file_storage.read())) as pdf:
                text = "\n".join(p.extract_text() or "" for p in pdf.pages)
            return text, "pdf"
        except Exception as e:
            return f"[Erro ao ler PDF: {e}]", "pdf"

    if filename.endswith(".docx"):
        try:
            import docx
            doc = docx.Document(io.BytesIO(file_storage.read()))
            text = "\n".join(p.text for p in doc.paragraphs)
            return text, "docx"
        except Exception as e:
            return f"[Erro ao ler DOCX: {e}]", "docx"

    return "", "unknown"


# ── Anonimização ──────────────────────────────────────────────────────────────

def anonymize_text(text: str, results: list) -> str:
    anonymized = text
    for item in results:
        label = item["type"]
        for match in item["matches"]:
            replacement = f"[{label.upper()} REMOVIDO]"
            anonymized = anonymized.replace(match, replacement)
    return anonymized


# ── Rate limiting ─────────────────────────────────────────────────────────────

def check_rate_limit(user_id: int, plan: str) -> tuple[bool, int, int]:
    """Returns (allowed, used, limit)"""
    from datetime import datetime
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    limit = PLAN_LIMITS.get(plan, 20)
    current_month = datetime.now().strftime("%Y-%m")

    # Reset mensal
    if user["month_reset"] != current_month:
        db.execute(
            "UPDATE users SET scans_this_month = 0, month_reset = ? WHERE id = ?",
            (current_month, user_id)
        )
        db.commit()
        return True, 0, limit

    used = user["scans_this_month"]
    return used < limit, used, limit


# ── Scanner principal ─────────────────────────────────────────────────────────

def scan_text(user_id: int, filename: str, text: str, source_type: str = "text") -> dict:
    results = []
    highest_risk = "nenhum"

    for label, (regex, risk) in PATTERNS.items():
        raw_matches = re.findall(regex, text, re.IGNORECASE)
        if not raw_matches:
            continue

        validated = []
        for m in raw_matches:
            if label == "CPF" and not validate_cpf(m):
                continue
            if label == "CNPJ" and not validate_cnpj(m):
                continue
            validated.append(m)

        if not validated:
            continue

        unique = list(dict.fromkeys(validated))
        results.append({
            "type":    label,
            "risk":    risk,
            "count":   len(unique),
            "matches": unique,
        })

        if RISK_ORDER[risk] > RISK_ORDER[highest_risk]:
            highest_risk = risk

    total_matches = sum(r["count"] for r in results)
    anonymized = anonymize_text(text, results)

    db = get_db()
    cursor = db.execute(
        """INSERT INTO scans
           (user_id, filename, source_type, total_matches, risk_level, details, raw_text, anonymized_text)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            user_id, filename, source_type, total_matches,
            highest_risk,
            json.dumps(results, ensure_ascii=False),
            text[:10000],
            anonymized[:10000],
        )
    )
    scan_id = cursor.lastrowid

    for item in results:
        for value in item["matches"]:
            db.execute(
                "INSERT INTO scan_items (scan_id, data_type, value) VALUES (?, ?, ?)",
                (scan_id, item["type"], value)
            )

    db.execute(
        "UPDATE users SET scans_used = scans_used + 1, scans_this_month = scans_this_month + 1 WHERE id = ?",
        (user_id,)
    )
    db.commit()

    return {
        "scan_id":       scan_id,
        "results":       results,
        "total_matches": total_matches,
        "risk_level":    highest_risk,
        "filename":      filename,
        "anonymized":    anonymized,
    }
