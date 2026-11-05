from io import BytesIO
from pathlib import Path
import re
import unicodedata

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from characters.models import Character
from concept_map.models import ConceptNode
from projects.models import Place
from projects.utils import get_active_project, ensure_concept_node
from .forms import EventForm, EventRelationshipForm, TimelineSpanForm
from .models import Event, EventCharacter, EventPlace, EventRelationship, TimelineSpan
from .services import guess_date_type, guess_date_era


def _active_project_or_redirect(request):
    project = get_active_project(request)
    if project is None:
        messages.info(request, 'Selecciona un proyecto para continuar.')
    return project


def _sync_event_links(event, characters, places):
    """Synchronize an event's character/place links and ensure it appears in the graph."""
    characters = list(characters)
    places = list(places)
    desired_character_ids = {character.pk for character in characters}
    desired_place_ids = {place.pk for place in places}

    EventCharacter.objects.filter(event=event).exclude(character_id__in=desired_character_ids).delete()
    EventPlace.objects.filter(event=event).exclude(place_id__in=desired_place_ids).delete()

    for character in characters:
        if character.project_id == event.project_id:
            EventCharacter.objects.get_or_create(event=event, character=character)
    for place in places:
        if place.project_id == event.project_id:
            EventPlace.objects.get_or_create(event=event, place=place)

    ensure_concept_node(event.project, event, 'EVENT')


def _sync_span_boundary_events(span):
    """Keep two real, read-only timeline events in sync with every time span."""
    for marker, date_value, date_era, title_prefix, order in (
        ('START', span.start_value, span.start_era, 'Inicio del lapso', -100000),
        ('END', span.end_value, span.end_era, 'Final del lapso', 100000),
    ):
        Event.objects.update_or_create(
            project=span.project,
            timeline_span=span,
            span_marker=marker,
            defaults={
                'title': f'{title_prefix}: {span.title}'[:200],
                'description': '',
                'date_value': date_value,
                'date_era': date_era,
                'date_type': guess_date_type(date_value),
                'event_type': title_prefix,
                'sort_order': order,
                'automatic': True,
            },
        )


def _temporal_key(value, era=Event.ERA_AD):
    """Return a comparable (year, month, day) tuple supporting A.C. and D.C."""
    raw = str(value or '').strip()
    if not raw:
        return None
    normalized = unicodedata.normalize('NFKD', raw).encode('ascii', 'ignore').decode('ascii').lower()
    # Explicit suffixes inside the typed value take precedence over the dropdown.
    if re.search(r'(?<![a-z])a\s*\.?\s*c\.?(?![a-z])|\bbce\b|antes de cristo', normalized):
        era = Event.ERA_BC
    elif re.search(r'(?<![a-z])d\s*\.?\s*c\.?(?![a-z])|\bce\b|despues de cristo', normalized):
        era = Event.ERA_AD

    match = re.search(r'(?<!\d)(\d{4})[./-](\d{1,2})[./-](\d{1,2})(?!\d)', normalized)
    if match:
        year, month, day = map(int, match.groups())
    else:
        match = re.search(r'(?<!\d)(\d{1,2})[./-](\d{1,2})[./-](\d{1,6})(?!\d)', normalized)
        if match:
            day, month, year = map(int, match.groups())
        else:
            numbers = [int(number) for number in re.findall(r'(?<![a-z])\d+(?![a-z])', normalized)]
            if not numbers:
                return None
            month_names = {
                'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
                'julio': 7, 'agosto': 8, 'septiembre': 9, 'setiembre': 9,
                'octubre': 10, 'noviembre': 11, 'diciembre': 12,
            }
            month = next((num for name, num in month_names.items() if name in normalized), 0)
            if len(numbers) > 1 and numbers[-1] >= 100 and numbers[0] <= 31:
                year, day = numbers[-1], numbers[0]
            else:
                year, day = numbers[0], 0
    year = -abs(year) if era == Event.ERA_BC else abs(year)
    return (year, month, day)


def _natural_sort_key(value):
    """Natural-sort arbitrary free-text temporal references without comparing int to str."""
    raw = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode('ascii').casefold()
    return tuple((0, int(part)) if part.isdigit() else (1, part) for part in re.split(r'(\d+)', raw) if part)


