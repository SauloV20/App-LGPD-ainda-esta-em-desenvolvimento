import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT


# ── Color palette ─────────────────────────────────────────────────────────────
C_BG       = colors.HexColor("#0a0c0f")
C_ACCENT   = colors.HexColor("#00ff88")
C_TEXT     = colors.HexColor("#e2e8f0")
C_MUTED    = colors.HexColor("#5a6475")
C_RED      = colors.HexColor("#ff4455")
C_ORANGE   = colors.HexColor("#ff8c42")
C_YELLOW   = colors.HexColor("#ffd166")
C_GREEN    = colors.HexColor("#00ff88")
C_DARK     = colors.HexColor("#111417")
C_BORDER   = colors.HexColor("#222830")
C_WHITE    = colors.white

RISK_COLORS_MAP = {
    "nenhum":  C_GREEN,
    "baixo":   C_GREEN,
    "médio":   C_YELLOW,
    "alto":    C_ORANGE,
    "crítico": C_RED,
}

RISK_LABELS = {
    "nenhum":  "NENHUM",
    "baixo":   "BAIXO",
    "médio":   "MÉDIO",
    "alto":    "ALTO",
    "crítico": "CRÍTICO",
}


def build_styles():
    base = getSampleStyleSheet()
    styles = {}

    styles["title"] = ParagraphStyle(
        "title",
        fontName="Helvetica-Bold",
        fontSize=22,
        textColor=C_WHITE,
        spaceAfter=4,
        leading=26,
    )
    styles["subtitle"] = ParagraphStyle(
        "subtitle",
        fontName="Helvetica",
        fontSize=9,
        textColor=C_ACCENT,
        spaceAfter=0,
        letterSpacing=1.5,
    )
    styles["section"] = ParagraphStyle(
        "section",
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=C_WHITE,
        spaceBefore=18,
        spaceAfter=8,
    )
    styles["body"] = ParagraphStyle(
        "body",
        fontName="Helvetica",
        fontSize=9,
        textColor=C_MUTED,
        spaceAfter=4,
        leading=14,
    )
    styles["mono"] = ParagraphStyle(
        "mono",
        fontName="Courier",
        fontSize=8,
        textColor=C_TEXT,
        spaceAfter=2,
        leading=12,
    )
    styles["label"] = ParagraphStyle(
        "label",
        fontName="Helvetica-Bold",
        fontSize=7,
        textColor=C_MUTED,
        spaceAfter=2,
        letterSpacing=1.2,
    )
    return styles


