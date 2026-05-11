from django.contrib import admin
from .models import (
	ExpertCommunityPost,
	LanguageOnboardingSession,
	QuestionPost,
	ScanImageUpload,
	SoilHealthCard,
	UserPreference,
)


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
	list_display = ('id', 'phone_number', 'full_name', 'location', 'preferred_language', 'voice_assistant_enabled', 'created_at', 'updated_at')
	search_fields = ('phone_number', 'full_name', 'location', 'preferred_language')


@admin.register(LanguageOnboardingSession)
class LanguageOnboardingSessionAdmin(admin.ModelAdmin):
	list_display = ('token', 'preferred_language', 'voice_assistant_enabled', 'created_at', 'expires_at')
	search_fields = ('preferred_language',)


@admin.register(ScanImageUpload)
class ScanImageUploadAdmin(admin.ModelAdmin):
	list_display = ('id', 'user_preference', 'source', 'analysis_status', 'created_at')
	list_filter = ('source', 'analysis_status', 'created_at')
	search_fields = ('user_preference__phone_number',)


@admin.register(SoilHealthCard)
class SoilHealthCardAdmin(admin.ModelAdmin):
	list_display = ('id', 'user_preference', 'land_name', 'ph', 'nitrogen', 'hydrogen', 'phosphate', 'created_at')
	search_fields = ('user_preference__phone_number', 'land_name')
	list_filter = ('created_at',)


@admin.register(QuestionPost)
class QuestionPostAdmin(admin.ModelAdmin):
	list_display = ('id', 'user_preference', 'crop_disease', 'created_at')
	search_fields = ('user_preference__phone_number', 'crop_disease', 'question_text')
	list_filter = ('created_at',)


@admin.register(ExpertCommunityPost)
class ExpertCommunityPostAdmin(admin.ModelAdmin):
	list_display = ('id', 'user_preference', 'title', 'target_region', 'created_at')
	search_fields = ('user_preference__phone_number', 'title', 'message', 'target_region')
	list_filter = ('created_at',)
