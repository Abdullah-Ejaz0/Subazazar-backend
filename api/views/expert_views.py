import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from api.supabase_client import supabase
from api.middleware.auth import require_auth, require_expert


@api_view(["GET"])
@require_auth
@require_expert
@require_http_methods(["GET"])
def dashboard_stats(request):
    """GET /api/expert/dashboard/stats/ — returns real counts for the dashboard."""
    # 1. Get verified post IDs (Solved)
    verified = supabase.table('community_replies') \
        .select('post_id') \
        .eq('is_verified', True) \
        .execute()
    answered_ids = {r['post_id'] for r in verified.data} if verified.data else set()

    # 2. Get all posts in one go to count Pending, Urgent, and Today
    all_posts = supabase.table('community_posts').select('id, category, created_at').execute()
    all_data = all_posts.data or []
    
    from datetime import datetime, date
    today_str = date.today().isoformat()
    
    pending_count = 0
    urgent_count = 0
    today_count = 0
    
    for p in all_data:
        is_answered = p['id'] in answered_ids
        if not is_answered:
            pending_count += 1
            
            # Strict Urgent Check
            cat = str(p.get('category', '')).lower()
            if cat == 'crop_disease' or cat == 'urgent':
                urgent_count += 1
        
        # Count if created today
        if p.get('created_at', '').startswith(today_str):
            today_count += 1

    return JsonResponse({
        'pending':   pending_count,
        'answered':  len(answered_ids),
        'today':     today_count,
        'urgent':    urgent_count
    })


@api_view(["GET"])
@require_auth
@require_expert
@require_http_methods(["GET"])
def pending_questions(request):
    """
    GET /api/expert/pending/
    Returns all community posts that do NOT have a verified reply yet.
    """
    # 1. Get IDs of all posts that HAVE a verified reply
    verified = supabase.table('community_replies') \
        .select('post_id') \
        .eq('is_verified', True) \
        .execute()
    
    answered_ids = [r['post_id'] for r in verified.data] if verified.data else []

    # 2. Get all posts
    # In a production app, we'd do a complex join or 'not.in', but for reliability now:
    all_posts = supabase.table('community_posts') \
        .select('*, profiles(full_name)') \
        .order('created_at', desc=True) \
        .execute()

    # 3. Filter for unanswered and format for the app
    pending = []
    for p in (all_posts.data or []):
        if p['id'] not in answered_ids:
            # Map database names to app expectations
            p['post_id'] = p['id']
            p['author_name'] = p.get('profiles', {}).get('full_name', 'Unknown Farmer')
            pending.append(p)

    return JsonResponse(pending, safe=False)


@csrf_exempt
@api_view(["POST"])
@require_auth
@require_expert
@require_http_methods(["POST"])
def send_broadcast(request):
    """POST /api/expert/broadcast/ — expert sends an alert broadcast, optionally targeted to a region."""
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    result = supabase.rpc('send_broadcast', {
        'p_expert_id': request.user_id,
        'p_title':     body['title'],
        'p_message':   body['message'],
        'p_region':    body.get('target_region')
    }).execute()
    return JsonResponse({'broadcast_id': result.data}, status=201)
