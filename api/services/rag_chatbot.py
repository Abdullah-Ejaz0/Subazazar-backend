import os
import threading
import traceback
import sys
from typing import List, Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from groq import Groq
from langdetect import detect

# --- Constants & Knowledge ---
_RICE_KNOWLEDGE = """
=== RICE DISEASES IN PAKISTAN ===

--- Bacterial Leaf Blight (BLB) ---
Bacterial Leaf Blight (BLB) is caused by Xanthomonas oryzae pv. oryzae.
It is one of the most destructive rice diseases in Punjab and Sindh, Pakistan.
Symptoms: Water-soaked to yellowish stripes on leaf margins, leaves dry out from tip.
Conditions: Hot humid weather above 30°C, waterlogged fields, excess nitrogen.
Spread: Through infected water, rain splash, farm tools.
Immediate action: Remove infected leaves, stop nitrogen fertilizer, improve drainage.
Treatment: Spray Copper Oxychloride 50% WP at 2.5g per liter every 10-14 days.
Also use Streptomycin Sulphate 90% SP at 0.5g per liter, 2 sprays 7 days apart.
Kasugamycin 3% SL at 2mL per liter, spray every 10 days maximum 3 times.
Fertilizer: Reduce nitrogen (Urea), use Potassium Chloride (KCl) 60kg per hectare.
Use Diammonium Phosphate (DAP) 50kg per hectare at basal application only.
Prevention: Use resistant varieties, clean seeds, proper field drainage, avoid excess urea.

--- Brown Spot ---
Brown Spot is caused by Helminthosporium oryzae (fungal disease).
Common in nutrient-deficient soils, especially in Sindh and southern Punjab.
Symptoms: Oval to circular brown spots on leaves with yellow halo, spots on grains too.
Conditions: Low soil fertility, silicon deficiency, drought stress, high humidity.
Treatment: Spray Mancozeb 75% WP at 2g per liter water, repeat after 14 days.
Also use Propiconazole 25% EC at 1mL per liter, 2-3 applications.
Tricyclazole 75% WP at 0.6g per liter is also effective.
Fertilizer: Apply balanced NPK fertilizer. Potassium silicate helps resistance.
Use Silicon-based fertilizers to strengthen cell walls.
Prevention: Use certified disease-free seeds, balanced fertilization, avoid water stress.

--- Leaf Smut ---
Leaf Smut is caused by Entyloma oryzae (fungal disease).
Less severe than BLB but causes quality loss. Found in humid regions of Pakistan.
Symptoms: Small angular black spots on leaves, powdery spore masses.
Treatment: Spray Carbendazim 50% WP at 1g per liter, or Mancozeb 75% WP at 2g per liter.
Prevention: Crop rotation, remove plant debris, use clean seeds treated with fungicide.

=== COMMON PESTICIDES FOR RICE IN PAKISTAN ===

--- Insecticides ---
Chlorpyrifos 40% EC: Controls stem borers, leaf folders. Use 1.5L per hectare.
Imidacloprid 200 SL: Controls brown planthopper (BPH). Use 200mL per hectare.
Lambda-cyhalothrin 2.5% EC: Controls leaf folders and BPH. Use 300mL per hectare.
Fipronil 5% SC: Controls stem borers. Use 1L per hectare.
Cartap Hydrochloride 50% SP: Controls stem borers, leaf folders. Use 1kg per hectare.

--- Common Rice Pests in Pakistan ---
Stem Borer (Scirpophaga): Most damaging pest in Punjab. Causes dead heart and white ear.
Treatment: Chlorpyrifos spray + Carbofuran 3G granules 10kg per hectare at tillering.
Brown Planthopper (BPH): Causes hopper burn. Use Imidacloprid or Buprofezin.
Leaf Folder: Rolls leaves into tubes. Use Lambda-cyhalothrin or Chlorpyrifos.
Rice Hispa: Scrapes leaf surface. Use Malathion 57% EC at 1L per hectare.

=== FERTILIZERS FOR RICE IN PAKISTAN ===

--- General NPK Schedule ---
Basal (Before transplanting): DAP 100kg/ha + SOP or MOP 50kg/ha
1st Top Dress (21-25 days after transplant): Urea 65kg/ha
2nd Top Dress (45 days after transplant): Urea 65kg/ha
Total Nitrogen: 120kg N per hectare for high-yield varieties.

--- Recommended Varieties in Pakistan ---
Basmati 515: Popular in Punjab, aromatic, disease tolerant.
Super Basmati: Export quality, but susceptible to BLB.
IRRI-6: High yield, tolerant to many diseases, common in Sindh.
KSK-282: Resistant to BLB, suitable for Punjab.
PK-386: Suitable for Sindh conditions.

--- Soil Preparation ---
Plow 2-3 times to 20cm depth. Level field for uniform irrigation.
Apply Farm Yard Manure (FYM) 5-10 tons per hectare before final plowing.
Soil pH should be 5.5 to 7.0 for best rice growth.

=== IRRIGATION MANAGEMENT ===
Maintain 5-7cm water depth during vegetative stage.
Use Alternate Wetting and Drying (AWD) to save water and reduce BLB risk.
Stop irrigation 10 days before harvest.
Avoid waterlogging as it promotes bacterial diseases.

=== PLANTING SEASON IN PAKISTAN ===
Nursery sowing: Late May to mid-June (Punjab), May-June (Sindh).
Transplanting: Late June to mid-July when seedlings are 25-30 days old.
Harvesting: October to November when 80% grains are mature.

=== ROMAN URDU COMMON TERMS ===
Chawal ki fasal = Rice crop
Bimari = Disease
Keeray = Insects/Pests
Khad = Fertilizer
Spray = Pesticide spray
Paani = Water
Zameen = Soil/Land
Mosam = Weather
Paidawar = Yield/Production
Bijli wali machine = Electric pump
Khal = Canal
Boring = Tube well
"""

