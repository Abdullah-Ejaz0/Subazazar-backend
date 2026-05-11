# import json
# from django.http import JsonResponse
# from django.views.decorators.http import require_http_methods
# from django.views.decorators.csrf import csrf_exempt
# from api.supabase_client import supabase
# from api.middleware.auth import require_auth


# @csrf_exempt
# @require_http_methods(["POST"])
# def complete_onboarding(request):
#     """POST /api/auth/onboarding/ — called after registration to save name, language, voice pref."""
#     try:
#         body = json.loads(request.body)
#     except json.JSONDecodeError:
#         return JsonResponse({'error': 'Invalid JSON'}, status=400)

#     result = supabase.rpc('complete_onboarding', {
#         'p_user_id':   body['user_id'],
#         'p_full_name': body['full_name'],
#         'p_language':  body.get('language', 'en'),
#         'p_voice':     body.get('voice_assistance', False)
#     }).execute()
#     return JsonResponse({'status': 'onboarding complete'})


# @csrf_exempt
# @require_auth
# @require_http_methods(["POST"])
# def update_settings(request):
#     """POST /api/auth/settings/ — updates language and voice guidance preferences."""
#     try:
#         body = json.loads(request.body)
#     except json.JSONDecodeError:
#         return JsonResponse({'error': 'Invalid JSON'}, status=400)

#     result = supabase.rpc('update_user_settings', {
#         'p_user_id':  request.user_id,
#         'p_language': body['language'],
#         'p_voice':    body['voice_guidance']
#     }).execute()
#     return JsonResponse({'status': 'settings updated'})


# @csrf_exempt
# @require_auth
# @require_http_methods(["GET", "PATCH"])
# def get_profile(request):
#     """
#     GET  /api/auth/profile/ — returns the authenticated user's full profile.
#     PATCH /api/auth/profile/ — updates allowed profile fields (full_name, avatar_url, region, username).
#     """
#     if request.method == 'GET':
#         result = supabase \
#             .from_('profiles') \
#             .select('*') \
#             .eq('id', request.user_id) \
#             .single() \
#             .execute()
#         return JsonResponse(result.data)

#     # PATCH
#     try:
#         body = json.loads(request.body)
#     except json.JSONDecodeError:
#         return JsonResponse({'error': 'Invalid JSON'}, status=400)

#     # Whitelist allowed fields — never let a user change their own role
#     allowed = ['full_name', 'avatar_url', 'region', 'username']
#     update_data = {k: v for k, v in body.items() if k in allowed}

#     if not update_data:
#         return JsonResponse({'error': 'No valid fields to update'}, status=400)

#     supabase \
#         .from_('profiles') \
#         .update(update_data) \
#         .eq('id', request.user_id) \
#         .execute()

#     return JsonResponse({'status': 'profile updated'})









import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from api.supabase_client import supabase, supabase_admin
from api.middleware.auth import require_auth


# ─────────────────────────────────────────────────────────────
#  FARMER AUTH  (phone-based, OTP handled on frontend)
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def check_phone(request):
    """
    POST /api/auth/check-phone/
    Body: { "phone_number": "+923001234567" }

    Checks whether a farmer with this phone number already exists.
    Returns status=1 (user exists → login flow) with profile data,
    or status=0 (new user → signup flow).
    """
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    phone_number = body.get('phone_number')
    if not phone_number:
        return JsonResponse(
            {'detail': 'phone_number is required.'},
            status=400
        )

    try:
        result = supabase_admin \
            .from_('profiles') \
            .select('*') \
            .eq('phone', phone_number) \
            .single() \
            .execute()

        if result.data:
            return JsonResponse({
                'status': 1,
                'message': 'User exists. Proceeding to login.',
                'user': result.data
            })
    except Exception:
        pass

    # User doesn't exist → signup flow
    return JsonResponse({
        'status': 0,
        'message': 'New user. Proceeding to signup.'
    })


