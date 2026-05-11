from django.urls import path
from .views import (
    cancel_onboarding,
    check_phone_number,
    complete_signup,
    expert_community_post_detail,
    expert_community_posts,
    list_scan_images,
    question_post_detail,
    question_posts,
    register_phone_number,
    save_voice_assistant_preference,
    soil_health_card_detail,
    soil_health_cards,
    start_language_onboarding,
    upsert_user_profile,
    user_profile_detail,
    upload_scan_image,
)

urlpatterns = [
    # New simplified auth flow
    path('users/check-phone/', check_phone_number),
    path('users/complete-signup/', complete_signup),
    
    # Legacy endpoints (deprecated but kept for backwards compatibility)
    path('users/start-language/', start_language_onboarding),
    path('users/set-voice-assistant/', save_voice_assistant_preference),
    path('users/register-phone/', register_phone_number),
    path('users/profile/', user_profile_detail),
    path('users/profile/upsert/', upsert_user_profile),
    path('users/cancel-onboarding/', cancel_onboarding),
    path('scan/upload-image/', upload_scan_image),
    path('scan/images/', list_scan_images),
    path('soil-health/cards/', soil_health_cards),
    path('soil-health/cards/<int:card_id>/', soil_health_card_detail),
    path('community/questions/', question_posts),
    path('community/questions/<int:post_id>/', question_post_detail),
    path('community/expert-posts/', expert_community_posts),
    path('community/expert-posts/<int:post_id>/', expert_community_post_detail),
]