_VECTORSTORE = None
_VECTORSTORE_LOCK = threading.Lock()

# --- Helper Functions ---

def _detect_language(text):
    print(f"DEBUG: Detecting language for: {text[:50]}...", flush=True)
    roman_urdu_words = [
        'kya', 'hai', 'hain', 'nahi', 'karo', 'mera', 'meri',
        'chawal', 'fasal', 'bimari', 'khad', 'keeray', 'acha',
        'batao', 'kaise', 'kyun', 'kab', 'kahan', 'kitna'
    ]
    text_lower = text.lower()
    roman_hits = sum(1 for w in roman_urdu_words if w in text_lower)
    if roman_hits >= 2:
        print("DEBUG: Language detected as Roman Urdu (Manual)", flush=True)
        return 'roman_urdu'
    try:
        lang = detect(text)
        print(f"DEBUG: Language detected as {lang} (langdetect)", flush=True)
        if lang == 'ur':
            return 'urdu'
    except Exception as e:
        print(f"DEBUG: Language detection failed: {e}", flush=True)
    return 'english'

def _load_faq_text():
    return ""

def _build_knowledge_base():
    faq_text = _load_faq_text()
    if faq_text:
        return f"{_RICE_KNOWLEDGE}\n\n{faq_text}"
    return _RICE_KNOWLEDGE

def _load_vectorstore(path, embeddings):
    if not path or not os.path.isdir(path):
        return None
    try:
        vs = FAISS.load_local(path, embeddings, allow_dangerous_deserialization=True)
        return vs
    except Exception as e:
        return None

def _get_vectorstore():
    global _VECTORSTORE
    if _VECTORSTORE is not None:
        return _VECTORSTORE

    with _VECTORSTORE_LOCK:
        if _VECTORSTORE is not None:
            return _VECTORSTORE

        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
        )
        
        vectorstore_path = os.getenv("RAG_VECTORSTORE_PATH", "rice_vectorstore").strip()
        vectorstore = _load_vectorstore(vectorstore_path, embeddings)
        
        if vectorstore is None:
            knowledge = _build_knowledge_base()
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=500,
                chunk_overlap=100,
                separators=["\n\n", "\n", "---", "===", ". "]
            )
            chunks = text_splitter.create_documents([knowledge])
            vectorstore = FAISS.from_documents(chunks, embeddings)
            vectorstore.save_local(vectorstore_path)
            
        _VECTORSTORE = vectorstore
        return _VECTORSTORE

def get_rag_response(user_question, chat_history=None):
    
    api_key = os.getenv("GROQ_API_KEY", "").strip()

    history = chat_history or []
    lang = _detect_language(user_question)

    try:
        vs = _get_vectorstore()
        retriever = vs.as_retriever(search_kwargs={"k": 4})
        docs = retriever.invoke(user_question)
        
        context = "\n\n".join([doc.page_content for doc in docs])

        if lang == 'roman_urdu':
            lang_instruction = (
                "The farmer is asking in Roman Urdu. "
                "Reply in simple Roman Urdu. Example: 'Aap ki fasal mein BLB bimari hai. Copper spray karein.'"
            )
        elif lang == 'urdu':
            lang_instruction = "Reply in Urdu script."
        else:
            lang_instruction = "Reply in clear, simple English suitable for farmers."

        system_prompt = f"""You are an expert agricultural assistant for Pakistani rice farmers.
You specialize in rice crop diseases, pesticides, fertilizers, irrigation, and farming practices
specifically for Pakistan's Punjab and Sindh regions.

{lang_instruction}

Use ONLY the context provided below to answer. If the answer is not in the context, say you don't
have that specific information but give general safe advice.

Keep answers practical and actionable. Mention specific product names, dosages, and timing when available.
Always remind farmers to consult their local Agriculture Extension Officer for serious issues.

CONTEXT FROM KNOWLEDGE BASE:
{context}
"""
        print(f"DEBUG: System Prompt constructed (Length: {len(system_prompt)})", flush=True)

        messages = [{"role": "system", "content": system_prompt}]
        for entry in history[-6:]:
            if isinstance(entry, dict) and "role" in entry and "content" in entry:
                messages.append({"role": entry["role"], "content": entry["content"]})
            elif isinstance(entry, (list, tuple)) and len(entry) == 2:
                if entry[0]:
                    messages.append({"role": "user", "content": entry[0]})
                if entry[1]:
                    messages.append({"role": "assistant", "content": entry[1]})

        messages.append({"role": "user", "content": user_question})

        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.3,
            max_tokens=800,
        )
        return {
            "answer": response.choices[0].message.content,
            "language": lang
        }
    except Exception as e:
        traceback.print_exc()
        raise e
