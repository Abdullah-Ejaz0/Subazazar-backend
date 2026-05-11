import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from api.supabase_client import supabase
from api.middleware.auth import require_auth


@api_view(["GET"])
@require_auth
@require_http_methods(["GET"])
def community_feed(request):
    """GET /api/community/ — paginated forum feed with optional category/search filters."""
    result = supabase.rpc('get_community_posts', {
        'p_category': request.GET.get('category'),
        'p_search':   request.GET.get('search'),
        'p_limit':    int(request.GET.get('limit', 20)),
        'p_offset':   int(request.GET.get('offset', 0))
    }).execute()
    return JsonResponse(result.data or [], safe=False)

@csrf_exempt
@api_view(["POST"])
@require_auth
@require_http_methods(["POST"])
def submit_post(request):
    """POST /api/community/post/ — farmer submits a new question to the forum."""
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    try:
        result = supabase.rpc('submit_community_post', {
            'p_author_id': request.user_id,
            'p_body':      body['body'],
            'p_category':  body.get('category', 'general'),
            'p_photo_url': body.get('photo_url'),
            'p_crop_id':   body.get('crop_id')
        }).execute()
        return JsonResponse({'post_id': result.data}, status=201)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@api_view(["POST"])
@require_auth
@require_http_methods(["POST"])
def upload_photo(request):
    """POST /api/community/upload-photo/ — upload an image to community-photos bucket."""
    image = request.FILES.get('photo')
    if not image:
        return JsonResponse({"error": "No photo provided"}, status=400)
    
    try:
        file_bytes = image.read()
        import os
        import uuid
        image_ext = os.path.splitext(image.name)[1] or ".jpg"
        object_name = f"{request.user_id}/{uuid.uuid4().hex}{image_ext}"
        content_type = image.content_type or "image/jpeg"
        
        from api.supabase_client import supabase_admin
        upload_result = supabase_admin.storage.from_("community-photos").upload(
            object_name,
            file_bytes,
            {"content-type": content_type, "upsert": "false"},
        )
        if getattr(upload_result, "error", None):
            return JsonResponse({"error": f"Upload failed: {upload_result.error}"}, status=502)
            
        return JsonResponse({"photo_url": object_name}, status=200)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(exc)}, status=500)


@api_view(["GET"])
@require_auth
@require_http_methods(["GET"])
def post_detail(request, post_id):
    """GET /api/community/<post_id>/ — single post with all replies."""
    result = supabase.rpc('get_post_detail', {
        'p_post_id': post_id
    }).execute()

    replies = result.data or []

    # Safely enrich with is_expert if author_id is present in the RPC response
    author_ids = [r['author_id'] for r in replies if r.get('author_id')]
    expert_ids = set()
    if author_ids:
        try:
            experts = supabase.table('experts').select('id').in_('id', author_ids).execute()
            expert_ids = {e['id'] for e in experts.data} if experts.data else set()
        except Exception:
            pass  # experts table may not exist yet; fall back to is_verified only

    for r in replies:
        r['is_expert'] = r.get('author_id') in expert_ids if r.get('author_id') else False

    return JsonResponse(replies, safe=False)


@csrf_exempt
@api_view(["POST"])
@require_auth
@require_http_methods(["POST"])
def submit_reply(request, post_id):
    """POST /api/community/<post_id>/replies/ — reply to a community post."""
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    result = supabase.rpc('submit_community_reply', {
        'p_post_id':     post_id,
        'p_author_id':   request.user_id,
        'p_body':        body['body'],
        'p_is_verified': body.get('is_verified', False)
    }).execute()
    return JsonResponse({'reply_id': result.data}, status=201)


@api_view(["GET"])
@require_auth
def user_history(request):
    """GET /api/community/my-history/ — returns questions the user has asked or replied to."""
    try:
        result = supabase.rpc('get_user_community_history', {
            'p_user_id': request.user_id
        }).execute()
        return JsonResponse(result.data or [], safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
