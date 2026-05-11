import json
import os
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from api.supabase_client import supabase, supabase_admin
from api.middleware.auth import require_auth


@api_view(["GET"])
@require_auth
@require_http_methods(["GET"])
def recent_scans(request):
    """GET /api/scans/recent/ — returns last N scans for the authenticated user."""
    result = supabase.rpc('get_recent_scans', {
        'p_user_id': request.user_id,
        'p_limit': 5
    }).execute()
    
    scans = result.data or []
    for scan in scans:
        if scan.get('image_url'):
            try:
                # Try generating a signed URL using supabase_admin to bypass RLS policies
                signed = supabase_admin.storage.from_("scan-images").create_signed_url(scan['image_url'], 3600)
                scan['signed_url'] = signed.get('signedURL')
            except Exception:
                try:
                    # Fallback to public URL
                    scan['signed_url'] = supabase_admin.storage.from_("scan-images").get_public_url(scan['image_url'])
                except Exception:
                    scan['signed_url'] = None

    return JsonResponse(scans, safe=False)


@api_view(["GET"])
@require_auth
@require_http_methods(["GET"])
def scan_detail(request, scan_id):
    """GET /api/scans/<scan_id>/ — returns full scan result with treatment details."""
    result = supabase.rpc('get_scan_detail', {
        'p_scan_id': scan_id,
        'p_user_id': request.user_id
    }).execute()
    if not result.data:
        return JsonResponse({'error': 'Scan not found'}, status=404)
    return JsonResponse(result.data[0])


@csrf_exempt
@api_view(["POST"])
@require_http_methods(["POST"])
def save_scan(request):
    """
    POST /api/scans/ — called by the AI/CV team (not by the mobile app directly).
    Authenticates via X-Internal-Key header instead of Bearer JWT.
    Uses supabase_admin to bypass RLS.
    """
    api_key = request.headers.get('X-Internal-Key', '')
    if api_key != os.getenv('INTERNAL_API_KEY'):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    required = ['user_id', 'image_url', 'crop_name',
                'disease_name', 'confidence', 'risk_level']
    for field in required:
        if field not in body:
            return JsonResponse({'error': f'Missing field: {field}'}, status=400)

    result = supabase_admin.rpc('save_scan_result', {
        'p_user_id':      body['user_id'],
        'p_image_url':    body['image_url'],
        'p_crop_name':    body['crop_name'],
        'p_disease_name': body['disease_name'],
        'p_confidence':   body['confidence'],
        'p_risk_level':   body['risk_level'],
        'p_ai_raw':       body.get('ai_raw')
    }).execute()
    return JsonResponse({'scan_id': result.data}, status=201)
