import functools
from django.conf import settings
from django.http import JsonResponse
from api.supabase_client import supabase, supabase_admin



def require_auth(view_func):
    """
    Decorator that validates the Supabase JWT from the Authorization header.
    Sets request.user_id and request.user_token on success.

    DEBUG bypass: when settings.DEBUG is True and no Bearer token is present,
    a fake user_id is injected so endpoints can be exercised via Swagger without
    a real Supabase account.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            if settings.DEBUG:
                request.user_id = "00000000-0000-0000-0000-000000000000"
                request.user_token = "debug_token"
                return view_func(request, *args, **kwargs)
            return JsonResponse({'error': 'Authorization header missing'}, status=401)

        token = auth_header.split(' ')[1]

        try:
            response = supabase.auth.get_user(token)
        except Exception:
            return JsonResponse({'error': 'Token validation failed'}, status=401)

        if not response.user:
            return JsonResponse({'error': 'Invalid or expired token'}, status=401)

        request.user_id = response.user.id
        request.user_token = token
        return view_func(request, *args, **kwargs)
    return wrapper


def require_expert(view_func):
    """
    Decorator that checks if the authenticated user has expert role.
    Must be used AFTER @require_auth so that request.user_id is set.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            result = supabase_admin \
                .from_('profiles') \
                .select('role, is_verified_expert') \
                .eq('id', request.user_id) \
                .single() \
                .execute()
        except Exception:
            return JsonResponse({'error': 'Could not verify expert status'}, status=403)

        profile = result.data
        if not profile:
            return JsonResponse({'error': 'Profile not found'}, status=404)

        if profile['role'] != 'expert' or not profile['is_verified_expert']:
            return JsonResponse({'error': 'Expert access required'}, status=403)

        return view_func(request, *args, **kwargs)
    return wrapper