def _value_sort_key(value, era=Event.ERA_AD):
    temporal = _temporal_key(value, era)
    if temporal is not None:
        return (0, temporal[0], temporal[1], temporal[2], _natural_sort_key(value))
    return (1, 0, 0, 0, _natural_sort_key(value))


def _event_falls_in_span(event, span):
    if event.timeline_span_id == span.pk:
        return True
    event_key = _temporal_key(event.date_value, event.date_era)
    start_key = _temporal_key(span.start_value, span.start_era)
    end_key = _temporal_key(span.end_value, span.end_era)
    if event_key is None or start_key is None or end_key is None:
        return False
    # A year-only event represents an event in that year, not an artificial
    # point before the year's first day.
    if event_key[1:] == (0, 0):
        event_key = (event_key[0], 6, 15)
    # Treat a year-only boundary as the full calendar year, not as January 0.
    # This includes events such as 12/06/100 in a span beginning at "100".
    start_bound = (start_key[0], 1, 1) if start_key[1:] == (0, 0) else start_key
    end_bound = (end_key[0], 12, 31) if end_key[1:] == (0, 0) else end_key
    lower, upper = sorted((start_bound, end_bound))
    return lower <= event_key <= upper


def _build_timeline_items(project):
    """Build a single timeline where each span contains its inner events."""
    spans = list(TimelineSpan.objects.filter(project=project))
    for span in spans:
        _sync_span_boundary_events(span)
    events = list(Event.objects.filter(project=project, span_marker='').select_related(
        'timeline_span'
    ).prefetch_related('character_links__character', 'place_links__place'))

    from collections import Counter
    counts = Counter((event.date_value, event.date_era) for event in events if event.date_value)
    positions = Counter()
    for event in sorted(events, key=lambda item: (item.sort_order, item.created_at, item.pk)):
        date_key = (event.date_value, event.date_era)
        event.same_date_count = counts.get(date_key, 0) if event.date_value else 0
        event.same_date_position = positions[date_key] if event.date_value else 0
        if event.date_value:
            positions[date_key] += 1

    assigned = {}
    for event in events:
        if event.timeline_span_id:
            if any(span.pk == event.timeline_span_id for span in spans):
                assigned[event.pk] = event.timeline_span_id
                continue
        candidates = [span for span in spans if _event_falls_in_span(event, span)]
        if candidates:
            # If periods overlap, nest the event inside the narrowest numeric interval.
            def width(span):
                a, b = _temporal_key(span.start_value, span.start_era), _temporal_key(span.end_value, span.end_era)
                if a is None or b is None:
                    return float('inf')
                return abs((b[0] - a[0]) * 372 + (b[1] - a[1]) * 31 + b[2] - a[2])
            selected = min(candidates, key=lambda span: (width(span), -(_temporal_key(span.start_value, span.start_era) or (0,))[0], span.pk))
            assigned[event.pk] = selected.pk

    grouped_events = {span.pk: [] for span in spans}
    top_level = []
    for event in events:
        span_id = assigned.get(event.pk)
        if span_id:
            grouped_events[span_id].append(event)
        else:
            top_level.append({'kind': 'event', 'event': event, 'sort_key': _value_sort_key(event.date_value, event.date_era)})

    for span in spans:
        span.start_event = span.events.filter(span_marker='START').first()
        span.end_event = span.events.filter(span_marker='END').first()
        span.inner_events = sorted(
            grouped_events[span.pk],
            key=lambda event: (_value_sort_key(event.date_value, event.date_era), event.sort_order, event.created_at, event.pk),
        )
        top_level.append({'kind': 'span', 'span': span, 'sort_key': _value_sort_key(span.start_value, span.start_era)})

    top_level.sort(key=lambda item: (item['sort_key'], 0 if item['kind'] == 'span' else 1,
                                     item.get('span', item.get('event')).pk))
    return top_level, events, spans


def index(request):
    project = _active_project_or_redirect(request)
    if project is None:
        return redirect('home')
    timeline_items, events, spans = _build_timeline_items(project)
    return render(request, 'timeline/index.html', {
        'project': project,
        'events': events,
        'timeline_items': timeline_items,
        'spans': spans,
        'can_export': request.user.is_subscribed,
    })