def generate_pdf_report(scan: dict, details: list, username: str) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2*cm,
        rightMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm,
    )

    styles = build_styles()
    risk = scan["risk_level"]
    risk_color = RISK_COLORS_MAP.get(risk, C_GREEN)
    story = []

    # ── Header block ──────────────────────────────────────────────────────────
    header_data = [[
        Paragraph("🛡️ ShieldScan", styles["title"]),
        Paragraph(f"RELATÓRIO LGPD", styles["subtitle"]),
    ]]
    header_table = Table(header_data, colWidths=["60%", "40%"])
    header_table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), C_BG),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [C_BG]),
        ("TOPPADDING",  (0, 0), (-1, -1), 16),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
        ("LEFTPADDING",  (0, 0), (-1, -1), 16),
        ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",       (1, 0), (1, 0), "RIGHT"),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 12))

    # ── Meta info ─────────────────────────────────────────────────────────────
    meta = [
        ["DOCUMENTO",  scan["filename"]],
        ["USUÁRIO",    username],
        ["DATA",       scan["created_at"][:16] if "created_at" in scan else datetime.now().strftime("%Y-%m-%d %H:%M")],
        ["FONTE",      scan.get("source_type", "text").upper()],
    ]
    meta_table = Table(meta, colWidths=["30%", "70%"])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_DARK),
        ("TEXTCOLOR",     (0, 0), (0, -1), C_MUTED),
        ("TEXTCOLOR",     (1, 0), (1, -1), C_TEXT),
        ("FONTNAME",      (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",      (1, 0), (1, -1), "Courier"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("LINEBELOW",     (0, 0), (-1, -2), 0.5, C_BORDER),
        ("LETTERSPACING", (0, 0), (0, -1), 1.2),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 16))

    # ── Risk summary ──────────────────────────────────────────────────────────
    story.append(Paragraph("RESUMO DE RISCO", styles["label"]))
    summary_data = [[
        Paragraph(f"{RISK_LABELS.get(risk, risk.upper())}", ParagraphStyle(
            "risk_val", fontName="Helvetica-Bold", fontSize=20,
            textColor=risk_color, leading=24,
        )),
        Paragraph(f"{scan['total_matches']}\nocorrências detectadas", ParagraphStyle(
            "occ", fontName="Helvetica", fontSize=10,
            textColor=C_MUTED, leading=14,
        )),
        Paragraph(f"{len(details)}\ntipo(s) de dados", ParagraphStyle(
            "types", fontName="Helvetica", fontSize=10,
            textColor=C_MUTED, leading=14,
        )),
    ]]
    summary_table = Table(summary_data, colWidths=["33%", "33%", "34%"])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_DARK),
        ("TOPPADDING",    (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING",   (0, 0), (-1, -1), 14),
        ("LINEAFTER",     (0, 0), (1, 0), 0.5, C_BORDER),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 20))

    # ── Details ───────────────────────────────────────────────────────────────
    if details:
        story.append(Paragraph("DADOS IDENTIFICADOS", styles["label"]))
        story.append(Spacer(1, 6))

        for item in details:
            item_risk_color = RISK_COLORS_MAP.get(item["risk"], C_GREEN)
            matches_text = "   ·   ".join(item["matches"][:10])
            if len(item["matches"]) > 10:
                matches_text += f"   ... +{len(item['matches']) - 10} mais"

            row = [[
                Paragraph(item["type"], ParagraphStyle(
                    "itype", fontName="Helvetica-Bold", fontSize=10, textColor=C_TEXT,
                )),
                Paragraph(item["risk"].upper(), ParagraphStyle(
                    "irisk", fontName="Helvetica-Bold", fontSize=7,
                    textColor=item_risk_color, letterSpacing=1,
                )),
                Paragraph(f"{item['count']} ocorrência(s)", ParagraphStyle(
                    "icount", fontName="Helvetica", fontSize=8, textColor=C_MUTED,
                )),
            ]]
            row_table = Table(row, colWidths=["40%", "25%", "35%"])
            row_table.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), C_DARK),
                ("TOPPADDING",    (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING",   (0, 0), (-1, -1), 12),
                ("LINEAFTER",     (0, 0), (1, 0), 0.5, C_BORDER),
                ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ]))

            matches_row = [[Paragraph(matches_text, ParagraphStyle(
                "matches", fontName="Courier", fontSize=7.5,
                textColor=C_MUTED, leading=12,
            ))]]
            matches_table = Table(matches_row, colWidths=["100%"])
            matches_table.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), C_BG),
                ("TOPPADDING",    (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING",   (0, 0), (-1, -1), 12),
                ("LINEBELOW",     (0, 0), (-1, -1), 0.5, C_BORDER),
            ]))

            story.append(KeepTogether([row_table, matches_table, Spacer(1, 4)]))

    else:
        story.append(Paragraph(
            "✓  Nenhum dado pessoal identificado no texto analisado.",
            ParagraphStyle("ok", fontName="Helvetica", fontSize=10, textColor=C_GREEN)
        ))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 24))
    story.append(HRFlowable(width="100%", thickness=0.5, color=C_BORDER))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        f"Gerado por ShieldScan  ·  {datetime.now().strftime('%d/%m/%Y %H:%M')}  ·  LGPD Scanner",
        ParagraphStyle("footer", fontName="Helvetica", fontSize=7, textColor=C_MUTED, alignment=TA_CENTER)
    ))
    story.append(Paragraph(
        "Este relatório é de uso interno e deve ser tratado como documento confidencial conforme a Lei 13.709/2018 (LGPD).",
        ParagraphStyle("footer2", fontName="Helvetica", fontSize=6.5, textColor=C_MUTED, alignment=TA_CENTER)
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
