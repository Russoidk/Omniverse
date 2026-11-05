from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from concept_map.models import ConceptNode
from projects.utils import get_active_project, ensure_concept_node
from timeline.models import Event, EventCharacter
from timeline.services import sync_birth_event
from .forms import CharacterForm, CharacterRelationshipForm
from .models import Character, CharacterRelationship


def _active_project_or_redirect(request):
    project = get_active_project(request)
    if project is None:
        messages.info(request, 'Selecciona un proyecto para continuar.')
        return None
    return project


@login_required
def index(request):
    project = _active_project_or_redirect(request)
    if project is None:
        return redirect('home')
    characters = Character.objects.filter(project=project).select_related('main_residence').order_by('full_name')
    return render(request, 'characters/index.html', {
        'project': project,
        'characters': characters,
    })


@login_required
def create(request):
    project = _active_project_or_redirect(request)
    if project is None:
        return redirect('home')
    form = CharacterForm(request.POST or None, request.FILES or None, project=project)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            character = form.save(commit=False)
            character.project = project
            character.save()
            sync_birth_event(character)
            ensure_concept_node(project, character, 'CHARACTER')
        messages.success(request, f'{character.full_name} fue creado correctamente.')
        return redirect('character_detail', pk=character.pk)
    return render(request, 'characters/form.html', {'form': form, 'project': project, 'mode': 'create'})


@login_required
def detail(request, pk):
    project = _active_project_or_redirect(request)
    if project is None:
        return redirect('home')
    character = get_object_or_404(
        Character.objects.select_related('main_residence'), pk=pk, project=project
    )
    outgoing = CharacterRelationship.objects.filter(
        project=project, character_1=character
    ).select_related('character_2').order_by('relationship_type')
    incoming = CharacterRelationship.objects.filter(
        project=project, character_2=character
    ).select_related('character_1').order_by('relationship_type')
    events = EventCharacter.objects.filter(
        character=character, event__project=project
    ).select_related('event').order_by('event__date_value')
    return render(request, 'characters/detail.html', {
        'character': character,
        'project': project,
        'outgoing_relationships': outgoing,
        'incoming_relationships': incoming,
        'character_events': events,
        'relationship_form': CharacterRelationshipForm(project=project, current_character=character),
        'can_export': request.user.is_subscribed,
    })


@login_required
def edit(request, pk):
    project = _active_project_or_redirect(request)
    if project is None:
        return redirect('home')
    character = get_object_or_404(Character, pk=pk, project=project)
    form = CharacterForm(request.POST or None, request.FILES or None, instance=character, project=project)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            character = form.save(commit=False)
            character.project = project
            character.save()
            sync_birth_event(character)
            ensure_concept_node(project, character, 'CHARACTER')
        messages.success(request, 'Los cambios del personaje fueron guardados.')
        return redirect('character_detail', pk=character.pk)
    return render(request, 'characters/form.html', {
        'form': form, 'project': project, 'mode': 'edit', 'character': character
    })


@login_required
def delete(request, pk):
    project = _active_project_or_redirect(request)
    if project is None:
        return redirect('home')
    character = get_object_or_404(Character, pk=pk, project=project)
    if request.method == 'POST':
        content_type = ContentType.objects.get_for_model(character, for_concrete_model=False)
        ConceptNode.objects.filter(project=project, content_type=content_type, object_id=character.pk).delete()
        auto_events = list(EventCharacter.objects.filter(
            character=character, role='Nacido/a', event__automatic=True
        ).select_related('event').values_list('event_id', flat=True))
        character.delete()
        for event_id in auto_events:
            event = Event.objects.filter(pk=event_id, automatic=True).first()
            if event and not event.character_links.exists():
                event_content_type = ContentType.objects.get_for_model(event, for_concrete_model=False)
                ConceptNode.objects.filter(
                    project=project,
                    content_type=event_content_type,
                    object_id=event.pk,
                ).delete()
                event.delete()
        messages.success(request, 'El personaje fue eliminado.')
        return redirect('characters')
    return render(request, 'characters/confirm_delete.html', {'character': character, 'project': project})


