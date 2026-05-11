import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework import serializers
from rest_framework.decorators import api_view
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)

from api.middleware.auth import require_auth
from api.supabase_client import supabase
from api.services.rag_chatbot import get_rag_response


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="Authorization",
            type=str,
            location=OpenApiParameter.HEADER,
            required=True,
            description="Bearer <supabase_jwt>",
        )
    ],
    request=inline_serializer(
        name="ChatbotAskRequest",
        fields={
            "question": serializers.CharField(),
            "history": serializers.ListField(
                child=serializers.DictField(),
                required=False,
                help_text="Optional chat history list of {role, content} entries.",
            ),
        },
    ),
    responses={
        200: OpenApiResponse(
            response=inline_serializer(
                name="ChatbotAskResponse",
                fields={
                    "answer": serializers.CharField(),
                    "language": serializers.CharField(),
                },
            ),
            description="RAG chatbot response.",
        )
    },
)
@csrf_exempt
@api_view(["POST"])
@require_auth
@require_http_methods(["POST"])
def ask_chatbot(request):
    print("\nDEBUG: ask_chatbot view called!", flush=True)
    """
    POST /api/chatbot/ask/
    Body: { "question": "...", "history": [{"role": "user", "content": "..."}] }
    Returns the chatbot answer plus the detected language.
    """
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    question = body.get("question", "").strip()
    if not question:
        return JsonResponse({"error": "question is required"}, status=400)

    history = body.get("history") or []

    try:
        result = get_rag_response(question, history)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)

    try:
        supabase.from_("chatbot").insert(
            {
                "user_id": request.user_id,
                "question": question,
                "answer": result["answer"],
                "language": result["language"],
            }
        ).execute()
    except Exception:
        pass

    return JsonResponse(result)


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="Authorization",
            type=str,
            location=OpenApiParameter.HEADER,
            required=True,
            description="Bearer <supabase_jwt>",
        ),
        OpenApiParameter(
            name="limit",
            type=int,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Maximum items to return (default 20).",
        ),
        OpenApiParameter(
            name="offset",
            type=int,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Pagination offset (default 0).",
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=inline_serializer(
                name="ChatbotHistoryResponse",
                fields={
                    "id": serializers.CharField(),
                    "question": serializers.CharField(),
                    "answer": serializers.CharField(),
                    "language": serializers.CharField(),
                    "created_at": serializers.DateTimeField(),
                },
            ),
            description="Chatbot history items for the authenticated user.",
        )
    },
)
@api_view(["GET"])
@require_auth
@require_http_methods(["GET"])
def chatbot_history(request):
    """
    GET /api/chatbot/history/?limit=20&offset=0
    Returns the authenticated user's chatbot history (newest first).
    """
    limit = int(request.GET.get("limit", 20))
    offset = int(request.GET.get("offset", 0))

    result = (
        supabase
        .from_("chatbot")
        .select("id,question,answer,language,created_at")
        .eq("user_id", request.user_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return JsonResponse(result.data, safe=False)