@csrf_exempt
@require_http_methods(["POST"])
def farmer_signup(request):
    """
    POST /api/auth/farmer/signup/
    Body: {
        "phone_number": "+923001234567",
        "full_name": "Ali Khan",                 (optional)
        "preferred_language": "en",               (required: en, ur, pa)
        "voice_assistant_enabled": false           (optional, default false)
    }

    Registers a new farmer via Supabase Phone Auth, then completes their profile.
    OTP verification is handled on the frontend — this endpoint creates the auth user
    and profile row.
    """
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    phone_number = body.get('phone_number')
    preferred_language = body.get('preferred_language')
    voice_assistant_enabled = body.get('voice_assistant_enabled', False)
    full_name = body.get('full_name')

    if not phone_number:
        return JsonResponse(
            {'detail': 'phone_number is required.'},
            status=400
        )

    if not preferred_language:
        return JsonResponse(
            {'detail': 'preferred_language is required.'},
            status=400
        )

    if preferred_language not in ('en', 'ur', 'pa'):
        return JsonResponse(
            {'detail': 'preferred_language must be one of: en, ur, pa'},
            status=400
        )

    # Check if the farmer already exists
    try:
        existing = supabase_admin \
            .from_('profiles') \
            .select('id') \
            .eq('phone', phone_number) \
            .execute()

        if existing.data:
            return JsonResponse(
                {'detail': 'User with this phone number already exists.'},
                status=400
            )
    except Exception:
        pass

    # Look up the auth.users entry created by Supabase phone OTP verification
    try:
        auth_users = supabase_admin.auth.admin.list_users()
        user_id = None
        for u in auth_users:
            if getattr(u, 'phone', None) == phone_number:
                user_id = u.id
                break

        if not user_id:
            return JsonResponse(
                {'error': 'Phone number not verified in Supabase Auth. '
                          'Complete OTP verification before calling signup.'},
                status=400
            )
    except Exception as e:
        return JsonResponse(
            {'error': f'Could not look up auth user: {str(e)}'},
            status=500
        )

    # Upsert the profile row (handles both: trigger already ran, or hasn't yet)
    try:
        supabase_admin \
            .from_('profiles') \
            .upsert({
                'id':               user_id,
                'phone':            phone_number,
                'full_name':        full_name,
                'language':         preferred_language,
                'voice_assistance': voice_assistant_enabled,
                'role':             'farmer',
            }) \
            .execute()

        # Fetch the completed profile
        profile = supabase_admin \
            .from_('profiles') \
            .select('*') \
            .eq('id', user_id) \
            .single() \
            .execute()

        return JsonResponse({
            'status': 1,
            'message': 'Farmer registered successfully.',
            'user': profile.data
        }, status=201)

    except Exception as e:
        return JsonResponse(
            {'error': f'Signup failed: {str(e)}'},
            status=500
        )


# ─────────────────────────────────────────────────────────────
#  EXPERT AUTH  (email + password)
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def expert_signup(request):
    """
    POST /api/auth/expert/signup/
    Body: {
        "email": "dr.expert@example.com",
        "password": "securepassword123",
        "full_name": "Dr. Ahmad",
        "username": "dr_ahmad"
    }

    Creates an expert account using Supabase email/password auth.
    The profile trigger creates the row; this endpoint then updates
    the role to 'expert'.
    """
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    email = body.get('email')
    password = body.get('password')
    full_name = body.get('full_name')
    username = body.get('username')

    if not email or not password:
        return JsonResponse(
            {'detail': 'email and password are required.'},
            status=400
        )

    try:
        # Create auth user via Supabase Admin
        auth_response = supabase_admin.auth.admin.create_user({
            'email': email,
            'password': password,
            'email_confirm': True,
            'user_metadata': {
                'full_name': full_name
            }
        })

        user_id = auth_response.user.id

        # Update the auto-created profile to set expert role + details
        supabase_admin \
            .from_('profiles') \
            .update({
                'role': 'expert',
                'full_name': full_name,
                'username': username,
            }) \
            .eq('id', user_id) \
            .execute()

        # Fetch completed profile
        profile = supabase_admin \
            .from_('profiles') \
            .select('*') \
            .eq('id', user_id) \
            .single() \
            .execute()

        return JsonResponse({
            'status': 1,
            'message': 'Expert account created successfully.',
            'user': profile.data
        }, status=201)

    except Exception as e:
        return JsonResponse(
            {'error': f'Expert signup failed: {str(e)}'},
            status=500
        )


@csrf_exempt
@require_http_methods(["POST"])
def expert_login(request):
    """
    POST /api/auth/expert/login/
    Body: { "email": "dr.expert@example.com", "password": "securepassword123" }

    Authenticates an expert via email + password.
    Returns the session token and profile data.
    """
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    email = body.get('email')
    password = body.get('password')

    if not email or not password:
        return JsonResponse(
            {'detail': 'email and password are required.'},
            status=400
        )

    try:
        auth_response = supabase.auth.sign_in_with_password({
            'email': email,
            'password': password,
        })

        user_id = auth_response.user.id

        # Verify user is actually an expert
        profile = supabase_admin \
            .from_('profiles') \
            .select('*') \
            .eq('id', user_id) \
            .single() \
            .execute()

        if not profile.data or profile.data.get('role') != 'expert':
            return JsonResponse(
                {'error': 'This account is not registered as an expert. Use farmer login instead.'},
                status=403
            )

        return JsonResponse({
            'status': 1,
            'message': 'Login successful.',
            'access_token': auth_response.session.access_token,
            'refresh_token': auth_response.session.refresh_token,
            'user': profile.data
        })

    except Exception as e:
        return JsonResponse(
            {'error': f'Login failed: {str(e)}'},
            status=401
        )


