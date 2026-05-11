import io
import os
import uuid
from dataclasses import dataclass

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework import serializers
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import FormParser, MultiPartParser
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from drf_spectacular.openapi import AutoSchema

from api.middleware.auth import require_auth
from api.supabase_client import supabase_admin


CLASS_NAMES = ["bacterial_leaf_blight", "brown_spot", "leaf_smut"]


DISEASE_KNOWLEDGE = {
    "bacterial_leaf_blight": {
        "display_name": "Bacterial Leaf Blight",
        "pathogen": "Xanthomonas oryzae pv. oryzae (Xoo)",
        "fertilizer": {
            "recommendation": "Reduce or avoid nitrogen fertilizer during infection. Use a balanced K-rich fertilizer.",
            "chemicals": [
                {"name": "Potassium Chloride (KCl)", "dosage": "60 kg/ha", "frequency": "Once at tillering stage"},
                {"name": "Diammonium Phosphate (DAP)", "dosage": "50 kg/ha", "frequency": "Basal application only"},
            ],
            "note": "Excess nitrogen promotes bacterial spread. Maintain field drainage.",
        },
        "pesticide": {
            "recommendation": "Use copper-based bactericides and streptomycin-based antibiotics.",
            "chemicals": [
                {"name": "Copper Oxychloride 50% WP", "dosage": "2.5 g/L water", "frequency": "Every 10-14 days, 2-3 applications"},
                {"name": "Streptomycin Sulphate 90% SP", "dosage": "0.5 g/L water", "frequency": "2 sprays, 7 days apart"},
                {"name": "Kasugamycin 3% SL", "dosage": "2 mL/L water", "frequency": "At 10-day intervals, max 3 times"},
            ],
        },
    },
    "brown_spot": {
        "display_name": "Brown Spot",
        "pathogen": "Bipolaris oryzae (Helminthosporium oryzae)",
        "fertilizer": {
            "recommendation": "Correct silicon and potassium deficiencies. Apply manganese if soil tests show deficiency.",
            "chemicals": [
                {"name": "Urea (46% N)", "dosage": "40-60 kg/ha", "frequency": "Split: basal + tillering"},
                {"name": "Single Super Phosphate (SSP)", "dosage": "30 kg/ha", "frequency": "Basal before transplanting"},
                {"name": "Potassium Sulphate (K2SO4)", "dosage": "40 kg/ha", "frequency": "Once at tillering stage"},
                {"name": "Silicon Fertilizer", "dosage": "100-200 kg/ha", "frequency": "Basal application"},
            ],
            "note": "Brown spot thrives in nutrient-deficient soils. Soil testing recommended.",
        },
        "pesticide": {
            "recommendation": "Apply systemic fungicides at booting to heading stage for best results.",
            "chemicals": [
                {"name": "Mancozeb 75% WP", "dosage": "2.5 g/L water", "frequency": "Every 10 days, 2-3 times"},
                {"name": "Tricyclazole 75% WP", "dosage": "0.6 g/L water", "frequency": "1-2 sprays at early symptoms"},
                {"name": "Iprobenfos (IBP) 48% EC", "dosage": "1.5 mL/L water", "frequency": "Booting stage, repeat after 14 days"},
            ],
        },
    },
    "leaf_smut": {
        "display_name": "Leaf Smut",
        "pathogen": "Entyloma oryzae",
        "fertilizer": {
            "recommendation": "Reduce nitrogen to moderate levels. Ensure adequate phosphorus and potassium balance.",
            "chemicals": [
                {"name": "NPK Fertilizer (10:26:26)", "dosage": "50 kg/ha", "frequency": "Basal at transplanting"},
                {"name": "Potassium Chloride (KCl)", "dosage": "40 kg/ha", "frequency": "Top-dress at tillering"},
            ],
            "note": "Leaf smut is favored by high humidity. Avoid over-irrigation.",
        },
        "pesticide": {
            "recommendation": "Fungicide seed treatment is most effective. Foliar sprays help reduce spread.",
            "chemicals": [
                {"name": "Propiconazole 25% EC", "dosage": "1 mL/L water", "frequency": "2 sprays, 14 days apart"},
                {"name": "Hexaconazole 5% SC", "dosage": "2 mL/L water", "frequency": "At first symptoms"},
                {"name": "Carbendazim 50% WP", "dosage": "1 g/L water", "frequency": "Seed treatment: 2 g/kg seed"},
            ],
        },
    },
}


