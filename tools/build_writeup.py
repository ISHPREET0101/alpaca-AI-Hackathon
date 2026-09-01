# ruff: noqa: E501 - long literal copy mirrors the rendered one-page artifact.
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = Path("output/pdf/Aegis_Alpha_Technical_Writeup.pdf")
INK = colors.HexColor("#070B10")
BLUE = colors.HexColor("#3D8DFF")
CYAN = colors.HexColor("#27C4F4")
MUTED = colors.HexColor("#58636F")
PALE = colors.HexColor("#E8F7FC")
RULE = colors.HexColor("#C4CBD2")


def section(title: str, body: str, styles: dict[str, ParagraphStyle]) -> list[object]:
    return [
        Paragraph(title.upper(), styles["section"]),
        Spacer(1, 1.4 * mm),
        Paragraph(body, styles["body"]),
        Spacer(1, 3.3 * mm),
    ]


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    custom = {
        "eyebrow": ParagraphStyle(
            "eyebrow",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9,
            textColor=CYAN,
            spaceAfter=3,
        ),
        "title": ParagraphStyle(
            "title",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=25,
            leading=27,
            textColor=colors.white,
            alignment=TA_LEFT,
            spaceAfter=5,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10.2,
            leading=13,
            textColor=colors.HexColor("#D7E0E7"),
        ),
        "section": ParagraphStyle(
            "section",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=8.2,
            leading=10,
            textColor=BLUE,
            spaceAfter=0,
        ),
        "body": ParagraphStyle(
            "body",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8.45,
            leading=11.2,
            textColor=INK,
            spaceAfter=0,
        ),
        "risk": ParagraphStyle(
            "risk",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8.2,
            leading=10.7,
            textColor=INK,
        ),
        "small": ParagraphStyle(
            "small",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=6.6,
            leading=8,
            textColor=MUTED,
        ),
    }

    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=10 * mm,
    )
    story = []
    hero = Table(
        [
            [
                Paragraph("ALPACA AI TRADING AGENTS HACKATHON", custom["eyebrow"]),
            ],
            [
                Paragraph("Aegis Alpha", custom["title"]),
            ],
            [
                Paragraph(
                    "An autonomous, explainable SPY/QQQ options agent where AI ranks opportunities but deterministic Python controls every order.",
                    custom["subtitle"],
                ),
            ],
        ],
        colWidths=[182 * mm],
    )
    hero.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), INK),
                ("LEFTPADDING", (0, 0), (-1, -1), 7 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7 * mm),
                ("TOPPADDING", (0, 0), (-1, 0), 5 * mm),
                ("BOTTOMPADDING", (0, 2), (-1, 2), 6 * mm),
                ("TOPPADDING", (0, 1), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, 1), 1 * mm),
            ]
        )
    )
    story.extend([hero, Spacer(1, 5 * mm)])

    left = [
        *section(
            "Problem and original idea",
            "AI-generated trading theses can sound confident while inputs are stale, liquidity is weak, or portfolio risk is already exhausted. Aegis Alpha separates <b>judgment</b> from <b>authority</b>: an optional constrained ranker may choose among valid candidates, but it cannot weaken, skip, or rewrite a risk gate. Any missing data, malformed schema, contradictory signal, API error, or reconciliation mismatch becomes <b>NO_TRADE</b>.",
            custom,
        ),
        *section(
            "Fixed strategy",
            "Five-minute SPY and QQQ bars feed EMA trend, VWAP position, RSI, and realized-volatility features. The regime is bullish, bearish, or neutral. The candidate layer emits only same-expiry bull-call or bear-put debit spreads with 7-21 DTE and a long-leg absolute delta near 0.35-0.55. The executor submits one atomic two-leg limit order with a deterministic client_order_id.",
            custom,
        ),
        *section(
            "Agent cycle",
            "<b>Market Data -> Regime -> Candidate -> Critic -> Risk Guard -> Executor -> Monitor -> Audit Log.</b> The critic rejects incomplete contracts, unsupported structures, weak liquidity, contradictory signals, and existing exposure. The monitor reprices open spreads and closes at +40%, -30%, signal invalidation, or the 15:45 ET risk cutoff.",
            custom,
        ),
        *section(
            "Infrastructure",
            "<b>alpaca-py</b> is the primary typed Trading and Market Data client. SQLite stores decisions, raw errors, orders, fills, snapshots, locks, and reconciliation evidence. The Alpaca CLI is isolated behind a JSON adapter and independently checks account, orders, and positions. Any SDK/CLI disagreement halts new orders. Alpaca MCP is configured only for judge-facing inspection; it is outside the execution path.",
            custom,
        ),
    ]

    risk_rows = [
        ["Per trade", "min($500, 0.5% equity)"],
        ["Open risk", "$1,500 across max 3 positions"],
        ["Frequency", "1 new trade / underlying / day"],
        ["Cooldown", "30 minutes after order or exit"],
        ["Quotes", "&lt;=60 sec old; width &lt;=15% midpoint"],
        ["Daily halt", "1.5% equity drawdown"],
        ["Endpoint", "Paper only; live settings rejected"],
        ["Kill switch", "Blocks every new order"],
    ]
    risk_table = Table(
        [[Paragraph("RISK GATE", custom["section"]), Paragraph("FIXED LIMIT", custom["section"])]]
        + [[Paragraph(a, custom["risk"]), Paragraph(b, custom["body"])] for a, b in risk_rows],
        colWidths=[34 * mm, 48 * mm],
    )
    risk_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PALE),
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2.2 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2.2 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 1.8 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8 * mm),
            ]
        )
    )
    right = [
        risk_table,
        Spacer(1, 4 * mm),
        *section(
            "Verification status",
            "<b>Locally verified:</b> 28 tests passed, 5 synthetic market regimes replayed, 72% measured code coverage, dry-run submission lock, idempotency, forced exits, malformed-AI failure, sanitized export, and multi-leg request construction. <b>Credential-gated:</b> one paper integration test is skipped until Alpaca credentials exist; no filled trade or paper P&amp;L is claimed.",
            custom,
        ),
        *section(
            "Demo and disclosure",
            "The read-only Streamlit dashboard shows equity, P&amp;L, positions, the latest thesis, critic result, risk checks, order timeline, and reconciliation status from sanitized snapshots. This is a paper-trading prototype for demonstration and research. It is not financial advice and does not establish real-market profitability.",
            custom,
        ),
    ]

    columns = Table([[left, right]], colWidths=[91 * mm, 87 * mm], hAlign="LEFT")
    columns.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 5 * mm),
                ("LEFTPADDING", (1, 0), (1, 0), 5 * mm),
                ("RIGHTPADDING", (1, 0), (1, 0), 0),
                ("LINEBEFORE", (1, 0), (1, 0), 0.7, RULE),
            ]
        )
    )
    story.extend([columns, Spacer(1, 2 * mm)])
    story.append(
        Paragraph(
            "Sources: Alpaca Trading API, Market Data API, alpaca-py, Alpaca CLI and Alpaca MCP documentation. Full links and operating instructions are in README.md and docs/.",
            custom["small"],
        )
    )
    doc.build(story)


if __name__ == "__main__":
    main()
