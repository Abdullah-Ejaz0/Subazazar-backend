import io
import json
import re
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from api.supabase_client import supabase
from api.middleware.auth import require_auth


def _normalize_text(text):
    if not text:
        return ''
    text = text.replace('\r', '\n')
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r'[\t ]+', ' ', text)
    return text.strip()


def _find_value(text, label_patterns):
    for label in label_patterns:
        pattern = rf'(?:{label})[^0-9]{{0,20}}([0-9]+(?:\.[0-9]+)?)'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue
    return None


def _extract_notes(text):
    match = re.search(r'(?:notes?|remarks?)\s*[:\-]?\s*(.+)', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()[:500]
    return None


def _extract_text_from_image(image):
    try:
        import pytesseract
    except ImportError as exc:
        raise RuntimeError('pytesseract is not installed') from exc
    return pytesseract.image_to_string(image)


def _extract_text_from_pdf(file_bytes):
    text_chunks = []
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ''
                if page_text:
                    text_chunks.append(page_text)
    except Exception:
        text_chunks = []

    text = _normalize_text('\n'.join(text_chunks))
    if len(text) >= 40:
        return text

    try:
        from pdf2image import convert_from_bytes
    except ImportError as exc:
        raise RuntimeError('pdf2image is not installed') from exc

    images = convert_from_bytes(file_bytes)
    ocr_chunks = []
    for image in images:
        ocr_chunks.append(_extract_text_from_image(image))

    return _normalize_text('\n'.join(ocr_chunks))


def _parse_soil_upload(upload):
    file_name = (upload.name or '').lower()
    is_pdf = file_name.endswith('.pdf') or upload.content_type == 'application/pdf'
    is_txt = file_name.endswith('.txt') or upload.content_type == 'text/plain'

    file_bytes = upload.read()
    if is_pdf:
        raw_text = _extract_text_from_pdf(file_bytes)
        source = 'pdf'
    elif is_txt:
        raw_text = file_bytes.decode('utf-8', errors='ignore')
        source = 'text'
    else:
        try:
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError('Pillow is not installed') from exc

        image = Image.open(io.BytesIO(file_bytes))
        raw_text = _normalize_text(_extract_text_from_image(image))
        source = 'image'

    text = _normalize_text(raw_text)

    ph = _find_value(text, [r'\bph\b', r'\bp\s*h\b'])
    nitrogen = _find_value(text, [r'\bnitrogen\b', r'\bN\b'])
    phosphorus = _find_value(text, [r'\bphosphorus\b', r'\bp2o5\b'])
    potassium = _find_value(text, [r'\bpotassium\b', r'\bk2o\b'])
    notes = _extract_notes(text)

    missing = [
        key for key, value in {
            'ph': ph,
            'nitrogen': nitrogen,
            'phosphorus': phosphorus,
            'potassium': potassium,
        }.items() if value is None
    ]

    return {
        'ph': ph,
        'nitrogen': nitrogen,
        'phosphorus': phosphorus,
        'potassium': potassium,
        'notes': notes,
        'source': source,
        'missing': missing,
    }


@api_view(["GET"])
@require_auth
@require_http_methods(["GET"])
def latest_soil(request):
    """GET /api/soil/latest/ — returns the most recent soil health reading for the user."""
    result = supabase.rpc('get_latest_soil_health', {
        'p_user_id': request.user_id
    }).execute()
    if not result.data:
        return JsonResponse({}, status=200)
    return JsonResponse(result.data[0])


@csrf_exempt
@api_view(["POST"])
@require_auth
@require_http_methods(["POST"])
def save_soil(request):
    """POST /api/soil/ — saves a new soil health reading (pH, N, P, K)."""
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    result = supabase.rpc('upsert_soil_health', {
        'p_user_id': request.user_id,
        'p_ph':      body.get('ph'),
        'p_n':       body.get('nitrogen'),
        'p_p':       body.get('phosphorus'),
        'p_k':       body.get('potassium'),
        'p_notes':   body.get('notes')
    }).execute()
    return JsonResponse({'entry_id': result.data}, status=201)


@csrf_exempt
@api_view(["POST"])
@require_auth
@require_http_methods(["POST"])
def parse_soil_report(request):
    """POST /api/soil/parse/ — parses a soil report (image or PDF) and extracts NPK + pH."""
    upload = (
        request.FILES.get('soil report')
        or request.FILES.get('soil_report')
        or request.FILES.get('file')
    )

    if not upload:
        return JsonResponse({'error': 'Missing file field: soil report'}, status=400)

    try:
        parsed = _parse_soil_upload(upload)
    except RuntimeError as exc:
        return JsonResponse({'error': str(exc)}, status=500)
    except Exception as exc:
        return JsonResponse({'error': f'Failed to parse report: {str(exc)}'}, status=500)

    return JsonResponse(parsed)


@csrf_exempt
@api_view(["POST"])
@require_auth
@require_http_methods(["POST"])
def parse_soil_report_save(request):
    """POST /api/soil/parse/save/ — parses soil report and saves values to the database."""
    upload = (
        request.FILES.get('soil report')
        or request.FILES.get('soil_report')
        or request.FILES.get('file')
    )

    if not upload:
        return JsonResponse({'error': 'Missing file field: soil report'}, status=400)

    try:
        parsed = _parse_soil_upload(upload)
    except RuntimeError as exc:
        return JsonResponse({'error': str(exc)}, status=500)
    except Exception as exc:
        return JsonResponse({'error': f'Failed to parse report: {str(exc)}'}, status=500)

    if parsed['missing']:
        return JsonResponse({
            'error': 'Missing required fields',
            'missing': parsed['missing'],
            'parsed': parsed,
        }, status=400)

    result = supabase.rpc('upsert_soil_health', {
        'p_user_id': request.user_id,
        'p_ph':      parsed['ph'],
        'p_n':       parsed['nitrogen'],
        'p_p':       parsed['phosphorus'],
        'p_k':       parsed['potassium'],
        'p_notes':   parsed['notes']
    }).execute()

    return JsonResponse({
        'entry_id': result.data,
        'parsed': parsed,
    }, status=201)