@login_required
def add_relationship(request, pk):
    project = _active_project_or_redirect(request)
    if project is None:
        return redirect('home')
    character = get_object_or_404(Character, pk=pk, project=project)
    form = CharacterRelationshipForm(request.POST or None, project=project, current_character=character)
    if request.method == 'POST' and form.is_valid():
        name = form.cleaned_data['character_name']
        relationship_type = form.cleaned_data['relationship_type'].strip()
        description = form.cleaned_data['description'].strip()
        target = Character.objects.filter(project=project, full_name__iexact=name).exclude(pk=character.pk).first()
        if target:
            CharacterRelationship.objects.create(
                project=project, character_1=character, character_2=target,
                character_2_name='', relationship_type=relationship_type, description=description,
            )
            messages.success(request, f'La relación con «{target.full_name}» fue añadida.')
            return redirect('character_detail', pk=character.pk)

        decision = request.POST.get('decision')
        if decision not in {'create', 'reference'}:
            return render(request, 'characters/relationship_confirm.html', {
                'project': project, 'character': character, 'form': form,
                'related_name': name, 'relationship_type': relationship_type,
                'description': description,
            })

        if decision == 'create':
            target = Character.objects.create(project=project, full_name=name)
            ensure_concept_node(project, target, 'CHARACTER')
            CharacterRelationship.objects.create(
                project=project, character_1=character, character_2=target,
                character_2_name='', relationship_type=relationship_type, description=description,
            )
            messages.success(request, f'Se creó una ficha vacía para «{target.full_name}» y se guardó la relación. Puedes completar su ficha más adelante.')
        else:
            CharacterRelationship.objects.create(
                project=project, character_1=character, character_2=None,
                character_2_name=name, relationship_type=relationship_type, description=description,
            )
            messages.success(request, f'La relación con «{name}» quedó como referencia sin ficha de personaje.')
        return redirect('character_detail', pk=character.pk)
    return redirect('character_detail', pk=character.pk)


@login_required
def delete_relationship(request, pk, relationship_id):
    project = _active_project_or_redirect(request)
    if project is None:
        return redirect('home')
    character = get_object_or_404(Character, pk=pk, project=project)
    relationship = get_object_or_404(
        CharacterRelationship, pk=relationship_id, project=project,
        character_1=character
    )
    if request.method == 'POST':
        relationship.delete()
        messages.success(request, 'La relación fue eliminada.')
    return redirect('character_detail', pk=character.pk)


def _load_font(size):
    from PIL import ImageFont
    candidates = [
        Path(settings.BASE_DIR) / 'static' / 'fonts' / 'Urbanist-VariableFont_wght.ttf',
    ]
    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                pass
    return ImageFont.load_default()


def _character_sections(character):
    return [
        ('Datos esenciales', [
            ('Fecha de nacimiento', character.birth_date),
            ('Edad al inicio', character.age_at_story_start),
            ('Especie o raza', character.species),
            ('Estado actual', character.current_status),
            ('Facción / afiliación', character.faction),
            ('Residencia principal', character.main_residence.name if character.main_residence else ''),
        ]),
        ('Rasgos y preferencias', [
            ('Rasgos dominantes', character.dominant_traits),
            ('Rasgos destructivos', character.destructive_traits),
            ('Sueño secreto', character.secret_dream),
            ('Gustos', character.likes),
            ('Disgustos', character.dislikes),
            ('Sería más feliz si…', character.happier_if),
        ]),
        ('Historia personal', [
            ('Infancia', character.childhood),
            ('Adolescencia', character.adolescence),
            ('Adultez', character.adulthood),
        ]),
    ]


