import json
import requests as http_requests
from datetime import datetime, timedelta, timezone
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from api.supabase_client import supabase, supabase_admin
from api.middleware.auth import require_auth


@csrf_exempt
@api_view(["POST"])
@require_auth
@require_http_methods(["POST"])
def get_upload_url(request):
    """
    POST /api/storage/upload-url/
    Body: { "bucket": "scan-images" or "community-photos", "filename": "photo.jpg" }
    Returns a signed URL the frontend uses to upload directly to Supabase Storage.
    """
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    bucket = body.get('bucket')
    filename = body.get('filename')

    if bucket not in ['scan-images', 'community-photos']:
        return JsonResponse({'error': 'Invalid bucket name. Use scan-images or community-photos'}, status=400)

    if not filename:
        return JsonResponse({'error': 'filename is required'}, status=400)

    # scan-images stored under user's folder so RLS policy (foldername = user_id) works
    if bucket == 'scan-images':
        path = f"{request.user_id}/{filename}"
    else:
        path = f"posts/{filename}"

    try:
        # The python supabase client has a known bug with create_signed_upload_url 
        # throwing "'dict' object has no attribute 'signed_url'". We bypass it via direct REST call.
        import requests as http_requests
        import os
        
        project_url = os.getenv('SUPABASE_URL')
        service_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        url = f"{project_url}/storage/v1/object/upload/sign/{bucket}/{path}"
        
        resp = http_requests.post(url, headers={
            'Authorization': f'Bearer {service_key}',
            'apikey': service_key,
            'Content-Type': 'application/json'
        })
        resp.raise_for_status()
        
        data = resp.json()
        return JsonResponse({
            'signed_url': project_url + data.get('url'),
            'path': path,
            'token': data.get('token', '')
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@api_view(["GET"])
@require_auth
@require_http_methods(["GET"])
def weather(request):
    """
    GET /api/weather/?lat=31.5497&lon=74.3436
    Checks Supabase cache first (1hr TTL). If stale, fetches fresh data from
    Open-Meteo (free, no API key, uses ECMWF/NOAA/DWD models).
    Returns current conditions and plain-language advisories for the home dashboard.
    """
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')

    if not lat or not lon:
        return JsonResponse({'error': 'lat and lon query params are required'}, status=400)

    region_key = f"{round(float(lat), 2)},{round(float(lon), 2)}"

    # Check cache first (1 hour TTL)
    try:
        cached = supabase_admin \
            .from_('weather_cache') \
            .select('*') \
            .eq('region', region_key) \
            .order('fetched_at', desc=True) \
            .limit(1) \
            .execute()

        if cached.data:
            fetched_at = datetime.fromisoformat(
                cached.data[0]['fetched_at'].replace('Z', '+00:00')
            )
            age = datetime.now(timezone.utc) - fetched_at
            if age < timedelta(hours=1):
                return JsonResponse(cached.data[0])
    except Exception:
        pass

    # Fetch fresh from Open-Meteo (no API key required)
    try:
        om_resp = http_requests.get(
            'https://api.open-meteo.com/v1/forecast',
            params={
                'latitude': lat,
                'longitude': lon,
                'current': 'temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code',
                'daily': 'weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max',
                'forecast_days': 3,
                'timezone': 'auto'
            },
            timeout=10
        )
        om_data = om_resp.json()
    except Exception as e:
        return JsonResponse({'error': f'Weather fetch failed: {str(e)}'}, status=500)

    if om_resp.status_code != 200:
        return JsonResponse({'error': 'Open-Meteo API error', 'detail': om_data}, status=502)

    current = om_data.get('current', {})
    temp      = current.get('temperature_2m')
    humidity  = current.get('relative_humidity_2m')
    wind      = current.get('wind_speed_10m')
    wmo_code  = current.get('weather_code', 0)

    # Map WMO weather codes to human-readable conditions
    # 0=Clear, 1-3=Cloudy, 45-48=Fog, 51-67=Rain/Drizzle, 71-77=Snow, 80-82=Showers, 95-99=Thunderstorm
    if wmo_code == 0:
        condition = 'Clear'
    elif wmo_code <= 3:
        condition = 'Cloudy'
    elif wmo_code <= 48:
        condition = 'Fog'
    elif wmo_code <= 67:
        condition = 'Rain'
    elif wmo_code <= 77:
        condition = 'Snow'
    elif wmo_code <= 82:
        condition = 'Showers'
    elif wmo_code <= 99:
        condition = 'Thunderstorm'
    else:
        condition = 'Unknown'

    # Generate plain-language advisories for the dashboard banner
    advisory_spray = None
    advisory_irrig = None
    advisory_sow   = None

    if condition in ['Rain', 'Showers', 'Drizzle', 'Thunderstorm']:
        advisory_spray = 'Rain expected — delay spraying'
        advisory_irrig = 'Rain expected — skip irrigation today'
    if humidity and humidity > 80:
        advisory_spray = (advisory_spray or '') + ' | High humidity — disease risk elevated'
    if wind and wind < 15:
        advisory_sow = 'Light wind — good conditions for sowing'

    weather_row = {
        'region':         region_key,
        'temperature':    temp,
        'humidity':       humidity,
        'wind_speed':     wind,
        'condition':      condition,
        'advisory_spray': advisory_spray,
        'advisory_irrig': advisory_irrig,
        'advisory_sow':   advisory_sow,
        'forecast_json':  om_data.get('daily', {}),
    }

    # Save to cache — don't fail the request if this errors
    try:
        supabase_admin.from_('weather_cache').insert(weather_row).execute()
    except Exception:
        pass

    return JsonResponse(weather_row)


@api_view(["GET"])
@require_auth
@require_http_methods(["GET"])
def chatbot_faqs(request):
    """GET /api/chatbot/faqs/ — returns localised FAQ content for the chatbot."""
    result = supabase.rpc('get_chatbot_faqs', {
        'p_category': request.GET.get('category'),
        'p_language': request.GET.get('language', 'en')
    }).execute()
    return JsonResponse(result.data, safe=False)


@api_view(["GET"])
@require_auth
@require_http_methods(["GET"])
def broadcasts(request):
    """GET /api/broadcasts/ — returns broadcast alerts for the farmer's region."""
    result = supabase.rpc('get_broadcasts', {
        'p_region': request.GET.get('region'),
        'p_limit':  int(request.GET.get('limit', 10))
    }).execute()
    return JsonResponse(result.data, safe=False)


@api_view(["GET"])
@require_http_methods(["GET"])
def health_check(request):
    """GET /api/health/ — no auth needed, verifies Django can reach Supabase."""
    try:
        result = supabase.from_('crops').select('name').limit(1).execute()
        return JsonResponse({'status': 'ok', 'db': 'connected'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'detail': str(e)}, status=500)
