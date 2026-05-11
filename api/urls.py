# from django.urls import path
# from api.views import (
#     scan_views, community_views, soil_views,
#     expert_views, auth_views, misc_views
# )

# from .views import (
#     cancel_onboarding,
#     check_phone_number,
#     complete_signup,
#     expert_community_post_detail,
#     expert_community_posts,
#     list_scan_images,
#     question_post_detail,
#     question_posts,
#     register_phone_number,
#     save_voice_assistant_preference,
#     soil_health_card_detail,
#     soil_health_cards,
#     start_language_onboarding,
#     upsert_user_profile,
#     user_profile_detail,
#     upload_scan_image,
# )

# urlpatterns = [
#     # New simplified auth flow
#     path('users/check-phone/', check_phone_number),
#     path('users/complete-signup/', complete_signup),
#     # Auth and profile
#     path('auth/onboarding/',             auth_views.complete_onboarding),
#     path('auth/settings/',               auth_views.update_settings),
#     path('auth/profile/',                auth_views.get_profile),

#     # Scans
#     path('scans/recent/',                scan_views.recent_scans),
#     path('scans/<str:scan_id>/',         scan_views.scan_detail),
#     path('scans/',                       scan_views.save_scan),

#     # Soil health
#     path('soil/latest/',                 soil_views.latest_soil),
#     path('soil/',                        soil_views.save_soil),

#     # Community
#     path('community/',                   community_views.community_feed),
#     path('community/post/',              community_views.submit_post),
#     path('community/<str:post_id>/replies/', community_views.submit_reply),
#     path('community/<str:post_id>/',     community_views.post_detail),

#     # Expert portal
#     path('expert/dashboard/',            expert_views.dashboard_stats),
#     path('expert/pending/',              expert_views.pending_questions),
#     path('expert/broadcast/',            expert_views.send_broadcast),

#     # Misc
#     path('chatbot/faqs/',                misc_views.chatbot_faqs),
#     path('broadcasts/',                  misc_views.broadcasts),
#     path('storage/upload-url/',          misc_views.get_upload_url),
#     path('weather/',                     misc_views.weather),

#     # Health check
#     path('health/',                      misc_views.health_check),
# ]



from django.urls import path
from api.views import (
    scan_views, community_views, soil_views,
    expert_views, auth_views, misc_views,
    disease_views, chatbot_views
)

urlpatterns = [
    # ── Farmer Auth (phone-based) ──────────────────────────────
    path('auth/check-phone/',            auth_views.check_phone),
    path('auth/farmer/signup/',          auth_views.farmer_signup),

    # ── Expert Auth (email + password) ─────────────────────────
    path('auth/expert/signup/',          auth_views.expert_signup),
    path('auth/expert/login/',           auth_views.expert_login),

    # ── Onboarding & Settings ──────────────────────────────────
    path('auth/onboarding/',             auth_views.complete_onboarding),
    path('auth/settings/',               auth_views.update_settings),

    # ── Profile (view, patch, update) ──────────────────────────
    path('auth/profile/',                auth_views.get_profile),
    path('auth/profile/update/',         auth_views.update_profile),

    # ── Scans ──────────────────────────────────────────────────
    path('scans/recent/',                scan_views.recent_scans),
    path('scans/detect/',                disease_views.detect_rice_disease),
    path('scans/<str:scan_id>/',         scan_views.scan_detail),
    path('scans/',                       scan_views.save_scan),

    # ── Soil health ────────────────────────────────────────────
    path('soil/latest/',                 soil_views.latest_soil),
    path('soil/',                        soil_views.save_soil),
    path('soil/parse/',                  soil_views.parse_soil_report),
    path('soil/parse/save/',             soil_views.parse_soil_report_save),

    # ── Community ──────────────────────────────────────────────
    path('community/',                   community_views.community_feed),
    path('community/post/',              community_views.submit_post),
    path('community/upload-photo/',      community_views.upload_photo),
    path('community/my-history/',        community_views.user_history),
    path('community/<str:post_id>/replies/', community_views.submit_reply),
    path('community/<str:post_id>/',     community_views.post_detail),

    # ── Expert portal ──────────────────────────────────────────
    path('expert/dashboard/stats/',      expert_views.dashboard_stats),
    path('expert/pending/',              expert_views.pending_questions),
    path('expert/broadcast/',            expert_views.send_broadcast),

    # ── Misc ───────────────────────────────────────────────────
    path('chatbot/faqs/',                misc_views.chatbot_faqs),
    path('chatbot/ask/',                 chatbot_views.ask_chatbot),
    path('chatbot/history/',             chatbot_views.chatbot_history),
    path('broadcasts/',                  misc_views.broadcasts),
    path('storage/upload-url/',          misc_views.get_upload_url),
    path('weather/',                     misc_views.weather),

    # ── Health check ───────────────────────────────────────────
    path('health/',                      misc_views.health_check),
]