def _character_relationship_export_lines(project, character):
    rows = []
    for rel in CharacterRelationship.objects.filter(project=project, character_1=character).select_related('character_2').order_by('relationship_type'):
        target_name = rel.character_2.full_name if rel.character_2_id else rel.character_2_name
        line = f'{rel.relationship_type}: {target_name}'
        if rel.description:
            line += f'\n{rel.description}'
        rows.append(line)
    for rel in CharacterRelationship.objects.filter(project=project, character_2=character).select_related('character_1').order_by('relationship_type'):
        line = f'{rel.character_1.full_name} → {rel.relationship_type} → {character.full_name}'
        if rel.description:
            line += f'\n{rel.description}'
        rows.append(line)
    return rows


def _cropped_portrait(character, size=(320, 400)):
    from PIL import Image, ImageOps
    if not character.image:
        return None
    try:
        source = Image.open(character.image.path)
        source = ImageOps.exif_transpose(source).convert('RGB')
        # Mimics object-fit: cover in the on-screen sheet, while leaving the uploaded original untouched.
        return ImageOps.fit(source, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.38))
    except (OSError, ValueError, AttributeError):
        return None


def _text_lines(draw, text, font, max_width):
    """Wrap text by rendered pixel width and preserve line/paragraph breaks."""
    value = '' if text is None else str(text)
    result = []
    for source_line in value.split('\n'):
        if not source_line.strip():
            result.append('')
            continue
        words = source_line.split()
        line = ''
        for word in words:
            candidate = word if not line else f'{line} {word}'
            if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
                line = candidate
            else:
                if line:
                    result.append(line)
                # Handle a word wider than the line without cutting it silently.
                piece = ''
                for char in word:
                    if draw.textbbox((0, 0), piece + char, font=font)[2] > max_width and piece:
                        result.append(piece)
                        piece = char
                    else:
                        piece += char
                line = piece
        if line:
            result.append(line)
    return result or ['']


def _draw_multiline(draw, x, y, value, font, fill, max_width, line_height, paragraph_gap=9):
    lines = _text_lines(draw, value, font, max_width)
    for line in lines:
        if line:
            draw.text((x, y), line, font=font, fill=fill)
        y += line_height if line else line_height + paragraph_gap
    return y


