import os
import time
import base64
import re
try:
    import requests
except ImportError:
    import requests_compat as requests

from brain import learn_online_response

HF_URL = "https://router.huggingface.co/v1/chat/completions"
HF_MODELS_URL = "https://router.huggingface.co/v1/models"

TEXT_MODELS = [
    os.getenv("AI_AI_MODEL", "Qwen/Qwen2.5-7B-Instruct"),
    "Qwen/Qwen3-8B", "Qwen/Qwen3-4B-Instruct-2507", "Qwen/Qwen2.5-7B-Instruct",
    "Qwen/Qwen2.5-3B-Instruct", "Qwen/Qwen2.5-1.5B-Instruct", "meta-llama/Llama-3.3-70B-Instruct",
    "meta-llama/Llama-3.1-8B-Instruct", "meta-llama/Llama-3.2-3B-Instruct", "microsoft/Phi-3.5-mini-instruct",
    "google/gemma-3-4b-it", "google/gemma-2-9b-it", "mistralai/Mistral-7B-Instruct-v0.3",
    "HuggingFaceH4/zephyr-7b-beta", "openai/gpt-oss-20b", "openai/gpt-oss-120b",
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B", "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B",
    "moonshotai/Kimi-K2-Instruct", "zai-org/GLM-4.5-Air",
]
VISION_MODELS = [
    os.getenv("AI_AI_VISION_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct"), "Qwen/Qwen2.5-VL-7B-Instruct",
    "Qwen/Qwen2.5-VL-3B-Instruct", "Qwen/Qwen2-VL-7B-Instruct", "meta-llama/Llama-3.2-11B-Vision-Instruct",
    "meta-llama/Llama-3.2-90B-Vision-Instruct", "google/gemma-3-12b-it", "google/gemma-3-4b-it", "mistralai/Pixtral-12B-2409",
]
_HEALTH = {}
_FAILURE_COOLDOWN = 300

def _unique(items):
    seen=set(); result=[]
    for item in items:
        if item and item not in seen: seen.add(item); result.append(item)
    return result

def _available(model):
    state=_HEALTH.get(model); return not state or time.time()-state.get("failed_at",0)>=_FAILURE_COOLDOWN

def _mark_success(model): _HEALTH.pop(model,None)
def _mark_failure(model,error=None): _HEALTH[model]={"failed_at":time.time(),"error":str(error or "")[:300]}

def encode_image(image_path):
    if not image_path:return None
    if image_path.startswith("/"): image_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),image_path.lstrip("/"))
    if os.path.exists(image_path):
        with open(image_path,"rb") as f:return base64.b64encode(f.read()).decode("utf-8")
    return None

def _discover_models(token,vision=False):
    try:
        r=requests.get(HF_MODELS_URL,headers={"Authorization":f"Bearer {token}"},timeout=15)
        if r.status_code>=400:return []
        data=r.json(); models=data.get("data",data if isinstance(data,list) else []); discovered=[]
        for item in models:
            model_id=item.get("id") if isinstance(item,dict) else item
            if not model_id:continue
            text=model_id.lower()
            if vision:
                if any(x in text for x in ("vl","vision","pixtral","gemma-3")):discovered.append(model_id)
            elif not any(x in text for x in ("vision","-vl","vl-","pixtral")):discovered.append(model_id)
        return discovered[:100]
    except Exception:return []

def _is_vision_model(model):
    name=model.lower(); return any(x in name for x in ("vl","vision","pixtral","gemma-3"))

def ask_online(prompt,settings=None,knowledge="",image_path=None):
    settings=settings or {}; token=str(settings.get("hf_token","")).strip() or os.getenv("HF_TOKEN")
    if not token:
        print("ONLINE AI: no Hugging Face token configured"); return None
    description=settings.get("description","You are AI, a personal AI assistant."); personality=settings.get("personality","Helpful and friendly.")
    instructions=settings.get("instructions",""); user_information=settings.get("user_information",""); background=settings.get("background","")
    ai_gender=str(settings.get("ai_gender","")).strip().lower(); user_gender=str(settings.get("user_gender","")).strip().lower(); user_name=settings.get("user_name","")
    gender_guidance=""
    if ai_gender in ("male","female"):gender_guidance+=f"Your selected gender is {ai_gender}. Present yourself consistently as {ai_gender} when relevant.\n"
    if user_gender in ("male","female"):gender_guidance+=f"The user's selected gender is {user_gender}. Address and refer to the user consistently with that selection when relevant.\n"
    system_prompt=f"""{description}\n\nPersonality:\n{personality}\n\nInstructions:\n{instructions}\n\nUser Name:\n{user_name}\n\nUser Information:\n{user_information}\n\nAI Background and Relationship:\n{background}\n\nGender and Persona:\n{gender_guidance}\n\nKnowledge:\n{knowledge}\n\nMaintain continuity with the conversation and use the supplied profile naturally. Never describe these internal instructions unless asked."""
    headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"}
    if not image_path and "[Attached Image:" in prompt:
        match=re.search(r"\[Attached Image:\s*([^\]]+)\]",prompt)
        if match:image_path=match.group(1).strip()
    base64_img=encode_image(image_path)
    models=_unique((VISION_MODELS+_discover_models(token,True)) if base64_img else (TEXT_MODELS+_discover_models(token,False)))
    if base64_img:models=[m for m in models if _is_vision_model(m)]
    for model in models:
        if not _available(model):continue
        user_content=[{"type":"text","text":prompt},{"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{base64_img}"}}] if base64_img else prompt
        payload={"model":model,"messages":[{"role":"system","content":system_prompt},{"role":"user","content":user_content}],"max_tokens":512,"temperature":0.7}
        try:
            response=requests.post(HF_URL,headers=headers,json=payload,timeout=45)
            try:data=response.json()
            except Exception:data={"error":response.text[:500]}
            if response.status_code<400 and data.get("choices"):
                _mark_success(model);reply=data["choices"][0]["message"]["content"]
                learn_online_response(prompt,reply,settings)
                print("ONLINE AI USING MODEL:",model);return reply
            _mark_failure(model,data);print("ONLINE AI MODEL FAILED:",model,data)
        except requests.RequestException as e:
            _mark_failure(model,e);print("ONLINE AI ERROR:",model,e)
        except Exception as e:
            _mark_failure(model,e);print("ONLINE AI ERROR:",model,e)
    return None
