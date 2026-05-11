from rest_framework import serializers

from .models import (
    ExpertCommunityPost,
    LanguageOnboardingSession,
    QuestionPost,
    ScanImageUpload,
    SoilHealthCard,
    UserPreference,
)


class StartLanguageOnboardingSerializer(serializers.Serializer):
    preferred_language = serializers.CharField(max_length=30)


class VoiceAssistantInputSerializer(serializers.Serializer):
    onboarding_token = serializers.UUIDField()
    voice_assistant_enabled = serializers.BooleanField()


class LanguageOnboardingSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = LanguageOnboardingSession
        fields = ['token', 'preferred_language', 'voice_assistant_enabled', 'created_at', 'expires_at']
        read_only_fields = fields


class PhoneInputSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=25)
    onboarding_token = serializers.UUIDField()


class CancelOnboardingSerializer(serializers.Serializer):
    onboarding_token = serializers.UUIDField()


class UserPreferenceSerializer(serializers.ModelSerializer):
    profile_photo_url = serializers.SerializerMethodField()

    class Meta:
        model = UserPreference
        fields = [
            'id',
            'phone_number',
            'full_name',
            'location',
            'profile_photo',
            'profile_photo_url',
            'preferred_language',
            'voice_assistant_enabled',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_profile_photo_url(self, obj):
        if not obj.profile_photo:
            return None
        request = self.context.get('request')
        if request is None:
            return obj.profile_photo.url
        return request.build_absolute_uri(obj.profile_photo.url)


class UserProfileUpsertSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=25)
    full_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    location = serializers.CharField(max_length=120, required=False, allow_blank=True)
    profile_photo = serializers.ImageField(required=False, allow_null=True)
    preferred_language = serializers.CharField(max_length=30, required=False, allow_blank=True)
    voice_assistant_enabled = serializers.BooleanField(required=False)


class ScanImageUploadInputSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=25)
    image = serializers.ImageField()
    source = serializers.ChoiceField(choices=ScanImageUpload.ImageSource.choices)


class ScanImageUploadSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(source='user_preference.phone_number', read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ScanImageUpload
        fields = [
            'id',
            'phone_number',
            'source',
            'analysis_status',
            'analysis_result',
            'image',
            'image_url',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_image_url(self, obj):
        request = self.context.get('request')
        if request is None:
            return obj.image.url
        return request.build_absolute_uri(obj.image.url)


class SoilHealthCardCreateSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=25)
    land_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    ph = serializers.FloatField(min_value=0, max_value=14)
    nitrogen = serializers.FloatField(min_value=0)
    hydrogen = serializers.FloatField(min_value=0)
    phosphate = serializers.FloatField(min_value=0)
    notes = serializers.CharField(required=False, allow_blank=True)


class SoilHealthCardUpdateSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=25)
    land_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    ph = serializers.FloatField(min_value=0, max_value=14, required=False)
    nitrogen = serializers.FloatField(min_value=0, required=False)
    hydrogen = serializers.FloatField(min_value=0, required=False)
    phosphate = serializers.FloatField(min_value=0, required=False)
    notes = serializers.CharField(required=False, allow_blank=True)


class SoilHealthCardSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(source='user_preference.phone_number', read_only=True)

    class Meta:
        model = SoilHealthCard
        fields = [
            'id',
            'phone_number',
            'land_name',
            'ph',
            'nitrogen',
            'hydrogen',
            'phosphate',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class QuestionPostCreateSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=25)
    question_text = serializers.CharField()
    crop_disease = serializers.CharField(max_length=120)
    photo = serializers.ImageField(required=False, allow_null=True)


class QuestionPostSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(source='user_preference.phone_number', read_only=True)
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = QuestionPost
        fields = [
            'id',
            'phone_number',
            'question_text',
            'crop_disease',
            'photo',
            'photo_url',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_photo_url(self, obj):
        if not obj.photo:
            return None
        request = self.context.get('request')
        if request is None:
            return obj.photo.url
        return request.build_absolute_uri(obj.photo.url)


class ExpertCommunityPostCreateSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=25)
    title = serializers.CharField(max_length=200)
    message = serializers.CharField()
    target_region = serializers.CharField(max_length=120, required=False, allow_blank=True)


class ExpertCommunityPostSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(source='user_preference.phone_number', read_only=True)

    class Meta:
        model = ExpertCommunityPost
        fields = [
            'id',
            'phone_number',
            'title',
            'message',
            'target_region',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields
