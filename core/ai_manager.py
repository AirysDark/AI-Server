"""AI registry, per-AI paths, settings and direct conversation archive helpers."""
import os, shutil, time, uuid, glob
from core.auth import clean_id, current_user, cookie
from core.config import AIS_FILE, MAX_AIS_PER_ACCOUNT, USERS_DIR
from core.storage import load_json, save_json

def get_ai_registry(): return load_json(AIS_FILE,{"accounts":{}})
def account_root(uid): return os.path.join(USERS_DIR,clean_id(uid))
def ais_root(uid): return os.path.join(account_root(uid),"ais")
def ai_root(uid,ai_id): return os.path.join(ais_root(uid),clean_id(ai_id))
def settings_file(uid,ai_id): return os.path.join(ai_root(uid,ai_id),"settings.json")
def conversations_root(uid,ai_id): return os.path.join(ai_root(uid,ai_id),"conversations")
def conversation_path(uid,ai_id,conversation_id): return os.path.join(conversations_root(uid,ai_id),clean_id(conversation_id)+".json")
def ai_photo_dir(uid,ai_id): return os.path.join(ai_root(uid,ai_id),"ai_photos")
def legacy_conversation_file(uid,ai_id): return os.path.join(ai_root(uid,ai_id),"conversation.json")

def _payload(value):
    if not isinstance(value,dict): return None
    if isinstance(value.get("data"),dict): value=value["data"]
    if not isinstance(value.get("conversation"),list): return None
    value.setdefault("memory",{}); value.setdefault("proactive_state",{})
    return value

def load_archived_conversation(uid,ai_id,conversation_id):
    safe=clean_id(conversation_id)
    if not safe or safe=="current": return None
    path=conversation_path(uid,ai_id,safe)
    if not os.path.isfile(path): return None
    return _payload(load_json(path,None))

def save_archived_conversation(uid,ai_id,conversation_id,data):
    safe=clean_id(conversation_id)
    if not safe or safe=="current": raise ValueError("Invalid conversation id")
    os.makedirs(conversations_root(uid,ai_id),exist_ok=True)
    save_json(conversation_path(uid,ai_id,safe),data)
    return data

def ensure_archived_conversation(uid,ai_id,conversation_id=None):
    """Return a valid per-AI conversation id and payload, creating it if missing/stale."""
    safe=clean_id(conversation_id)
    if not safe or safe=="current" or load_archived_conversation(uid,ai_id,safe) is None:
        safe="C-"+uuid.uuid4().hex[:16]
        now=time.time()
        save_archived_conversation(uid,ai_id,safe,{"conversation":[],"memory":{},"proactive_state":{},"created":now,"updated":now})
    return safe,load_archived_conversation(uid,ai_id,safe)

def blank_settings(uid,ai_id):
    return {"user_id":uid,"ai_id":ai_id,"setup_complete":False,"ai_name":"","profile_photo":"","description":"","background":"","user_information":"","user_name":"","personality":"","instructions":"","api_provider":"huggingface","api_token":"","hf_token":"","google_token":"","openai_token":"","openrouter_token":"","gemini_api_key":"","api_endpoint":"","api_model":"","local_model_path":"","config":{"traits":[],"rules":[]},"features":{"online_ai":True,"learning":True,"long_term_memory":True,"relevant_memory":True,"automatic_images":False,"proactive_images":False},"proactive":{"enabled":False}}
def load_settings(uid,ai_id):
    data=load_json(settings_file(uid,ai_id),blank_settings(uid,ai_id)); return data if isinstance(data,dict) else blank_settings(uid,ai_id)
def save_settings(uid,ai_id,data): os.makedirs(ai_root(uid,ai_id),exist_ok=True); save_json(settings_file(uid,ai_id),data)

def _latest_archive(uid,ai_id):
    root=conversations_root(uid,ai_id)
    if not os.path.isdir(root): return None
    candidates=[]
    for path in glob.glob(os.path.join(root,"*.json")):
        if os.path.basename(path)=="current.json": continue
        try:
            raw=load_json(path,None); data=_payload(raw)
            if data and data.get("conversation"): candidates.append((float(data.get("updated",0) or 0),os.path.getmtime(path),data))
        except Exception: pass
    if not candidates:return None
    candidates.sort(key=lambda x:(x[0],x[1]),reverse=True); return candidates[0][2]

def load_conversation(uid,ai_id):
    """Legacy compatibility only; does not create or read current.json."""
    archived=_latest_archive(uid,ai_id)
    if archived is not None:return archived
    legacy=legacy_conversation_file(uid,ai_id)
    if os.path.isfile(legacy):return _payload(load_json(legacy,{"conversation":[],"memory":{},"proactive_state":{}})) or {"conversation":[],"memory":{},"proactive_state":{}}
    return {"conversation":[],"memory":{},"proactive_state":{}}

def save_conversation_data(uid,ai_id,data):
    raise RuntimeError("Direct chat persistence requires a conversation_id")

def migrate_legacy_ai(uid):
    reg=get_ai_registry(); account=reg.setdefault("accounts",{}).setdefault(uid,{"ais":[],"active_ai":None})
    if account.get("ais"):return account["ais"][0]["ai_id"]
    old_settings=os.path.join(account_root(uid),"settings.json"); old_conversation=os.path.join(USERS_DIR,uid+".json")
    if not os.path.exists(old_settings) and not os.path.exists(old_conversation):return None
    ai_id="AI1-"+uuid.uuid4().hex[:12]; os.makedirs(ai_root(uid,ai_id),exist_ok=True); settings=load_json(old_settings,blank_settings(uid,ai_id)); settings["user_id"]=uid; settings["ai_id"]=ai_id; save_settings(uid,ai_id,settings)
    if os.path.exists(old_conversation):
        cid="C-"+uuid.uuid4().hex[:16]; save_archived_conversation(uid,ai_id,cid,_payload(load_json(old_conversation,{})) or {"conversation":[]})
    account["ais"]=[{"ai_id":ai_id,"created":time.time()}]; account["active_ai"]=ai_id; save_json(AIS_FILE,reg); return ai_id

def ensure_first_ai(uid):
    reg=get_ai_registry(); account=reg.setdefault("accounts",{}).setdefault(uid,{"ais":[],"active_ai":None})
    if not account.get("ais"):
        migrated=migrate_legacy_ai(uid)
        if migrated:return migrated
        return create_ai(uid)
    return account.get("active_ai") or account["ais"][0]["ai_id"]
def list_ais(uid):
    ensure_first_ai(uid); account=get_ai_registry()["accounts"][uid]; out=[]
    for item in account.get("ais",[]):
        ai_id=item["ai_id"]; s=load_settings(uid,ai_id); out.append({"ai_id":ai_id,"ai_name":s.get("ai_name") or "Unnamed AI","profile_photo":s.get("profile_photo",""),"setup_complete":bool(s.get("setup_complete")),"created":item.get("created"),"active":ai_id==account.get("active_ai")})
    return out

def active_ai(handler):
    uid=current_user(handler)
    if not uid:return None,None
    account=get_ai_registry().get("accounts",{}).get(uid,{})
    valid={x.get("ai_id") for x in account.get("ais",[])}; selected=clean_id(cookie(handler,"AI_active"))
    if selected in valid:return uid,selected
    ai_id=account.get("active_ai")
    return uid,ai_id if ai_id in valid else (account.get("ais") or [{}])[0].get("ai_id")
def set_active(uid,ai_id):
    reg=get_ai_registry(); account=reg.setdefault("accounts",{}).setdefault(uid,{"ais":[],"active_ai":None})
    if ai_id not in {x["ai_id"] for x in account.get("ais",[])}:return False
    account["active_ai"]=ai_id; save_json(AIS_FILE,reg); return True
def create_ai(uid):
    reg=get_ai_registry(); account=reg.setdefault("accounts",{}).setdefault(uid,{"ais":[],"active_ai":None})
    if len(account.get("ais",[]))>=MAX_AIS_PER_ACCOUNT:return None
    ai_id=f"AI{len(account.get('ais',[]))+1}-"+uuid.uuid4().hex[:12]; os.makedirs(ai_root(uid,ai_id),exist_ok=True); save_settings(uid,ai_id,blank_settings(uid,ai_id)); account["ais"].append({"ai_id":ai_id,"created":time.time()}); account["active_ai"]=ai_id; save_json(AIS_FILE,reg); return ai_id
def delete_ai(uid,ai_id):
    reg=get_ai_registry(); account=reg.get("accounts",{}).get(uid)
    if not account or ai_id not in {x["ai_id"] for x in account.get("ais",[])} or len(account["ais"])<=1:return False
    account["ais"]=[x for x in account["ais"] if x["ai_id"]!=ai_id]
    if account.get("active_ai")==ai_id:account["active_ai"]=account["ais"][0]["ai_id"]
    shutil.rmtree(ai_root(uid,ai_id),ignore_errors=True); save_json(AIS_FILE,reg); return True