@login_required
def create(request):
    project = _active_project_or_redirect(request)
    if project is None:
        return redirect('home')
    form = EventForm(request.POST or None, project=project)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            event = form.save(commit=False)
            event.project = project
            event.automatic = False
            event.save()
            _sync_event_links(event, form.cleaned_data['characters'], form.cleaned_data['places'])
        messages.success(request, 'El acontecimiento fue creado.')
        return redirect('event_detail', pk=event.pk)
    return render(request, 'timeline/form.html', {'form': form, 'project': project, 'mode': 'create'})


@login_required
def detail(request, pk):
    project = _active_project_or_redirect(request)
    if project is None:
        return redirect('home')
    event = get_object_or_404(Event, pk=pk, project=project)
    character_links = EventCharacter.objects.filter(event=event).select_related('character')
    place_links = EventPlace.objects.filter(event=event).select_related('place')
    relationships = EventRelationship.objects.filter(project=project).filter(
        Q(event_1=event) | Q(event_2=event)
    ).select_related('event_1', 'event_2')
    relationship_form = EventRelationshipForm(project=project, current_event=event)
    return render(request, 'timeline/detail.html', {
        'event': event,
        'project': project,
        'character_links': character_links,
        'place_links': place_links,
        'relationships': relationships,
        'relationship_form': relationship_form,
        'can_edit': not event.automatic,
        'can_export': request.user.is_subscribed,
    })


@login_required
def edit(request, pk):
    project = _active_project_or_redirect(request)
    if project is None:
        return redirect('home')
    event = get_object_or_404(Event, pk=pk, project=project)
    if event.automatic:
        messages.info(request, 'Este acontecimiento se actualiza automáticamente desde el elemento que lo origina.')
        return redirect('event_detail', pk=event.pk)
    initial = {
        'characters': list(event.character_links.values_list('character_id', flat=True)),
        'places': list(event.place_links.values_list('place_id', flat=True)),
    }
    form = EventForm(request.POST or None, project=project, instance=event, initial=initial)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            event = form.save(commit=False)
            event.project = project
            event.save()
            _sync_event_links(event, form.cleaned_data['characters'], form.cleaned_data['places'])
        messages.success(request, 'El acontecimiento fue actualizado.')
        return redirect('event_detail', pk=event.pk)
    return render(request, 'timeline/form.html', {'form': form, 'project': project, 'mode': 'edit', 'event': event})


@login_required
def delete(request, pk):
    project = _active_project_or_redirect(request)
    if project is None:
        return redirect('home')
    event = get_object_or_404(Event, pk=pk, project=project)
    if event.automatic:
        messages.error(request, 'Los acontecimientos automáticos se gestionan desde el elemento que los origina.')
        return redirect('event_detail', pk=event.pk)
    if request.method == 'POST':
        ct = ContentType.objects.get_for_model(event, for_concrete_model=False)
        ConceptNode.objects.filter(project=project, content_type=ct, object_id=event.pk).delete()
        event.delete()
        messages.success(request, 'El acontecimiento fue eliminado.')
        return redirect('timeline')
    return render(request, 'timeline/confirm_delete.html', {'event': event, 'project': project})


@login_required
def add_relationship(request, pk):
    project = _active_project_or_redirect(request)
    if project is None:
        return redirect('home')
    event = get_object_or_404(Event, pk=pk, project=project)
    form = EventRelationshipForm(request.POST or None, project=project, current_event=event)
    if request.method == 'POST' and form.is_valid():
        relationship = form.save(commit=False)
        relationship.project = project
        relationship.event_1 = event
        if relationship.event_2.project_id != project.id:
            messages.error(request, 'El acontecimiento seleccionado no pertenece al proyecto activo.')
        else:
            relationship.save()
            messages.success(request, 'La relación entre acontecimientos fue guardada.')
    return redirect('event_detail', pk=event.pk)


@login_required
def delete_relationship(request, pk, relationship_id):
    project = _active_project_or_redirect(request)
    if project is None:
        return redirect('home')
    event = get_object_or_404(Event, pk=pk, project=project)
    relation = get_object_or_404(EventRelationship, pk=relationship_id, project=project)
    if event.pk not in (relation.event_1_id, relation.event_2_id):
        return redirect('event_detail', pk=event.pk)
    if request.method == 'POST':
        relation.delete()
        messages.success(request, 'La relación fue eliminada.')
    return redirect('event_detail', pk=event.pk)


def _timeline_events(project):
    return list(Event.objects.filter(project=project, span_marker='').order_by('date_value', 'sort_order', 'created_at', 'title'))