# ─────────────────────────────────────────────────────────────
#  ONBOARDING  (post-registration preferences setup)
# ─────────────────────────────────────────────────────────────
@csrf_exempt
@api_view(["POST"])
@require_http_methods(["POST"])
def complete_onboarding(request):
    """POST /api/auth/onboarding/ — called after registration to save name, language, voice pref."""
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    result = supabase.rpc('complete_onboarding', {
        'p_user_id':   body['user_id'],
        'p_full_name': body['full_name'],
        'p_language':  body.get('language', 'en'),
        'p_voice':     body.get('voice_assistance', False)
    }).execute()
    return JsonResponse({'status': 'onboarding complete'})


# ─────────────────────────────────────────────────────────────
#  SETTINGS
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@api_view(["POST"])
@require_auth
@require_http_methods(["POST"])
def update_settings(request):
    """POST /api/auth/settings/ — updates language and voice guidance preferences."""
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    result = supabase.rpc('update_user_settings', {
        'p_user_id':  request.user_id,
        'p_language': body['language'],
        'p_voice':    body['voice_guidance']
    }).execute()
    return JsonResponse({'status': 'settings updated'})


# ─────────────────────────────────────────────────────────────
#  PROFILE  (view + update)
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@api_view(["GET", "PATCH"])
@require_auth
@require_http_methods(["GET", "PATCH"])
def get_profile(request):
    """
    GET  /api/auth/profile/ — returns the authenticated user's full profile.
    PATCH /api/auth/profile/ — updates allowed profile fields.
    """
    if request.method == 'GET':
        result = supabase \
            .from_('profiles') \
            .select('*') \
            .eq('id', request.user_id) \
            .single() \
            .execute()
        return JsonResponse(result.data)

    # PATCH
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    # Whitelist allowed fields — never let a user change their own role or is_verified_expert
    allowed = ['full_name', 'avatar_url', 'region', 'username', 'language', 'voice_assistance']
    update_data = {k: v for k, v in body.items() if k in allowed}

    if not update_data:
        return JsonResponse({'error': 'No valid fields to update'}, status=400)

    supabase \
        .from_('profiles') \
        .update(update_data) \
        .eq('id', request.user_id) \
        .execute()

    # Return updated profile
    result = supabase \
        .from_('profiles') \
        .select('*') \
        .eq('id', request.user_id) \
        .single() \
        .execute()

    return JsonResponse({
        'status': 'profile updated',
        'user': result.data
    })


@csrf_exempt
@require_auth
@require_http_methods(["POST"])
def update_profile(request):
    """
    POST /api/auth/profile/update/
    Body: {
        "full_name": "Ali Khan",
        "avatar_url": "https://...",
        "region": "Punjab", (or "location")
        "username": "ali_khan",
        "language": "ur", (or "preferred_language")
        "voice_assistance": true
    }

    Updates the authenticated user's profile.
    All fields are optional — only provided fields are updated.
    Certain fields (role, is_verified_expert, phone) cannot be changed.
    """
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    # Map Android app field names to DB field names
    if 'location' in body:
        body['region'] = body.pop('location')
    if 'preferred_language' in body:
        body['language'] = body.pop('preferred_language')
    if 'voice_assistant_enabled' in body:
        body['voice_assistance'] = body.pop('voice_assistant_enabled')

    # Whitelist allowed fields
    allowed = ['full_name', 'avatar_url', 'region', 'username', 'language', 'voice_assistance']
    update_data = {k: v for k, v in body.items() if k in allowed}

    if not update_data:
        return JsonResponse({'error': 'No valid fields to update. Allowed: ' + ', '.join(allowed)}, status=400)

    # Validate language if provided
    if 'language' in update_data and update_data['language'] not in ('en', 'ur', 'pa'):
        return JsonResponse({'detail': 'language must be one of: en, ur, pa'}, status=400)

    try:
        # Use supabase_admin to bypass RLS, since we already verified the user via @require_auth
        supabase_admin \
            .from_('profiles') \
            .update(update_data) \
            .eq('id', request.user_id) \
            .execute()

        # If language or voice changed, also update user_settings
        if 'language' in update_data or 'voice_assistance' in update_data:
            # Fetch current settings to fill in any missing values
            current = supabase_admin \
                .from_('profiles') \
                .select('language, voice_assistance') \
                .eq('id', request.user_id) \
                .single() \
                .execute()

            supabase_admin.rpc('update_user_settings', {
                'p_user_id':  request.user_id,
                'p_language': current.data['language'],
                'p_voice':    current.data['voice_assistance']
            }).execute()

        # Return updated profile
        result = supabase_admin \
            .from_('profiles') \
            .select('*') \
            .eq('id', request.user_id) \
            .single() \
            .execute()

        return JsonResponse({
            'status': 'profile updated',
            'user': result.data
        })

    except Exception as e:
        return JsonResponse(
            {'error': f'Profile update failed: {str(e)}'},
            status=500
        )