@login_required
def export_character(request, pk, file_format):
    project = _active_project_or_redirect(request)
    if project is None:
        return redirect('home')
    character = get_object_or_404(Character.objects.select_related('main_residence'), pk=pk, project=project)
    if not request.user.is_subscribed:
        messages.error(request, 'La exportación está disponible para las cuentas suscritas.')
        return redirect('character_detail', pk=character.pk)
    if file_format not in {'pdf', 'png'}:
        messages.error(request, 'Formato de exportación no válido.')
        return redirect('character_detail', pk=character.pk)

    sections = _character_sections(character)
    relationships = _character_relationship_export_lines(project, character)
    filename = f'personaje_{character.pk}_{file_format}'
    logo_path = Path(settings.BASE_DIR) / 'static' / 'images' / 'omniverse-logo.png'

    if file_format == 'pdf':
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT, TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as ReportImage, Table, TableStyle, KeepTogether
        from xml.sax.saxutils import escape

        stream = BytesIO()
        page_bg = colors.HexColor('#0d0d10')
        border = colors.HexColor('#34313b')
        panel = colors.HexColor('#15151b')
        subpanel = colors.HexColor('#111116')
        accent = colors.HexColor('#ff4263')
        muted = colors.HexColor('#a2a2ae')
        doc = SimpleDocTemplate(stream, pagesize=A4, rightMargin=1.45*cm, leftMargin=1.45*cm,
                                topMargin=1.25*cm, bottomMargin=1.3*cm, title=f'{character.full_name} — Omniverse')
        def page_background(canvas, document):
            canvas.saveState()
            canvas.setFillColor(page_bg)
            canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
            canvas.setStrokeColor(border)
            canvas.setLineWidth(0.55)
            canvas.line(1.45*cm, 1.02*cm, A4[0]-1.45*cm, 1.02*cm)
            canvas.setStrokeColor(accent)
            canvas.setLineWidth(1.8)
            canvas.line(1.45*cm, A4[1]-0.78*cm, A4[0]-1.45*cm, A4[1]-0.78*cm)
            canvas.setFont('Helvetica-Bold', 7)
            canvas.setFillColor(muted)
            canvas.drawString(1.45*cm, 0.68*cm, 'OMNIVERSE  ·  FICHA DE PERSONAJE')
            canvas.drawRightString(A4[0]-1.45*cm, 0.68*cm, f'PÁG. {document.page}')
            canvas.restoreState()
        styles = getSampleStyleSheet()
        brand_style = ParagraphStyle('OmniBrand', parent=styles['Normal'], textColor=accent, fontName='Helvetica-Bold', fontSize=10, leading=13, alignment=TA_LEFT)
        title_style = ParagraphStyle('OmniTitle', parent=styles['Title'], textColor=colors.HexColor('#f6f4f6'), fontName='Helvetica-Bold', fontSize=23, leading=27, alignment=TA_LEFT, spaceAfter=3)
        role_style = ParagraphStyle('OmniRole', parent=styles['Normal'], textColor=colors.HexColor('#ff8ca0'), fontName='Helvetica', fontSize=10, leading=14)
        quote_style = ParagraphStyle('OmniQuote', parent=styles['BodyText'], textColor=colors.HexColor('#eeeaf0'), fontName='Helvetica', fontSize=9.2, leading=13.2, spaceAfter=5, wordWrap='CJK')
        label_style = ParagraphStyle('OmniLabel', parent=styles['Normal'], textColor=accent, fontName='Helvetica-Bold', fontSize=8, leading=10, spaceAfter=4)
        body_style = ParagraphStyle('OmniBody', parent=styles['BodyText'], textColor=colors.HexColor('#e2e2e9'), fontName='Helvetica', fontSize=8.5, leading=12, spaceAfter=2, wordWrap='CJK')
        small_style = ParagraphStyle('OmniSmall', parent=styles['Normal'], textColor=muted, fontName='Helvetica', fontSize=7.5, leading=10)

        brand_mark = ReportImage(str(logo_path), width=1.35*cm, height=1.35*cm) if logo_path.exists() else Paragraph('✦', brand_style)
        header = Table([[brand_mark, Paragraph('OMNIVERSE<br/><font color="#9696a2" size="7">FICHA DE PERSONAJE</font>', brand_style)]], colWidths=[1.8*cm, 16.2*cm])
        header.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,-1),panel), ('BOX',(0,0),(-1,-1),0.6,border),
            ('LINEBELOW',(0,0),(-1,-1),1.4,accent), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING',(0,0),(-1,-1),4), ('RIGHTPADDING',(0,0),(-1,-1),4),
            ('TOPPADDING',(0,0),(-1,-1),7), ('BOTTOMPADDING',(0,0),(-1,-1),7),
        ]))
        story = [header, Spacer(1, 5), Paragraph(escape(character.full_name), title_style)]
        if character.role or character.species:
            story.append(Paragraph(escape(character.role or character.species), role_style))
        story.append(Spacer(1, 12))

        quote_cells = []
        for idx, (quote, author, context, descriptor) in enumerate([
            (character.quote_1, character.quote_1_author, character.quote_1_context, '01 · VISIÓN DEL MUNDO'),
            (character.quote_2, character.quote_2_author, character.quote_2_context, '02 · ESENCIA / CONTRADICCIÓN'),
        ]):
            quote_body = Paragraph(escape(quote or '—').replace('\n', '<br/>'), quote_style)
            attributions = ' · '.join(v for v in [author, context] if v)
            contents = [Paragraph(escape(descriptor), label_style), quote_body]
            if attributions:
                contents.append(Paragraph(escape(attributions), small_style))
            quote_cells.append(contents)
        portrait_stream = None
        portrait = _cropped_portrait(character, (320, 400))
        if portrait:
            portrait_stream = BytesIO()
            portrait.save(portrait_stream, format='PNG')
            portrait_stream.seek(0)
            portrait_cell = ReportImage(portrait_stream, width=3.3*cm, height=4.1*cm)
        else:
            portrait_cell = Paragraph('<font color="#ff4263" size="20">✦</font>', ParagraphStyle('OmniNoPortrait', parent=styles['Normal'], alignment=TA_CENTER))
        quote_tables = []
        for contents in quote_cells:
            cell_table = Table([[item] for item in contents], colWidths=[6.65*cm])
            cell_table.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,-1),panel), ('VALIGN',(0,0),(-1,-1),'TOP'),
                ('LEFTPADDING',(0,0),(-1,-1),9), ('RIGHTPADDING',(0,0),(-1,-1),9),
                ('TOPPADDING',(0,0),(-1,-1),7), ('BOTTOMPADDING',(0,0),(-1,-1),6),
                ('BOX',(0,0),(-1,-1),0.7,border),
            ]))
            quote_tables.append(cell_table)
        hero = Table([[quote_tables[0], portrait_cell, quote_tables[1]]], colWidths=[6.95*cm, 4.0*cm, 6.95*cm])
        hero.setStyle(TableStyle([
            ('VALIGN',(0,0),(-1,-1),'TOP'), ('LEFTPADDING',(0,0),(-1,-1),3), ('RIGHTPADDING',(0,0),(-1,-1),3),
            ('TOPPADDING',(0,0),(-1,-1),4), ('BOTTOMPADDING',(0,0),(-1,-1),7),
        ]))
        story.extend([hero, Spacer(1, 7)])

        def section_table(section_title, fields):
            rows = []
            values = [(label, value) for label, value in fields if value not in (None, '')]
            for i in range(0, len(values), 2):
                pair = values[i:i+2]
                row = []
                for label, value in pair:
                    body = escape(str(value)).replace('\r\n', '\n').replace('\n', '<br/>')
                    row.append([Paragraph(escape(label.upper()), label_style), Paragraph(body, body_style)])
                if len(pair) == 1:
                    row.append('')
                rows.append(row)
            title_bar = Table([[Paragraph(escape(section_title.upper()), ParagraphStyle('OmniSec'+section_title, parent=label_style, fontSize=9, leading=12))]], colWidths=[18.0*cm])
            title_bar.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#25131b')),('BOX',(0,0),(-1,-1),0.5,border),('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
            if not rows:
                return [title_bar, Spacer(1, 8)]
            cells = []
            for row in rows:
                fixed = []
                for cell in row:
                    if cell == '':
                        fixed.append('')
                    else:
                        fixed.append(Table([[item] for item in cell], colWidths=[8.55*cm], style=TableStyle([
                            ('BACKGROUND',(0,0),(-1,-1),panel), ('BOX',(0,0),(-1,-1),0.4,border),
                            ('VALIGN',(0,0),(-1,-1),'TOP'), ('LEFTPADDING',(0,0),(-1,-1),8), ('RIGHTPADDING',(0,0),(-1,-1),8),
                            ('TOPPADDING',(0,0),(-1,-1),6), ('BOTTOMPADDING',(0,0),(-1,-1),7),
                        ])))
                if len(fixed) == 1: fixed.append('')
                cells.append(fixed)
            grid = Table(cells, colWidths=[9.0*cm, 9.0*cm], hAlign='LEFT')
            grid.setStyle(TableStyle([
                ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),2),('RIGHTPADDING',(0,0),(-1,-1),2),
                ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
            ]))
            return [title_bar, grid, Spacer(1, 9)]

        # El nombre y el rol ya forman parte del encabezado de la ficha; no duplicarlos en la sección.
        for title, fields in sections:
            story.extend(section_table(title, fields))
        if relationships:
            rows = [[Paragraph(escape(row).replace('\n', '<br/>'), body_style)] for row in relationships]
            rel_table = Table(rows, colWidths=[18.0*cm])
            rel_table.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,-1),panel),('BOX',(0,0),(-1,-1),0.5,border),('INNERGRID',(0,0),(-1,-1),0.3,border),
                ('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('VALIGN',(0,0),(-1,-1),'TOP'),
            ]))
            story.extend([Table([[Paragraph('RELACIONES', label_style)]], colWidths=[18.0*cm], style=TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#25131b')),('LEFTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),5)])), rel_table, Spacer(1, 8)])
        doc.build(story, onFirstPage=page_background, onLaterPages=page_background)
        response = HttpResponse(stream.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
        return response

    from PIL import Image, ImageDraw, ImageFont
    width = 1400
    margin = 52
    font_title = _load_font(42)
    font_section = _load_font(25)
    font_body = _load_font(19)
    font_label = _load_font(15)
    font_small = _load_font(13)
    line_height = 29
    all_fields = []
    for _title, fields in sections:
        all_fields += fields
    all_fields += [('Relación', item) for item in relationships]
    estimate = 780 + sum(max(1, len(str(value)) // 57 + 2) * 35 for _label, value in all_fields if value not in (None, ''))
    image = Image.new('RGB', (width, max(1500, estimate + 400)), '#0d0d10')
    draw = ImageDraw.Draw(image)
    # Soft accent wash to echo the application's dark panels.
    draw.ellipse((-420, -420, 660, 700), fill='#171017')
    draw.rounded_rectangle((22, 22, width-22, image.height-22), radius=25, outline='#34313b', width=2)
    y = 45
    if logo_path.exists():
        try:
            logo = Image.open(logo_path).convert('RGBA')
            logo.thumbnail((68, 68), Image.Resampling.LANCZOS)
            image.paste(logo, (margin, y), logo)
        except OSError:
            pass
    draw.text((margin + 82, y + 8), 'OMNIVERSE', font=font_section, fill='#ff4263')
    draw.text((margin + 82, y + 42), 'FICHA DE PERSONAJE', font=font_small, fill='#92929e')
    y += 88
    draw.line((margin, y, width-margin, y), fill='#39323c', width=2)
    y += 22
    draw.text((margin, y), character.full_name, font=font_title, fill='#f4f2f5')
    y += 55
    if character.role or character.species:
        draw.text((margin, y), character.role or character.species, font=font_body, fill='#ff8ca0')
        y += 40

    # Header / quote composition. The portrait is cropped with the same cover treatment as the UI.
    hero_top = y
    quote_w = 472
    portrait_w, portrait_h = 220, 275
    gap = 22
    left_x = margin
    portrait_x = (width - portrait_w) // 2
    right_x = width - margin - quote_w
    quote_texts = [
        ('01 · VISIÓN DEL MUNDO', character.quote_1, ' · '.join(v for v in [character.quote_1_author, character.quote_1_context] if v)),
        ('02 · ESENCIA / CONTRADICCIÓN', character.quote_2, ' · '.join(v for v in [character.quote_2_author, character.quote_2_context] if v)),
    ]
    quote_lines = []
    for title, text_value, attribution in quote_texts:
        lines = _text_lines(draw, f'“{text_value or "—"}”', font_body, quote_w-36)
        attr_lines = _text_lines(draw, attribution, font_small, quote_w-36) if attribution else []
        quote_lines.append((title, lines, attr_lines))
    hero_h = max(portrait_h + 25, max((len(lines)*line_height + len(attrs)*20 + 90) for _, lines, attrs in quote_lines) + 20)
    for quote_x, (title, lines, attrs) in zip((left_x, right_x), quote_lines):
        draw.rounded_rectangle((quote_x, hero_top, quote_x+quote_w, hero_top+hero_h), radius=16, fill='#15151b', outline='#35313b', width=2)
        draw.text((quote_x+18, hero_top+18), title, font=font_small, fill='#ff5b77')
        qy = hero_top+53
        for line in lines:
            if line:
                draw.text((quote_x+18, qy), line, font=font_body, fill='#f1edf1')
            qy += line_height if line else line_height+9
        if attrs:
            qy += 9
            for line in attrs:
                draw.text((quote_x+18, qy), line, font=font_small, fill='#92929e')
                qy += 20
    portrait = _cropped_portrait(character, (portrait_w, portrait_h))
    if portrait:
        image.paste(portrait, (portrait_x, hero_top+5))
    else:
        draw.rounded_rectangle((portrait_x, hero_top+5, portrait_x+portrait_w, hero_top+portrait_h+5), radius=13, fill='#1b151d', outline='#39313b', width=2)
        draw.text((portrait_x+84, hero_top+120), '✦', font=font_title, fill='#ff4263')
    draw.rounded_rectangle((portrait_x, hero_top+5, portrait_x+portrait_w, hero_top+portrait_h+5), radius=13, outline='#39313b', width=2)
    y = hero_top + hero_h + 28

    def draw_section(title, fields, single_column=False):
        nonlocal y
        values = [(label, value) for label, value in fields if value not in (None, '')]
        if not values:
            return
        inner_pad = 20
        col_gap = 26
        col_w = (width - 2*margin - 2*inner_pad - col_gap) // 2
        prepared = []
        if single_column:
            col_w = width - 2*margin - 2*inner_pad
            for label, value in values:
                lines = _text_lines(draw, value, font_body, col_w-8)
                row_h = max(54, len(lines)*line_height + 39) + 12
                prepared.append(([(label, lines)], row_h))
        else:
            for i in range(0, len(values), 2):
                pair = []
                for label, value in values[i:i+2]:
                    lines = _text_lines(draw, value, font_body, col_w-8)
                    pair.append((label, lines))
                if len(pair) == 1:
                    pair.append(('', []))
                row_h = max([len(lines)*line_height + 38 if lines else 36 for _, lines in pair]) + 12
                prepared.append((pair, row_h))
        total_h = 58 + sum(row_h for _pair, row_h in prepared) + 14
        draw.rounded_rectangle((margin, y, width-margin, y+total_h), radius=14, fill='#131318', outline='#34313b', width=2)
        draw.rounded_rectangle((margin, y, width-margin, y+49), radius=14, fill='#21131a', outline='#34313b', width=1)
        draw.rectangle((margin, y+26, width-margin, y+49), fill='#21131a')
        draw.text((margin+inner_pad, y+14), title.upper(), font=font_section, fill='#ff4263')
        cy = y+60
        for pair, row_h in prepared:
            for col_idx, (label, lines) in enumerate(pair):
                x = margin+inner_pad+(0 if single_column else col_idx*(col_w+col_gap))
                if label:
                    draw.text((x, cy), label.upper(), font=font_label, fill='#a3a3af')
                    ty = cy+25
                    for line in lines:
                        if line:
                            draw.text((x, ty), line, font=font_body, fill='#e4e3e9')
                        ty += line_height if line else line_height+9
            cy += row_h
        y += total_h + 18

    draw_section('Datos esenciales', sections[0][1])
    draw_section('Rasgos y preferencias', sections[1][1])
    draw_section('Historia personal', sections[2][1], single_column=True)
    if relationships:
        draw_section('Relaciones', [(f'Relación {idx+1}', value) for idx, value in enumerate(relationships)])
    image = image.crop((0, 0, width, min(image.height, y+30)))
    stream = BytesIO()
    image.save(stream, format='PNG', optimize=True)
    response = HttpResponse(stream.getvalue(), content_type='image/png')
    response['Content-Disposition'] = f'attachment; filename="{filename}.png"'
    return response
