from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import io
from datetime import datetime

TEAL = colors.HexColor('#1A7A8A')
PURPLE = colors.HexColor('#764ba2')
LIGHT_GRAY = colors.HexColor('#F7FAFC')
DARK = colors.HexColor('#2D3748')
GRAY = colors.HexColor('#718096')
RED = colors.HexColor('#E53E3E')
GREEN = colors.HexColor('#38A169')
WHITE = colors.white

def generate_settlement_pdf(group, expenses, settlements, category_totals):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    story = []

    # ── HEADER ──
    header_style = ParagraphStyle(
        'Header',
        parent=styles['Normal'],
        fontSize=24,
        textColor=TEAL,
        fontName='Helvetica-Bold',
        alignment=TA_CENTER,
        spaceAfter=4
    )
    sub_style = ParagraphStyle(
        'Sub',
        parent=styles['Normal'],
        fontSize=11,
        textColor=GRAY,
        alignment=TA_CENTER,
        spaceAfter=4
    )
    date_style = ParagraphStyle(
        'Date',
        parent=styles['Normal'],
        fontSize=9,
        textColor=GRAY,
        alignment=TA_CENTER,
        spaceAfter=16
    )

    story.append(Paragraph("💸 SmartSplit AI", header_style))
    story.append(Paragraph(f"Trip Report — {group['name']}", sub_style))
    story.append(Paragraph(f"Members: {group['members']}", sub_style))
    story.append(Paragraph(
        f"Generated on {datetime.now().strftime('%d %B %Y, %I:%M %p')}",
        date_style
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=TEAL, spaceAfter=16))

    # ── SUMMARY CARDS ──
    section_style = ParagraphStyle(
        'Section',
        parent=styles['Normal'],
        fontSize=13,
        textColor=WHITE,
        fontName='Helvetica-Bold',
        alignment=TA_LEFT,
        spaceAfter=8,
        spaceBefore=16,
        backColor=TEAL,
        leftIndent=-4,
        borderPad=6
    )

    total_amount = sum(e['amount'] for e in expenses)
    num_members = len([m.strip() for m in group['members'].split(',')])
    per_person = total_amount / num_members if num_members > 0 else 0

    summary_data = [
        ['Total Spent', 'Per Person', 'Total Expenses', 'Members'],
        [
            f"Rs. {total_amount:,.2f}",
            f"Rs. {per_person:,.2f}",
            str(len(expenses)),
            str(num_members)
        ]
    ]

    summary_table = Table(summary_data, colWidths=[130, 130, 130, 130])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), TEAL),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWHEIGHT', (0, 0), (-1, -1), 28),
        ('BACKGROUND', (0, 1), (-1, 1), LIGHT_GRAY),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, 1), 12),
        ('TEXTCOLOR', (0, 1), (-1, 1), DARK),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('ROUNDEDCORNERS', [6, 6, 6, 6]),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 16))

    # ── EXPENSES TABLE ──
    story.append(Paragraph("  All Expenses", ParagraphStyle(
        'SectionHead', parent=styles['Normal'],
        fontSize=12, textColor=WHITE, fontName='Helvetica-Bold',
        backColor=TEAL, borderPad=8, spaceAfter=8
    )))

    if expenses:
        expense_data = [['#', 'Description', 'Amount', 'Paid By', 'Category']]
        for i, e in enumerate(expenses, 1):
            expense_data.append([
                str(i),
                e['description'],
                f"Rs. {e['amount']:,.2f}",
                e['paid_by'],
                e['category']
            ])

        expense_table = Table(
            expense_data,
            colWidths=[30, 200, 90, 90, 100]
        )
        expense_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), TEAL),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('ALIGN', (4, 0), (4, -1), 'CENTER'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TEXTCOLOR', (0, 1), (-1, -1), DARK),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('ROWHEIGHT', (0, 0), (-1, -1), 22),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (1, 0), (1, -1), 8),
        ]))
        story.append(expense_table)
    else:
        story.append(Paragraph("No expenses recorded.", styles['Normal']))

    story.append(Spacer(1, 16))

    # ── CATEGORY BREAKDOWN ──
    story.append(Paragraph("  Spending by Category", ParagraphStyle(
        'SectionHead2', parent=styles['Normal'],
        fontSize=12, textColor=WHITE, fontName='Helvetica-Bold',
        backColor=TEAL, borderPad=8, spaceAfter=8
    )))

    if category_totals:
        cat_data = [['Category', 'Amount', 'Percentage']]
        for cat, total in category_totals.items():
            pct = (total / total_amount * 100) if total_amount > 0 else 0
            cat_data.append([cat, f"Rs. {total:,.2f}", f"{pct:.1f}%"])

        cat_table = Table(cat_data, colWidths=[200, 150, 160])
        cat_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), TEAL),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TEXTCOLOR', (0, 1), (-1, -1), DARK),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('ROWHEIGHT', (0, 0), (-1, -1), 22),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 1), (0, -1), 8),
        ]))
        story.append(cat_table)

    story.append(Spacer(1, 16))

    # ── SETTLEMENTS ──
    story.append(Paragraph("  Final Settlements", ParagraphStyle(
        'SectionHead3', parent=styles['Normal'],
        fontSize=12, textColor=WHITE, fontName='Helvetica-Bold',
        backColor=TEAL, borderPad=8, spaceAfter=8
    )))

    if settlements:
        settle_data = [['From', 'To', 'Amount']]
        for s in settlements:
            settle_data.append([
                s['from'],
                s['to'],
                f"Rs. {s['amount']:,.2f}"
            ])

        settle_table = Table(settle_data, colWidths=[170, 170, 170])
        settle_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), TEAL),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0, 1), (-1, 1), RED),
            ('TEXTCOLOR', (1, 1), (1, -1), GREEN),
            ('FONTNAME', (2, 1), (2, -1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (2, 1), (2, -1), DARK),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('ROWHEIGHT', (0, 0), (-1, -1), 26),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(settle_table)
    else:
        story.append(Paragraph(
            "All expenses are equal — no settlements needed!",
            ParagraphStyle('Green', parent=styles['Normal'],
                textColor=GREEN, fontSize=10)
        ))

    # ── FOOTER ──
    story.append(Spacer(1, 24))
    story.append(HRFlowable(width="100%", thickness=1, color=GRAY))
    story.append(Paragraph(
        "Generated by SmartSplit AI — smartsplit-ai.onrender.com",
        ParagraphStyle('Footer', parent=styles['Normal'],
            fontSize=8, textColor=GRAY, alignment=TA_CENTER, spaceBefore=8)
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer