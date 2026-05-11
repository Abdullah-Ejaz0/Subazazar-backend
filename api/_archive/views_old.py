from rest_framework.decorators import api_view, permission_classes
from rest_framework.decorators import parser_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from django.utils import timezone

from .models import (
    ExpertCommunityPost,
    LanguageOnboardingSession,
    QuestionPost,
    ScanImageUpload,
    SoilHealthCard,
    UserPreference,
)
from .serializers import (
    CancelOnboardingSerializer,
    ExpertCommunityPostCreateSerializer,
    ExpertCommunityPostSerializer,
    LanguageOnboardingSessionSerializer,
    PhoneInputSerializer,
    QuestionPostCreateSerializer,
    QuestionPostSerializer,
    ScanImageUploadInputSerializer,
    ScanImageUploadSerializer,
    SoilHealthCardCreateSerializer,
    SoilHealthCardSerializer,
    SoilHealthCardUpdateSerializer,
    StartLanguageOnboardingSerializer,
    UserPreferenceSerializer,
    UserProfileUpsertSerializer,
    VoiceAssistantInputSerializer,
)


@api_view(['POST'])
@permission_classes([AllowAny])
def check_phone_number(request):
    """
    Check if phone number exists in database.
    Returns 1 if user exists (login flow) with user data.
    Returns 0 if user doesn't exist (signup flow).
    """
    phone_number = request.data.get('phone_number')
    
    if not phone_number:
        return Response(
            {'detail': 'phone_number is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user_preference = UserPreference.objects.get(phone_number=phone_number)
        # User exists - Login flow
        return Response(
            {
                'status': 1,
                'message': 'User exists. Proceeding to login.',
                'user': UserPreferenceSerializer(user_preference, context={'request': request}).data
            },
            status=status.HTTP_200_OK
        )
    except UserPreference.DoesNotExist:
        # User doesn't exist - Signup flow
        return Response(
            {
                'status': 0,
                'message': 'New user. Proceeding to signup.'
            },
            status=status.HTTP_200_OK
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def complete_signup(request):
    """
    Complete user signup with phone number and preferences.
    Takes: phone_number, preferred_language, voice_assistant_enabled
    """
    phone_number = request.data.get('phone_number')
    preferred_language = request.data.get('preferred_language')
    voice_assistant_enabled = request.data.get('voice_assistant_enabled', False)
    
    if not phone_number:
        return Response(
            {'detail': 'phone_number is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if not preferred_language:
        return Response(
            {'detail': 'preferred_language is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Check if user already exists
        user_preference = UserPreference.objects.get(phone_number=phone_number)
        return Response(
            {'detail': 'User already exists.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except UserPreference.DoesNotExist:
        # Create new user with preferences
        user_preference = UserPreference.objects.create(
            phone_number=phone_number,
            preferred_language=preferred_language,
            voice_assistant_enabled=voice_assistant_enabled
        )
        
        return Response(
            {
                'status': 1,
                'message': 'User created successfully.',
                'user': UserPreferenceSerializer(user_preference, context={'request': request}).data
            },
            status=status.HTTP_201_CREATED
        )


def cleanup_expired_onboarding_sessions():
    LanguageOnboardingSession.objects.filter(expires_at__lt=timezone.now()).delete()


@api_view(['POST'])
@permission_classes([AllowAny])
def start_language_onboarding(request):
    """
    Deprecated: Use check_phone_number and complete_signup instead.
    Kept for backwards compatibility.
    """
    cleanup_expired_onboarding_sessions()

    serializer = StartLanguageOnboardingSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    session = LanguageOnboardingSession.objects.create(
        preferred_language=serializer.validated_data['preferred_language'],
    )
    return Response(LanguageOnboardingSessionSerializer(session).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def save_voice_assistant_preference(request):
    """
    Save voice assistant preference for a user.
    Takes: phone_number, voice_assistant_enabled
    """
    phone_number = request.data.get('phone_number')
    voice_assistant_enabled = request.data.get('voice_assistant_enabled')
    
    if not phone_number:
        return Response(
            {'detail': 'phone_number is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user_preference = UserPreference.objects.get(phone_number=phone_number)
        user_preference.voice_assistant_enabled = voice_assistant_enabled
        user_preference.save(update_fields=['voice_assistant_enabled'])
        
        return Response(
            UserPreferenceSerializer(user_preference, context={'request': request}).data,
            status=status.HTTP_200_OK
        )
    except UserPreference.DoesNotExist:
        return Response(
            {'detail': 'Phone number not found. Register user first.'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def register_phone_number(request):
    """
    Deprecated: Use check_phone_number and complete_signup instead.
    Kept for backwards compatibility.
    Register a new user with phone number and preferences from onboarding session.
    """
    cleanup_expired_onboarding_sessions()

    serializer = PhoneInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    phone_number = serializer.validated_data['phone_number']
    onboarding_token = serializer.validated_data['onboarding_token']

    try:
        session = LanguageOnboardingSession.objects.get(token=onboarding_token)
    except LanguageOnboardingSession.DoesNotExist:
        return Response(
            {'detail': 'Invalid or expired onboarding token.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    user_preference, created = UserPreference.objects.get_or_create(
        phone_number=phone_number,
        defaults={
            'preferred_language': session.preferred_language,
            'voice_assistant_enabled': session.voice_assistant_enabled,
        },
    )

    if not created:
        user_preference.preferred_language = session.preferred_language
        user_preference.voice_assistant_enabled = session.voice_assistant_enabled
        user_preference.save(update_fields=['preferred_language', 'voice_assistant_enabled', 'updated_at'])

    # Remove temporary language record after successful phone registration.
    session.delete()

    response_data = UserPreferenceSerializer(user_preference).data
    response_data['created'] = created
    return Response(response_data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def cancel_onboarding(request):
    """
    Deprecated: Use the new simplified flow instead.
    Kept for backwards compatibility.
    Cancel onboarding and remove temporary session.
    """
    serializer = CancelOnboardingSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    onboarding_token = serializer.validated_data['onboarding_token']
    deleted_count, _ = LanguageOnboardingSession.objects.filter(token=onboarding_token).delete()

    if deleted_count == 0:
        return Response({'detail': 'Session already removed or token invalid.'}, status=status.HTTP_404_NOT_FOUND)

    return Response({'detail': 'Onboarding cancelled and temporary language removed.'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
@parser_classes([MultiPartParser, FormParser])
def upload_scan_image(request):
    serializer = ScanImageUploadInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    phone_number = serializer.validated_data['phone_number']

    try:
        user_preference = UserPreference.objects.get(phone_number=phone_number)
    except UserPreference.DoesNotExist:
        return Response(
            {'detail': 'Phone number not found. Register user first.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    scan_upload = ScanImageUpload.objects.create(
        user_preference=user_preference,
        image=serializer.validated_data['image'],
        source=serializer.validated_data['source'],
        analysis_status='pending',
    )

    response_serializer = ScanImageUploadSerializer(scan_upload, context={'request': request})
    return Response(response_serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([AllowAny])
def list_scan_images(request):
    phone_number = request.query_params.get('phone_number')
    queryset = ScanImageUpload.objects.select_related('user_preference').all()

    if phone_number:
        queryset = queryset.filter(user_preference__phone_number=phone_number)

    response_serializer = ScanImageUploadSerializer(queryset, many=True, context={'request': request})
    return Response(response_serializer.data, status=status.HTTP_200_OK)


@api_view(['POST', 'GET'])
@permission_classes([AllowAny])
def soil_health_cards(request):
    if request.method == 'POST':
        serializer = SoilHealthCardCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data['phone_number']

        try:
            user_preference = UserPreference.objects.get(phone_number=phone_number)
        except UserPreference.DoesNotExist:
            return Response(
                {'detail': 'Phone number not found. Register user first.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        card = SoilHealthCard.objects.create(
            user_preference=user_preference,
            land_name=serializer.validated_data.get('land_name', ''),
            ph=serializer.validated_data['ph'],
            nitrogen=serializer.validated_data['nitrogen'],
            hydrogen=serializer.validated_data['hydrogen'],
            phosphate=serializer.validated_data['phosphate'],
            notes=serializer.validated_data.get('notes', ''),
        )
        response_serializer = SoilHealthCardSerializer(card)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    phone_number = request.query_params.get('phone_number')
    queryset = SoilHealthCard.objects.select_related('user_preference').all()
    if phone_number:
        queryset = queryset.filter(user_preference__phone_number=phone_number)

    response_serializer = SoilHealthCardSerializer(queryset, many=True)
    return Response(response_serializer.data, status=status.HTTP_200_OK)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([AllowAny])
def soil_health_card_detail(request, card_id):
    try:
        card = SoilHealthCard.objects.select_related('user_preference').get(pk=card_id)
    except SoilHealthCard.DoesNotExist:
        return Response({'detail': 'Soil health card not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(SoilHealthCardSerializer(card).data, status=status.HTTP_200_OK)

    if request.method in ['PUT', 'PATCH']:
        partial = request.method == 'PATCH'
        serializer = SoilHealthCardUpdateSerializer(data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        if serializer.validated_data['phone_number'] != card.user_preference.phone_number:
            return Response(
                {'detail': 'Phone number does not match this soil health card.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        for field, value in serializer.validated_data.items():
            if field == 'phone_number':
                continue
            setattr(card, field, value)
        card.save()

        return Response(SoilHealthCardSerializer(card).data, status=status.HTTP_200_OK)

    phone_number = request.data.get('phone_number')
    if not phone_number:
        return Response({'detail': 'phone_number is required for delete.'}, status=status.HTTP_400_BAD_REQUEST)
    if phone_number != card.user_preference.phone_number:
        return Response(
            {'detail': 'Phone number does not match this soil health card.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    card.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST', 'GET'])
@permission_classes([AllowAny])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def question_posts(request):
    if request.method == 'POST':
        serializer = QuestionPostCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data['phone_number']
        try:
            user_preference = UserPreference.objects.get(phone_number=phone_number)
        except UserPreference.DoesNotExist:
            return Response(
                {'detail': 'Phone number not found. Register user first.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        post = QuestionPost.objects.create(
            user_preference=user_preference,
            question_text=serializer.validated_data['question_text'],
            crop_disease=serializer.validated_data['crop_disease'],
            photo=serializer.validated_data.get('photo'),
        )
        response_serializer = QuestionPostSerializer(post, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    crop_disease = request.query_params.get('crop_disease')
    queryset = QuestionPost.objects.select_related('user_preference').all()
    if crop_disease:
        queryset = queryset.filter(crop_disease__icontains=crop_disease)

    response_serializer = QuestionPostSerializer(queryset, many=True, context={'request': request})
    return Response(response_serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def question_post_detail(request, post_id):
    try:
        post = QuestionPost.objects.select_related('user_preference').get(pk=post_id)
    except QuestionPost.DoesNotExist:
        return Response({'detail': 'Question post not found.'}, status=status.HTTP_404_NOT_FOUND)

    return Response(QuestionPostSerializer(post, context={'request': request}).data, status=status.HTTP_200_OK)


@api_view(['POST', 'GET'])
@permission_classes([AllowAny])
def expert_community_posts(request):
    if request.method == 'POST':
        serializer = ExpertCommunityPostCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data['phone_number']
        try:
            user_preference = UserPreference.objects.get(phone_number=phone_number)
        except UserPreference.DoesNotExist:
            return Response(
                {'detail': 'Phone number not found. Register user first.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        post = ExpertCommunityPost.objects.create(
            user_preference=user_preference,
            title=serializer.validated_data['title'],
            message=serializer.validated_data['message'],
            target_region=serializer.validated_data.get('target_region', ''),
        )
        return Response(ExpertCommunityPostSerializer(post).data, status=status.HTTP_201_CREATED)

    target_region = request.query_params.get('target_region')
    queryset = ExpertCommunityPost.objects.select_related('user_preference').all()
    if target_region:
        queryset = queryset.filter(target_region__icontains=target_region)

    return Response(ExpertCommunityPostSerializer(queryset, many=True).data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def expert_community_post_detail(request, post_id):
    try:
        post = ExpertCommunityPost.objects.select_related('user_preference').get(pk=post_id)
    except ExpertCommunityPost.DoesNotExist:
        return Response({'detail': 'Expert post not found.'}, status=status.HTTP_404_NOT_FOUND)

    return Response(ExpertCommunityPostSerializer(post).data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def user_profile_detail(request):
    phone_number = request.query_params.get('phone_number')
    if not phone_number:
        return Response({'detail': 'phone_number query parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user_preference = UserPreference.objects.get(phone_number=phone_number)
    except UserPreference.DoesNotExist:
        return Response({'detail': 'Phone number not found. Register user first.'}, status=status.HTTP_404_NOT_FOUND)

    return Response(UserPreferenceSerializer(user_preference, context={'request': request}).data, status=status.HTTP_200_OK)


@api_view(['POST', 'PATCH'])
@permission_classes([AllowAny])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def upsert_user_profile(request):
    partial = request.method == 'PATCH'
    serializer = UserProfileUpsertSerializer(data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)

    phone_number = serializer.validated_data['phone_number']
    try:
        user_preference = UserPreference.objects.get(phone_number=phone_number)
    except UserPreference.DoesNotExist:
        return Response({'detail': 'Phone number not found. Register user first.'}, status=status.HTTP_404_NOT_FOUND)

    for field in ['full_name', 'location', 'profile_photo', 'preferred_language', 'voice_assistant_enabled']:
        if field in serializer.validated_data:
            setattr(user_preference, field, serializer.validated_data[field])

    user_preference.save()
    return Response(UserPreferenceSerializer(user_preference, context={'request': request}).data, status=status.HTTP_200_OK)