@dataclass
class ModelBundle:
    model: object
    device: object
    preprocess: object


_MODEL_BUNDLE = None


def _load_model_bundle():
    global _MODEL_BUNDLE
    if _MODEL_BUNDLE is not None:
        return _MODEL_BUNDLE

    try:
        import torch
        import torch.nn as nn
        from torchvision import models, transforms
    except Exception as exc:  # pragma: no cover - import-time error
        raise RuntimeError(f"Model dependencies are missing: {exc}")

    model_path = os.getenv("RICE_DISEASE_MODEL_PATH", "").strip()
    if not model_path:
        raise RuntimeError("RICE_DISEASE_MODEL_PATH is not set")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model = models.efficientnet_b0(weights=None)
    model.classifier = nn.Sequential(
        nn.Dropout(p=0.3),
        nn.Linear(model.classifier[1].in_features, len(CLASS_NAMES)),
    )
    model.load_state_dict(torch.load(model_path, map_location=device))
    model = model.to(device)
    model.eval()

    preprocess = transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ]
    )

    _MODEL_BUNDLE = ModelBundle(model=model, device=device, preprocess=preprocess)
    return _MODEL_BUNDLE


def _maybe_remove_background(image):
    try:
        from rembg import remove
    except BaseException:   # rembg calls sys.exit(1) when onnxruntime is missing;
        return image        # SystemExit is BaseException, not Exception

    img_bytes = io.BytesIO()
    image.save(img_bytes, format="PNG")
    img_no_bg = remove(img_bytes.getvalue())
    from PIL import Image

    return Image.open(io.BytesIO(img_no_bg)).convert("RGBA")


def _prepare_image(file_bytes):
    from PIL import Image

    image = Image.open(io.BytesIO(file_bytes)).convert("RGBA")
    image = _maybe_remove_background(image)

    bbox = image.getbbox()
    image = image.crop(bbox) if bbox else image
    image = image.convert("RGB")
    image = image.resize((224, 224))
    return image


def _risk_level_from_confidence(confidence):
    if confidence >= 80:
        return "high"
    if confidence >= 60:
        return "medium"
    return "low"


def _build_recommendations(disease_key):
    info = DISEASE_KNOWLEDGE.get(disease_key)
    if not info:
        return {}

    return {
        "display_name": info["display_name"],
        "pathogen": info["pathogen"],
        "fertilizer": info["fertilizer"],
        "pesticide": info["pesticide"],
        "disclaimer": "Always consult your local agriculture officer before use.",
    }


def _get_llm_disease_explanation(disease_label, confidence):
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        from groq import Groq
    except Exception:
        return None

    disease_name = disease_label.replace("_", " ").title()
    info = DISEASE_KNOWLEDGE.get(disease_label, {})
    pathogen = info.get("pathogen", "unknown pathogen")

    prompt = f"""You are an expert agricultural plant pathologist specializing in rice crop diseases.

A rice leaf image has been analyzed by an AI model and the following disease has been detected:

- Disease: {disease_name}
- Causative Agent: {pathogen}
- Model Confidence: {confidence:.1f}%
- Crop: Rice (Oryza sativa)

Provide a simple disease advisory report with sections:
1) Disease description and causes
2) Symptoms (early vs severe)
3) Immediate actions
4) Prevention tips

Keep the language clear for rice farmers in South and Southeast Asia."""

    groq_client = Groq(api_key=api_key)
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are an expert agricultural plant pathologist."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=1200,
    )
    return response.choices[0].message.content


