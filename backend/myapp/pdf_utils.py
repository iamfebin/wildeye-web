# wildeye/myapp/pdf_utils.py

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.units import cm, inch
from reportlab.lib import colors
import io
import os
from django.conf import settings
from django.template.defaultfilters import date as _date_format, time as _time_format
from django.utils import timezone

# ==============================================================================
# PDF GENERATION FUNCTION
# ==============================================================================
def generate_trekking_pass_pdf(trekking_pass_instance):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=0.75*inch, leftMargin=0.75*inch,
                            topMargin=0.75*inch, bottomMargin=0.75*inch)
    
    story = []
    styles = getSampleStyleSheet()

    # --- STYLES for a cleaner look ---
    styles.add(ParagraphStyle(name='MainTitle', alignment=TA_LEFT, fontSize=24, fontName='Helvetica-Bold',
                              textColor=colors.HexColor('#2C5F2D'), spaceAfter=15))
    styles.add(ParagraphStyle(name='SubTitle', alignment=TA_LEFT, fontSize=16, fontName='Helvetica',
                              textColor=colors.HexColor('#444444')))
    styles.add(ParagraphStyle(name='SectionHeader', alignment=TA_CENTER, fontSize=12, fontName='Helvetica-Bold',
                              textColor=colors.white, backColor=colors.HexColor('#36454F')))
    styles.add(ParagraphStyle(name='KeyText', alignment=TA_LEFT, fontSize=10, fontName='Helvetica-Bold',
                              textColor=colors.HexColor('#333333')))
    styles.add(ParagraphStyle(name='ValueText', alignment=TA_LEFT, fontSize=10, fontName='Helvetica',
                              textColor=colors.HexColor('#555555')))
    styles.add(ParagraphStyle(name='FooterText', alignment=TA_CENTER, fontSize=8, fontName='Helvetica',
                               textColor=colors.HexColor('#666666'), leading=10))
    styles.add(ParagraphStyle(name='InstructionsText', alignment=TA_LEFT, fontSize=9, fontName='Helvetica',
                               textColor=colors.HexColor('#333333'), leading=12, spaceAfter=10))

    # --- 1. HEADER SECTION (Using a Table for Layout) ---
    logo_path = None
    if settings.STATICFILES_DIRS:
        logo_path = os.path.join(settings.STATICFILES_DIRS[0], 'wild_eye_logo2.png')
    
    logo_img = None
    if logo_path and os.path.exists(logo_path):
        logo_img = Image(logo_path, width=1.0*inch, height=1.0*inch)
    else:
        # Create a placeholder if logo is not found
        logo_img = Paragraph("Logo", styles['Normal'])

    header_data = [[
        logo_img,
        [
            Paragraph("Wildeye Forest Management", styles['MainTitle']),
            Paragraph("Official Digital Trekking Pass", styles['SubTitle'])
        ]
    ]]
    
    header_table = Table(header_data, colWidths=[1.2*inch, None])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10)
    ]))
    
    story.append(header_table)

    # --- 2. CONSOLIDATED DETAILS TABLE (More Compact) ---
    # Prepare data values with timezone conversion
    local_valid_from = timezone.localtime(trekking_pass_instance.valid_from) if trekking_pass_instance.valid_from else None
    local_valid_to = timezone.localtime(trekking_pass_instance.valid_to) if trekking_pass_instance.valid_to else None
    valid_from_str = f"{_date_format(local_valid_from, 'M d, Y')} at {_time_format(local_valid_from, 'P')}" if local_valid_from else "N/A"
    valid_to_str = f"{_date_format(local_valid_to, 'M d, Y')} at {_time_format(local_valid_to, 'P')}" if local_valid_to else "N/A"

    details_data = [
        # Section 1: Trekker Details
        [Paragraph('Trekker Details', styles['SectionHeader']), '', '', ''],
        [Paragraph('Full Name:', styles['KeyText']), Paragraph(trekking_pass_instance.request.full_name, styles['ValueText']),
         Paragraph('Phone:', styles['KeyText']), Paragraph(str(trekking_pass_instance.request.phone), styles['ValueText'])], # <--- FIX 1
        [Paragraph('Email:', styles['KeyText']), Paragraph(trekking_pass_instance.request.email, styles['ValueText']),
         Paragraph('Group Size:', styles['KeyText']), Paragraph(str(trekking_pass_instance.request.trekkers_count), styles['ValueText'])], # <--- FIX 2
        
        # Section 2: Trekking Details
        [Paragraph('Trekking Details', styles['SectionHeader']), '', '', ''],
        [Paragraph('Pass ID:', styles['KeyText']), Paragraph(f"WP-{trekking_pass_instance.id:06}", styles['ValueText']),
         Paragraph('Destination:', styles['KeyText']), Paragraph(trekking_pass_instance.request.destination, styles['ValueText'])],
        [Paragraph('Valid From:', styles['KeyText']), Paragraph(valid_from_str, styles['ValueText']),
         Paragraph('Valid To:', styles['KeyText']), Paragraph(valid_to_str, styles['ValueText'])],
    ]

    details_table = Table(details_data, colWidths=[1.5*inch, 2.0*inch, 1.5*inch, 2.0*inch])
    details_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,1), (-1,-1), 0.5, colors.lightgrey), # Grid on data rows only
        ('SPAN', (0,0), (3,0)), # Span for 'Trekker Details' header
        ('SPAN', (0,3), (3,3)), # Span for 'Trekking Details' header
        ('BACKGROUND', (0,0), (3,0), colors.HexColor('#36454F')),
        ('BACKGROUND', (0,3), (3,3), colors.HexColor('#36454F')),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))

    story.append(details_table)
    story.append(Spacer(1, 0.25*inch)) # A small spacer for breathing room

    # --- 3. FOOTER SECTION (Using a Table for Layout to prevent page breaks) ---
    # Prepare footer content
    issued_by_name = "System"
    if trekking_pass_instance.issued_by:
        # issued_by_name = f"{trekking_pass_instance.issued_by.first_name} {trekking_pass_instance.issued_by.last_name}"
        issued_by_name = f"{trekking_pass_instance.issued_by.first_name} {trekking_pass_instance.issued_by.last_name} (Officer ID: {trekking_pass_instance.issued_by.id})"

    
    local_issued_at = timezone.localtime(trekking_pass_instance.issued_at) if trekking_pass_instance.issued_at else None
    issued_at_formatted = _date_format(local_issued_at, 'M d, Y, P') if local_issued_at else "N/A"

    issued_by_content = [
        Paragraph("<b>Issued By:</b>", styles['KeyText']),
        Paragraph(issued_by_name, styles['ValueText']),
        Spacer(1, 6),
        Paragraph("<b>Issued On:</b>", styles['KeyText']),
        Paragraph(issued_at_formatted, styles['ValueText']),
    ]

    instructions_content = [
        Paragraph("<b>Important Instructions:</b>", styles['KeyText']),
        Paragraph(trekking_pass_instance.instructions, styles['InstructionsText']),
    ]

    # Load the seal image
    seal_image_path = None
    if settings.STATICFILES_DIRS:
        seal_image_path = os.path.join(settings.STATICFILES_DIRS[0], 'Kerala_Forest_Department_logo_no_background.png')

    seal_img = None
    if seal_image_path and os.path.exists(seal_image_path):
        seal_img = Image(seal_image_path, width=1.2*inch, height=1.2*inch)
    else:
        seal_img = Paragraph("SEAL", styles['KeyText']) # Placeholder

    # Assemble the footer table
    footer_data = [[
        issued_by_content,
        seal_img,
        instructions_content
    ]]

    footer_table = Table(footer_data, colWidths=[2.5*inch, 1.5*inch, 3.0*inch])
    footer_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (1,0), (1,0), 'CENTER'),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    
    story.append(footer_table)
    story.append(Spacer(1, 0.2*inch))

    # --- 4. FINAL DISCLAIMER ---
    forest_station_phone = "N/A"
    forest_station_name = "N/A"
    if (trekking_pass_instance.request and
        trekking_pass_instance.request.station and
        trekking_pass_instance.request.station.phone):
        
        forest_station_phone = str(trekking_pass_instance.request.station.phone)
        forest_station_name = trekking_pass_instance.request.station.name




    # forest_station_phone = trekking_pass_instance.request.station.phone if trekking_pass_instance.request.station else "N/A"
    disclaimer_text = (
        f"This is a digitally generated pass. Please adhere to all forest regulations. "
        f"For inquiries, contact {forest_station_name} at {forest_station_phone}"
    )
    story.append(Paragraph(disclaimer_text, styles['FooterText']))
    
    # Build the document
    doc.build(story)
    buffer.seek(0)
    return buffer