@login_required
def export_timeline(request, file_format):
    project = _active_project_or_redirect(request)
    if project is None:
        return redirect('home')
    if not request.user.is_subscribed:
        messages.error(request, 'La exportación de la cronología está disponible para las cuentas suscritas.')
        return redirect('timeline')
    if file_format not in {'pdf', 'png'}:
        messages.error(request, 'Formato de exportación no válido.')
        return redirect('timeline')
    timeline_items, events, spans = _build_timeline_items(project)
    event_summary = f"{len(events)} {'acontecimiento' if len(events) == 1 else 'acontecimientos'}"
    span_summary = f"{len(spans)} {'lapso de tiempo' if len(spans) == 1 else 'lapsos de tiempo'}"
    summary_text = f'{event_summary} · {span_summary}'
    logo_path = Path(settings.BASE_DIR) / 'static' / 'images' / 'omniverse-logo.png'

    if file_format == 'pdf':
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as ReportImage, Table, TableStyle, KeepTogether
        from xml.sax.saxutils import escape

        stream = BytesIO()
        page_bg = colors.HexColor('#0d0d10')
        panel = colors.HexColor('#15151b')
        panel_alt = colors.HexColor('#111116')
        border = colors.HexColor('#34313b')
        accent = colors.HexColor('#ff4263')
        muted = colors.HexColor('#a2a2ae')
        doc = SimpleDocTemplate(stream, pagesize=A4, rightMargin=1.3*cm, leftMargin=1.3*cm,
                                topMargin=1.15*cm, bottomMargin=1.2*cm, title=f'{project.name} — Cronología Omniverse')
        def page_background(canvas, document):
            canvas.saveState()
            canvas.setFillColor(page_bg)
            canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
            canvas.setStrokeColor(border)
            canvas.setLineWidth(0.55)
            canvas.line(1.3*cm, 0.98*cm, A4[0]-1.3*cm, 0.98*cm)
            canvas.setStrokeColor(accent)
            canvas.setLineWidth(1.8)
            canvas.line(1.3*cm, A4[1]-0.75*cm, A4[0]-1.3*cm, A4[1]-0.75*cm)
            canvas.setFont('Helvetica-Bold', 7)
            canvas.setFillColor(muted)
            canvas.drawString(1.3*cm, 0.63*cm, 'OMNIVERSE  ·  CRONOLOGÍA')
            canvas.drawRightString(A4[0]-1.3*cm, 0.63*cm, f'PÁG. {document.page}')
            canvas.restoreState()
        styles = getSampleStyleSheet()
        brand_style = ParagraphStyle('TimelineBrand', parent=styles['Normal'], textColor=accent, fontName='Helvetica-Bold', fontSize=10, leading=13)
        title_style = ParagraphStyle('TimelineTitle', parent=styles['Heading1'], textColor=colors.HexColor('#f4f3f6'), fontName='Helvetica-Bold', fontSize=15, leading=18, alignment=0, spaceAfter=3)
        sub_style = ParagraphStyle('TimelineSub', parent=styles['Normal'], textColor=muted, fontSize=9, leading=12)
        body_style = ParagraphStyle('TimelineBody', parent=styles['BodyText'], textColor=colors.HexColor('#e2e2e9'), fontSize=8.3, leading=11.3, wordWrap='CJK')
        date_style = ParagraphStyle('TimelineDate', parent=body_style, textColor=accent, fontName='Helvetica-Bold', fontSize=8, leading=10)
        chip_style = ParagraphStyle('TimelineChip', parent=body_style, textColor=colors.HexColor('#ff8da0'), fontSize=7.4, leading=9)
        section_style = ParagraphStyle('TimelineSection', parent=styles['Heading2'], textColor=accent, fontName='Helvetica-Bold', fontSize=10, leading=13, spaceBefore=6, spaceAfter=5)
        logo = ReportImage(str(logo_path), width=1.25*cm, height=1.25*cm) if logo_path.exists() else Paragraph('✦', brand_style)
        head = Table([[logo, [Paragraph('OMNIVERSE · CRONOLOGÍA', brand_style), Paragraph(escape(project.name), title_style), Paragraph(escape(summary_text), sub_style)]]], colWidths=[1.5*cm, 16.6*cm])
        head.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),10)]))
        story = [head, Spacer(1, 7)]

        def event_card(event, nested=False):
            date = Paragraph(escape(event.display_date), date_style)
            title_text = escape(event.title)
            event_type = event.event_type or 'Acontecimiento'
            if event.automatic and not event.span_marker:
                title_text += ' <font color="#ff8da0" size="7">· AUTOMÁTICO</font>'
            event_title = Paragraph(f'<b>{title_text}</b><br/><font color="#ff8da0" size="7.5">{escape(event_type)}</font>', body_style)
            description = escape(event.description or (' ' if event.span_marker else 'Sin descripción')).replace('\r\n', '\n').replace('\n', '<br/>')
            links = []
            for link in event.character_links.all():
                links.append(f'◉ {escape(link.character.full_name)}')
            for link in event.place_links.all():
                links.append(f'⌖ {escape(link.place.name)}')
            detail_markup = description + (('<br/><font color="#a2a2ae" size="7">' + escape(' · '.join(links)) + '</font>') if links else '')
            details = Paragraph(detail_markup or ' ', body_style)
            if nested:
                card = Table([['', date, [event_title, Spacer(1, 2), details]]], colWidths=[1.0*cm, 2.7*cm, 14.4*cm])
                line_col = accent
                background = colors.HexColor('#17141a')
                card.setStyle(TableStyle([('BACKGROUND',(1,0),(-1,-1),background),('BOX',(1,0),(-1,-1),0.5,border),('LINEBEFORE',(1,0),(1,-1),2,line_col),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
            else:
                card = Table([[date, [event_title, Spacer(1, 2), details]]], colWidths=[3.0*cm, 15.1*cm])
                card.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),panel_alt),('BOX',(0,0),(-1,-1),0.5,border),('LINEBEFORE',(0,0),(0,-1),2,accent),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
            return card

        for item in timeline_items:
            if item['kind'] == 'event':
                story.extend([event_card(item['event']), Spacer(1, 6)])
                continue
            span = item['span']
            span_title = Paragraph(
                f'<b>{escape(span.title)}</b><br/><font color="#ff8da0" size="7.5">{escape(span.start_display)}  →  {escape(span.end_display)}</font>'
                + (f'<br/><font color="#b8b5c0" size="7.5">{escape(span.span_type)}</font>' if span.span_type else ''),
                body_style,
            )
            span_description = Paragraph(escape(span.description or 'Periodo delimitado por los acontecimientos de inicio y final.').replace('\r\n', '\n').replace('\n', '<br/>'), body_style)
            span_card = Table([[span_title, span_description]], colWidths=[6.1*cm, 12.0*cm])
            span_card.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#25151e')),('BOX',(0,0),(-1,-1),0.6,border),('LINEBEFORE',(0,0),(0,-1),3,accent),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
            story.extend([span_card, Spacer(1, 4)])
            if span.start_event:
                story.extend([event_card(span.start_event, nested=True), Spacer(1, 3)])
            for inner_event in span.inner_events:
                story.extend([event_card(inner_event, nested=True), Spacer(1, 3)])
            if span.end_event:
                story.extend([event_card(span.end_event, nested=True), Spacer(1, 5)])

        doc.build(story, onFirstPage=page_background, onLaterPages=page_background)
        response = HttpResponse(stream.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="cronologia_{project.pk}.pdf"'
        return response

    from PIL import Image, ImageDraw, ImageFont
    font_path = Path(settings.BASE_DIR) / 'static' / 'fonts' / 'Urbanist-VariableFont_wght.ttf'
    def font(size):
        try:
            return ImageFont.truetype(str(font_path), size)
        except OSError:
            return ImageFont.load_default()
    f_title, f_head, f_body, f_meta = font(43), font(28), font(20), font(15)
    width, margin = 1400, 58
    available = width - 2*margin - 45
    def wrap(text, selected_font, max_width):
        lines = []
        for source in ('' if text is None else str(text)).split('\n'):
            if not source.strip():
                lines.append('')
                continue
            line = ''
            for word in source.split():
                test = word if not line else f'{line} {word}'
                if draw.textbbox((0, 0), test, font=selected_font)[2] <= max_width:
                    line = test
                else:
                    if line: lines.append(line)
                    line = word
            if line: lines.append(line)
        return lines or ['']
    # Estimate a generous canvas, then crop to the actual final content height.
    # Each period renders a title card plus separate start/end markers and its
    # nested events, so reserve enough height before drawing and crop afterwards.
    estimate = 500 + len(spans)*450 + sum(165 + max(0, len(event.description or '')//78)*27 for event in events)
    estimate += sum(130 + max(0, len(span.description or '')//100)*26 for span in spans)
    image = Image.new('RGB', (width, max(1000, estimate+400)), '#0d0d10')
    draw = ImageDraw.Draw(image)
    draw.ellipse((-360, -500, 620, 600), fill='#171017')
    draw.rounded_rectangle((22, 22, width-22, image.height-22), radius=24, outline='#34313b', width=2)
    if logo_path.exists():
        try:
            logo = Image.open(logo_path).convert('RGBA')
            logo.thumbnail((72, 72), Image.Resampling.LANCZOS)
            image.paste(logo, (margin, 40), logo)
        except OSError:
            pass
    draw.text((margin+90, 45), 'OMNIVERSE', font=f_head, fill='#ff4263')
    draw.text((margin+90, 81), 'CRONOLOGÍA', font=f_meta, fill='#a2a2ae')
    y = 139
    draw.text((margin, y), project.name, font=f_title, fill='#f4f3f6')
    y += 61
    draw.text((margin, y), summary_text, font=f_meta, fill='#92929e')
    y += 40

    def card_text(text, x, y, max_width, selected_font, fill, line_height):
        lines = wrap(text, selected_font, max_width)
        for line in lines:
            if line: draw.text((x, y), line, font=selected_font, fill=fill)
            y += line_height if line else line_height+8
        return y

    def draw_event_card(event, indent=0, boundary_label=''):
        nonlocal y
        left = margin + indent
        right = width - margin
        text_x = left + 270
        text_width = max(220, right - text_x - 20)
        title_lines = wrap(event.title, f_body, text_width)
        desc_lines = wrap(event.description or ('' if event.span_marker else 'Sin descripción.'), f_meta, text_width)
        link_text = ' · '.join([link.character.full_name for link in event.character_links.all()] + [link.place.name for link in event.place_links.all()])
        link_lines = wrap(link_text, f_meta, text_width) if link_text else []
        meta_lines = wrap(boundary_label or event.event_type or 'Acontecimiento', f_meta, text_width)
        card_h = max(100, 23 + len(title_lines)*28 + len(meta_lines)*21 + len(desc_lines)*22 + len(link_lines)*20 + 26)
        if event.span_marker in {'START', 'END'}:
            fill, stroke, accent_color = '#171219', '#49303b', '#ff6480'
        else:
            fill, stroke, accent_color = '#15151b', '#34313b', '#ff4263'
        draw.rounded_rectangle((left, y, right, y+card_h), radius=12, fill=fill, outline=stroke, width=2)
        draw.rounded_rectangle((left, y, left+5, y+card_h), radius=2, fill=accent_color)
        draw.text((left+18, y+16), event.display_date, font=f_meta, fill=accent_color)
        cy = y+15
        for line in title_lines:
            if line: draw.text((text_x, cy), line, font=f_body, fill='#f2f0f4')
            cy += 28
        for line in meta_lines:
            if line: draw.text((text_x, cy+1), line, font=f_meta, fill='#ff8ca0')
            cy += 21
        if desc_lines:
            cy = card_text(event.description or '', text_x, cy, text_width, f_meta, '#b1b1bc', 22)
        if link_lines:
            cy += 4
            card_text('Vínculos: ' + link_text, text_x, cy, text_width, f_meta, '#92929e', 20)
        y += card_h+9

    if not timeline_items:
        draw.text((margin, y), 'No hay acontecimientos registrados.', font=f_body, fill='#a2a2ae')
        y += 50

    for item in timeline_items:
        if item['kind'] == 'event':
            draw_event_card(item['event'])
            continue
        span = item['span']
        left = margin
        right = width - margin
        title_lines = wrap(span.title, f_body, available-40)
        desc_lines = wrap(span.description or '', f_meta, available-40) if span.description else []
        card_h = 24 + len(title_lines)*28 + 24 + (len(desc_lines)*22 if desc_lines else 0) + (23 if span.span_type else 0)
        card_h = max(94, card_h)
        draw.rounded_rectangle((left, y, right, y+card_h), radius=13, fill='#25151e', outline='#53313d', width=2)
        draw.rounded_rectangle((left, y, left+5, y+card_h), radius=2, fill='#ff4263')
        cy = y+15
        cy = card_text(span.title, left+22, cy, available-30, f_body, '#f4f3f6', 28)
        draw.text((left+22, cy+1), f'{span.start_display}  →  {span.end_display}', font=f_meta, fill='#ff8ca0')
        cy += 25
        if span.span_type:
            draw.text((left+22, cy), span.span_type, font=f_meta, fill='#f07b90')
            cy += 23
        if desc_lines:
            card_text(span.description, left+22, cy, available-30, f_meta, '#b3b3be', 22)
        y += card_h+4
        if span.start_event:
            draw_event_card(span.start_event, indent=18, boundary_label='INICIO DEL LAPSO')
        for inner_event in span.inner_events:
            draw_event_card(inner_event, indent=52)
        if span.end_event:
            draw_event_card(span.end_event, indent=18, boundary_label='FINAL DEL LAPSO')
        y += 7

    image = image.crop((0, 0, width, min(image.height, y+30)))
    stream = BytesIO()
    image.save(stream, format='PNG', optimize=True)
    response = HttpResponse(stream.getvalue(), content_type='image/png')
    response['Content-Disposition'] = f'attachment; filename="cronologia_{project.pk}.png"'
    return response
@login_required
@require_POST
def move_event_order(request, event_id, direction):
    project = _active_project_or_redirect(request)
    if project is None:
        return redirect('home')
    if direction not in {'up', 'down'}:
        messages.error(request, 'Movimiento de orden no válido.')
        return redirect('timeline')
    event = get_object_or_404(Event, pk=event_id, project=project)
    if not event.date_value or event.span_marker:
        messages.error(request, 'Solo puedes reordenar acontecimientos que compartan una fecha definida.')
        return redirect('timeline')
    same_date = list(Event.objects.filter(project=project, date_value=event.date_value, date_era=event.date_era, span_marker='').order_by('sort_order', 'created_at', 'title', 'pk'))
    for idx, item in enumerate(same_date):
        item.sort_order = idx
    try:
        index = next(i for i, item in enumerate(same_date) if item.pk == event.pk)
    except StopIteration:
        return redirect('timeline')
    other_index = index - 1 if direction == 'up' else index + 1
    if 0 <= other_index < len(same_date):
        same_date[index], same_date[other_index] = same_date[other_index], same_date[index]
        for idx, item in enumerate(same_date):
            item.sort_order = idx
            item.save(update_fields=['sort_order', 'updated_at'])
        messages.success(request, 'Orden de acontecimientos actualizado.')
    return redirect('timeline')


@login_required
def span_create(request):
    project = _active_project_or_redirect(request)
    if project is None:
        return redirect('home')
    form = TimelineSpanForm(request.POST or None, project=project)
    if request.method == 'POST' and form.is_valid():
        span = form.save(commit=False)
        span.project = project
        span.save()
        _sync_span_boundary_events(span)
        messages.success(request, f'El lapso «{span.title}» fue creado.')
        return redirect('timeline')
    return render(request, 'timeline/span_form.html', {'project': project, 'form': form, 'mode': 'create'})


@login_required
def span_edit(request, pk):
    project = _active_project_or_redirect(request)
    if project is None:
        return redirect('home')
    span = get_object_or_404(TimelineSpan, pk=pk, project=project)
    form = TimelineSpanForm(request.POST or None, instance=span, project=project)
    if request.method == 'POST' and form.is_valid():
        span = form.save()
        _sync_span_boundary_events(span)
        messages.success(request, 'El lapso fue actualizado.')
        return redirect('timeline')
    return render(request, 'timeline/span_form.html', {'project': project, 'form': form, 'mode': 'edit', 'span': span})


@login_required
@require_POST
def span_delete(request, pk):
    project = _active_project_or_redirect(request)
    if project is None:
        return redirect('home')
    span = get_object_or_404(TimelineSpan, pk=pk, project=project)
    # Remove only the generated boundaries; ordinary events assigned to this
    # span are preserved and become top-level timeline events (SET_NULL).
    Event.objects.filter(project=project, timeline_span=span, span_marker__in=['START', 'END']).delete()
    span.delete()
    messages.success(request, 'El lapso fue eliminado. Los acontecimientos vinculados se conservaron en la cronología.')
    return redirect('timeline')