@extend_schema(
    request={
        "multipart/form-data": {
            "type": "object",
            "properties": {
                "image":     {"type": "string", "format": "binary", "description": "Rice leaf image (JPEG/PNG)"},
                "crop_name": {"type": "string", "default": "Rice"},
                "use_llm":   {"type": "boolean", "default": True},
                "notes":     {"type": "string", "default": ""},
            },
            "required": ["image"],
        }
    },
    responses={
        200: OpenApiResponse(
            response=inline_serializer(
                name="RiceDiseaseDetectResponse",
                fields={
                    "scan_id": serializers.CharField(),
                    "image_path": serializers.CharField(),
                    "crop_name": serializers.CharField(),
                    "disease_key": serializers.CharField(),
                    "disease_name": serializers.CharField(),
                    "confidence": serializers.FloatField(),
                    "risk_level": serializers.CharField(),
                    "class_probabilities": serializers.DictField(child=serializers.FloatField()),
                    "recommendations": serializers.DictField(),
                    "llm_report": serializers.CharField(allow_null=True),
                },
            ),
            description="Disease prediction with recommendations.",
        )
    },
)
@csrf_exempt
@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser])
@require_auth
@require_http_methods(["POST"])
def detect_rice_disease(request):
    image = request.FILES.get("image")
    if not image:
        return JsonResponse({"error": "image file is required"}, status=400)

    crop_name = request.POST.get("crop_name", "Rice")
    use_llm = request.POST.get("use_llm", "true").lower() in {"true", "1", "yes"}
    notes = request.POST.get("notes", "")

    try:
        file_bytes = image.read()
    except Exception:
        return JsonResponse({"error": "Unable to read image"}, status=400)

    try:
        bundle = _load_model_bundle()
        from PIL import Image
        import torch
        import torch.nn.functional as F

        processed = _prepare_image(file_bytes)
        tensor = bundle.preprocess(processed).unsqueeze(0).to(bundle.device)

        with torch.no_grad():
            outputs = bundle.model(tensor)
            probabilities = F.softmax(outputs, dim=1)[0]

        probs = {name: float(probabilities[idx].item() * 100) for idx, name in enumerate(CLASS_NAMES)}
        predicted_idx = int(probabilities.argmax().item())
    except BaseException as exc:   # catches SystemExit from rembg as well as regular errors
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": f"Inference failed: {exc}", "traceback": traceback.format_exc()}, status=500)

    predicted_key = CLASS_NAMES[predicted_idx]
    confidence = probs[predicted_key]
    
    # Threshold check: if confidence is too low, it's likely not a leaf or the photo is too blurry
    if confidence < 40.0:
        disease_name = "Healthy or Inconclusive"
        risk_level = "low"
        llm_report = "We couldn't clearly identify any rice disease in this photo. Please ensure the leaf is in focus and well-lit, then try again."
        recommendations = {
            "display_name": "No Disease Detected",
            "pathogen": "None",
            "fertilizer": {"recommendation": "Continue your regular fertilizer schedule.", "chemicals": [], "note": ""},
            "pesticide": {"recommendation": "No pesticide needed at this time.", "chemicals": []},
            "disclaimer": "This is an automated scan. If you see symptoms, please consult an expert."
        }
    else:
        disease_name = predicted_key.replace("_", " ").title()
        risk_level = _risk_level_from_confidence(confidence)
        llm_report = _get_llm_disease_explanation(predicted_key, confidence) if use_llm else None
        recommendations = _build_recommendations(predicted_key)

    image_ext = os.path.splitext(image.name)[1] or ".jpg"
    object_name = f"{request.user_id}/{uuid.uuid4().hex}{image_ext}"
    content_type = image.content_type or "image/jpeg"

    try:
        upload_result = supabase_admin.storage.from_("scan-images").upload(
            object_name,
            file_bytes,
            {"content-type": content_type, "upsert": "false"},
        )
        if getattr(upload_result, "error", None):
            return JsonResponse({"error": f"Upload failed: {upload_result.error}"}, status=502)
    except Exception as exc:
        return JsonResponse({"error": f"Upload failed: {exc}"}, status=502)

    ai_raw = {
        "class_probabilities": probs,
        "device": str(getattr(bundle.device, "type", bundle.device)),
        "notes": notes,
    }

    try:
        scan_result = supabase_admin.rpc(
            "save_scan_result",
            {
                "p_user_id": request.user_id,
                "p_image_url": object_name,
                "p_crop_name": crop_name,
                "p_disease_name": disease_name,
                "p_confidence": confidence,
                "p_risk_level": risk_level,
                "p_ai_raw": ai_raw,
            },
        ).execute()
        scan_id = scan_result.data
    except Exception as exc:
        return JsonResponse({"error": f"Database save failed: {exc}"}, status=502)

    return JsonResponse(
        {
            "scan_id": scan_id,
            "image_path": object_name,
            "crop_name": crop_name,
            "disease_key": predicted_key,
            "disease_name": disease_name,
            "confidence": confidence,
            "risk_level": risk_level,
            "class_probabilities": probs,
            "recommendations": recommendations,
            "llm_report": llm_report,
        }
    )
