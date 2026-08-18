from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import json, os, uuid, re, random, time, hashlib, hmac, secrets, shutil, socket, struct, threading, atexit
from urllib.parse import urlparse, parse_qs
from email.parser import BytesParser
from email.policy import default
from brain import think, learn_from_conversation
from online_ai import ask_online

PORT = 47823
PUBLIC_HOSTNAME = "ai-server.ddns.net"
PUBLIC_URL = f"http://{PUBLIC_HOSTNAME}:{PORT}/"
MDNS_HOSTNAME = "ai-server.ddns.net"
RECENT_CONTEXT_MESSAGES = 10
RELEVANT_MEMORY_LIMIT = 10
PROACTIVE_MIN_MINUTES = 10
PROACTIVE_MAX_MINUTES = 30
MAX_AIS_PER_ACCOUNT = 3
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_DIR = os.path.join(BASE_DIR, "users")
AUTH_FILE = os.path.join(BASE_DIR, "accounts.json")
SESSIONS_FILE = os.path.join(BASE_DIR, "sessions.json")
AIS_FILE = os.path.join(BASE_DIR, "ais.json")
os.makedirs(USERS_DIR, exist_ok=True)

_mdns_socket = None
_mdns_stop = threading.Event()
_mdns_thread = None

def _lan_ip():
    s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8",80)); return s.getsockname()[0]
    except Exception:
        try:return socket.gethostbyname(socket.gethostname())
        except Exception:return "127.0.0.1"
    finally:s.close()

def _dns_name(name): return b"".join(bytes([len(p)])+p.encode() for p in name.rstrip(".").split("."))+b"\0"
def _dns_question_name(data,offset):
    labels=[]; jumped=False; next_offset=offset
    while offset<len(data):
        length=data[offset]; offset+=1
        if length==0:
            if not jumped:next_offset=offset
            break
        if (length&0xC0)==0xC0:
            if offset>=len(data):break
            pointer=((length&0x3F)<<8)|data[offset]; offset+=1
            if not jumped:next_offset=offset
            offset=pointer; jumped=True; continue
        if offset+length>len(data):break
        labels.append(data[offset:offset+length].decode("utf-8","ignore")); offset+=length
    return ".".join(labels).lower(),next_offset

def _mdns_response(ip,query_id=0):
    host="ai-server.ddns.net"; service="_http._tcp.local"; instance="ai-server._http._tcp.local"; instance_name=_dns_name(instance); host_name=_dns_name(host); service_name=_dns_name(service)
    packet=struct.pack("!HHHHHH",query_id,0x8400,4,0,0,0)
    packet+=host_name+struct.pack("!HHIH",1,0x8001,120,4)+socket.inet_aton(ip)
    srv_data=struct.pack("!HHH",0,0,PORT)+_dns_name(_lan_hostname())
    packet+=instance_name+struct.pack("!HHIH",33,0x8001,120,len(srv_data))+srv_data
    txt=b"".join(bytes([len(x)])+x for x in (b"path=/",b"server=AI")); packet+=instance_name+struct.pack("!HHIH",16,0x8000,120,len(txt))+txt
    packet+=service_name+struct.pack("!HHIH",12,0x8000,120,len(instance_name))+instance_name; return packet

def _lan_hostname(): return "LOCAL-AI.local"
def _send_mdns(sock,packet):sock.sendto(packet,("224.0.0.251",5353))
def _mdns_loop():
    global _mdns_socket
    ip=_lan_ip()
    if ip=="127.0.0.1":print("mDNS: no LAN IPv4 address found; not advertising");return
    try:
        sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP);sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        try:sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEPORT,1)
        except (AttributeError,OSError):pass
        sock.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_TTL,255);sock.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_LOOP,1);sock.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_IF,socket.inet_aton(ip))
        try:sock.bind(("0.0.0.0",5353))
        except OSError:sock.bind((ip,5353))
        sock.setsockopt(socket.IPPROTO_IP,socket.IP_ADD_MEMBERSHIP,socket.inet_aton("224.0.0.251")+socket.inet_aton(ip));sock.settimeout(1.0);_mdns_socket=sock
        print(f"mDNS: public URL {PUBLIC_URL}");print(f"mDNS: LAN address http://{ip}:{PORT}/");print("mDNS: listening on UDP 5353")
        announcement=_mdns_response(ip,0);last=0
        while not _mdns_stop.is_set():
            now=time.time()
            if now-last>=10:
                try:_send_mdns(sock,announcement);last=now
                except OSError as exc:print("mDNS announcement error:",exc)
            try:
                data,addr=sock.recvfrom(9000)
                if len(data)<12:continue
                query_id,flags,qdcount=struct.unpack("!HHH",data[:6])
                if flags&0x8000 or qdcount==0:continue
                offset=12;matched=False
                for _ in range(qdcount):
                    name,offset=_dns_question_name(data,offset)
                    if offset+4>len(data):break
                    qtype,qclass=struct.unpack("!HH",data[offset:offset+4]);offset+=4
                    if name in ("ai-server.ddns.net","_http._tcp.local","ai-server._http._tcp.local") or qtype==255:matched=True
                if matched:_send_mdns(sock,_mdns_response(ip,query_id))
            except socket.timeout:pass
            except OSError:
                if not _mdns_stop.is_set():print("mDNS socket closed unexpectedly")
                break
            except Exception as exc:print("mDNS query error:",exc)
    except Exception as exc:print("mDNS startup error:",exc)
    finally:
        try:
            if _mdns_socket:_mdns_socket.close()
        except Exception:pass
        _mdns_socket=None

def start_mdns():
    global _mdns_thread
    if _mdns_thread and _mdns_thread.is_alive():return
    _mdns_stop.clear();_mdns_thread=threading.Thread(target=_mdns_loop,name="AI-server-mDNS",daemon=True);_mdns_thread.start()
def stop_mdns():
    _mdns_stop.set();global _mdns_socket
    if _mdns_socket:
        try:_mdns_socket.close()
        except Exception:pass
atexit.register(stop_mdns)

def load_json(path,default):
    try:
        with open(path,"r",encoding="utf-8") as f:return json.load(f)
    except Exception:return default
def save_json(path,data):
    os.makedirs(os.path.dirname(path) or ".",exist_ok=True);tmp=path+".tmp"
    with open(tmp,"w",encoding="utf-8") as f:json.dump(data,f,indent=4,ensure_ascii=False)
    os.replace(tmp,path)
def clean_id(uid):return re.sub(r"[^A-Za-z0-9_-]","",str(uid or ""))[:100]
def normalize_email(x):return str(x or "").strip().lower()
def valid_email(x):return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",x))
def hash_password(password):
    salt=secrets.token_hex(16);digest=hashlib.pbkdf2_hmac("sha256",password.encode(),salt.encode(),210000).hex();return salt+":"+digest
def verify_password(password,stored):
    try:
        salt,digest=stored.split(":",1);check=hashlib.pbkdf2_hmac("sha256",password.encode(),salt.encode(),210000).hex();return hmac.compare_digest(check,digest)
    except Exception:return False
def get_accounts():return load_json(AUTH_FILE,{"users":{}})
def get_sessions():return load_json(SESSIONS_FILE,{})
def get_ai_registry():return load_json(AIS_FILE,{"accounts":{}})
def cookie(handler,name):
    for part in handler.headers.get("Cookie","").split(";"):
        part=part.strip()
        if part.startswith(name+"="):return part.split("=",1)[1]
    return ""
def create_session(uid):
    token=secrets.token_urlsafe(48);data=get_sessions();data[token]={"user_id":uid,"created":time.time()};save_json(SESSIONS_FILE,data);return token
def current_user(handler):return clean_id(get_sessions().get(cookie(handler,"AI_session"),{}).get("user_id")) or None
def account_root(uid):return os.path.join(USERS_DIR,clean_id(uid))
def ais_root(uid):return os.path.join(account_root(uid),"ais")
def ai_root(uid,ai_id):return os.path.join(ais_root(uid),clean_id(ai_id))
def settings_file(uid,ai_id):return os.path.join(ai_root(uid,ai_id),"settings.json")
def conversation_file(uid,ai_id):return os.path.join(ai_root(uid,ai_id),"conversation.json")
def ai_photo_dir(uid,ai_id):return os.path.join(ai_root(uid,ai_id),"ai_photos")
def upload_dir(uid,ai_id):return os.path.join(ai_root(uid,ai_id),"uploads")
def blank_settings(uid,ai_id):return {"user_id":uid,"ai_id":ai_id,"setup_complete":False,"ai_name":"","profile_photo":"","description":"","background":"","user_information":"","user_name":"","personality":"","instructions":"","config":{"traits":[],"rules":[]},"features":{"online_ai":True,"learning":True,"long_term_memory":True,"relevant_memory":True,"automatic_images":False,"proactive_images":False},"proactive":{"enabled":False}}
def load_settings(uid,ai_id):
    data=load_json(settings_file(uid,ai_id),blank_settings(uid,ai_id))
    if not isinstance(data,dict):data=blank_settings(uid,ai_id)
    data["user_id"]=uid;data["ai_id"]=ai_id;data.setdefault("setup_complete",False);data.setdefault("user_name","");return data
def save_settings(uid,ai_id,data):
    data=dict(data or {});data["user_id"]=uid;data["ai_id"]=ai_id;data["setup_complete"]=True;save_json(settings_file(uid,ai_id),data)
def load_conversation(uid,ai_id):return load_json(conversation_file(uid,ai_id),{"conversation":[],"memory":{},"proactive_state":{}})
def save_conversation_data(uid,ai_id,data):save_json(conversation_file(uid,ai_id),data)
def migrate_legacy_ai(uid):
    reg=get_ai_registry();account=reg.setdefault("accounts",{}).setdefault(uid,{"ais":[],"active_ai":None})
    if account.get("ais"):return account["ais"][0]["ai_id"]
    old_settings=os.path.join(account_root(uid),"settings.json");old_conversation=os.path.join(USERS_DIR,uid+".json")
    if not os.path.exists(old_settings) and not os.path.exists(old_conversation):return None
    ai_id="AI1-"+uuid.uuid4().hex[:12];os.makedirs(ai_root(uid,ai_id),exist_ok=True);settings=load_json(old_settings,blank_settings(uid,ai_id));settings["user_id"]=uid;settings["ai_id"]=ai_id;save_json(settings_file(uid,ai_id),settings)
    if os.path.exists(old_conversation):save_conversation_data(uid,ai_id,load_json(old_conversation,{"conversation":[],"memory":{},"proactive_state":{}}))
    account["ais"]=[{"ai_id":ai_id,"created":time.time()}];account["active_ai"]=ai_id;save_json(AIS_FILE,reg);return ai_id
def ensure_first_ai(uid):
    reg=get_ai_registry();account=reg.setdefault("accounts",{}).setdefault(uid,{"ais":[],"active_ai":None})
    if not account.get("ais"):
        migrated=migrate_legacy_ai(uid)
        if migrated:return migrated
        ai_id="AI1-"+uuid.uuid4().hex[:12];os.makedirs(ai_root(uid,ai_id),exist_ok=True);save_json(settings_file(uid,ai_id),blank_settings(uid,ai_id));account["ais"]=[{"ai_id":ai_id,"created":time.time()}];account["active_ai"]=ai_id;save_json(AIS_FILE,reg)
    return account.get("active_ai") or account["ais"][0]["ai_id"]
def list_ais(uid):
    ensure_first_ai(uid);reg=get_ai_registry();account=reg["accounts"][uid];result=[]
    for item in account.get("ais",[]):
        ai_id=item["ai_id"];s=load_settings(uid,ai_id);result.append({"ai_id":ai_id,"ai_name":s.get("ai_name") or "Unnamed AI","profile_photo":s.get("profile_photo",""),"setup_complete":bool(s.get("setup_complete")),"created":item.get("created"),"active":ai_id==account.get("active_ai")})
    return result
def active_ai(handler):
    uid=current_user(handler)
    if not uid:return None,None
    ensure_first_ai(uid);reg=get_ai_registry();account=reg["accounts"][uid];valid={x["ai_id"] for x in account.get("ais",[])};ai_id=clean_id(cookie(handler,"AI_active"))
    if ai_id not in valid:ai_id=account.get("active_ai")
    if ai_id not in valid:ai_id=next(iter(valid))
    account["active_ai"]=ai_id;save_json(AIS_FILE,reg);return uid,ai_id
def set_active(uid,ai_id):
    reg=get_ai_registry();account=reg.setdefault("accounts",{}).setdefault(uid,{"ais":[],"active_ai":None})
    if ai_id not in {x["ai_id"] for x in account.get("ais",[])}:return False
    account["active_ai"]=ai_id;save_json(AIS_FILE,reg);return True
def create_ai(uid):
    reg=get_ai_registry();account=reg.setdefault("accounts",{}).setdefault(uid,{"ais":[],"active_ai":None})
    if len(account.get("ais",[]))>=MAX_AIS_PER_ACCOUNT:return None
    ai_id=f"AI{len(account.get('ais',[]))+1}-"+uuid.uuid4().hex[:12];os.makedirs(ai_root(uid,ai_id),exist_ok=True);save_json(settings_file(uid,ai_id),blank_settings(uid,ai_id));account["ais"].append({"ai_id":ai_id,"created":time.time()});account["active_ai"]=ai_id;save_json(AIS_FILE,reg);return ai_id
def delete_ai(uid,ai_id):
    reg=get_ai_registry();account=reg.get("accounts",{}).get(uid)
    if not account or ai_id not in {x["ai_id"] for x in account.get("ais",[])} or len(account["ais"])<=1:return False
    account["ais"]=[x for x in account["ais"] if x["ai_id"]!=ai_id]
    if account.get("active_ai")==ai_id:account["active_ai"]=account["ais"][0]["ai_id"]
    save_json(AIS_FILE,reg);shutil.rmtree(ai_root(uid,ai_id),ignore_errors=True);return True
def features(s):
    f=s.get("features",{});return {"online_ai":f.get("online_ai",True),"learning":f.get("learning",True),"long_term_memory":f.get("long_term_memory",True),"relevant_memory":f.get("relevant_memory",True),"automatic_images":f.get("automatic_images",False),"proactive_images":f.get("proactive_images",False)}
def random_image(uid,ai_id):
    d=ai_photo_dir(uid,ai_id);os.makedirs(d,exist_ok=True);files=[x for x in os.listdir(d) if x.lower().endswith((".jpg",".jpeg",".png",".webp",".gif"))];return f"/users/{uid}/ais/{ai_id}/ai_photos/{random.choice(files)}" if files else None
def clean_reply(x):
    if not isinstance(x,str):return x
    for s in ("[Sends a photo]","[Sends a playful photo","[Shows image]","[Uploads image]"):x=x.replace(s,"")
    return x.strip()
def ai_profile(profile,message,s):
    fs=features(s);conv=profile.get("conversation",[]);recent=conv[-RECENT_CONTEXT_MESSAGES:];result=dict(profile)
    if not fs["long_term_memory"]:result["conversation"]=recent;return result
    relevant=[]
    if fs["relevant_memory"] and len(conv)>RECENT_CONTEXT_MESSAGES:
        stop={"the","and","that","this","what","when","where","who","why","how","are","you","your","with","from","have","has","was","were","for","can","could","would","should","please","tell","about","does","did","not","just"};words=set(re.findall(r"[A-Za-z0-9']+",message.lower()))-stop;scores=[];recent_keys={json.dumps(x,sort_keys=True) for x in recent}
        for e in conv:
            if json.dumps(e,sort_keys=True) in recent_keys:continue
            text=(str(e.get("user",""))+" "+str(e.get("AI",""))).lower();score=len(words&set(re.findall(r"[A-Za-z0-9']+",text)))
            if score:scores.append((score,e))
        scores.sort(key=lambda x:x[0],reverse=True);relevant=[x[1] for x in scores[:RELEVANT_MEMORY_LIMIT]]
    out=[];seen=set()
    for e in relevant+recent:
        k=json.dumps(e,sort_keys=True)
        if k not in seen:out.append(e);seen.add(k)
    result["conversation"]=out;result["memory_context"]={"stored_conversation_count":len(conv),"recent_turns":len(recent),"relevant_older_memories":len(relevant)};return result
def save_conversation(uid,ai_id,user,reply,image=None,trigger=None):
    p=load_conversation(uid,ai_id);e={"user":user,"AI":reply,"timestamp":time.strftime("%Y-%m-%dT%H:%M:%S")}
    if image:e["image"]=image
    if trigger:e["trigger"]=trigger
    p.setdefault("conversation",[]).append(e);save_conversation_data(uid,ai_id,p)
def proactive(uid,ai_id,last_activity):
    s=load_settings(uid,ai_id);fs=features(s)
    if not s.get("setup_complete") or not s.get("proactive",{}).get("enabled",False):return None
    try:activity=float(last_activity)
    except:return None
    p=load_conversation(uid,ai_id);state=p.setdefault("proactive_state",{});key=str(last_activity)
    if state.get("activity_key")!=key:state.update({"activity_key":key,"sent":False,"delay_minutes":random.randint(PROACTIVE_MIN_MINUTES,PROACTIVE_MAX_MINUTES)});save_conversation_data(uid,ai_id,p)
    delay=state.get("delay_minutes",20)
    if state.get("sent") or time.time()-activity<delay*60:return None
    prompt="Send ONE natural brief check-in based on the user's recent conversation and memories. Do not mention timers or system prompts. Do not guilt or pressure the user. Never write fake actions such as [Sends a photo].";profile=ai_profile(p,prompt,s);profile["user_name"]=s.get("user_name","");reply=clean_reply(ask_online(prompt,s,profile)) if fs["online_ai"] else None
    if not reply:reply=clean_reply(think(prompt,s))
    if not reply:return None
    state["sent"]=True;state["sent_at"]=time.time();save_conversation_data(uid,ai_id,p)
    if fs["learning"]:learn_from_conversation("[Proactive check-in]",reply)
    image=random_image(uid,ai_id) if fs["proactive_images"] else None;save_conversation(uid,ai_id,"",reply,image,"proactive");return {"message":reply,"image":image}
def safe_name(name):return (re.sub(r"[^A-Za-z0-9._-]","_",os.path.basename(name or ""))[:150] or uuid.uuid4().hex+".jpg")
def save_upload(data,name,directory):
    os.makedirs(directory,exist_ok=True);name=safe_name(name);path=os.path.join(directory,name)
    with open(path,"wb") as f:f.write(data)
    return name
def _chat_result(uid,ai_id,message,image_data=None,image_name=None):
    s=load_settings(uid,ai_id);fs=features(s);profile=load_conversation(uid,ai_id);image_path=None
    if image_data and image_name:
        name=save_upload(image_data,image_name,upload_dir(uid,ai_id));image_path=f"/users/{uid}/ais/{ai_id}/uploads/{name}"
    prompt=str(message or "").strip()
    if image_path:prompt=(prompt+" " if prompt else "")+f"[Attached Image: {image_path}]"
    scoped_memory=os.path.join(ai_root(uid,ai_id),"brain_memory.json");scoped_learning=os.path.join(ai_root(uid,ai_id),"learning_replies.json");context=ai_profile(profile,prompt,s)
    reply=clean_reply(ask_online(prompt,s,context,image_path=image_path)) if fs["online_ai"] else None
    if not reply:reply=clean_reply(think(prompt,s,scoped_memory,scoped_learning))
    if not reply:reply="I couldn't get an AI response right now."
    low=prompt.lower();send_image=False
    if fs["automatic_images"] and any(k in low for k in ("send a photo","send me a photo","send a picture","send me a picture","show me a photo","show me a picture")):send_image=True
    if "[Attached Image:" not in prompt and any(k in low for k in ("photo","picture","image")) and fs["automatic_images"]:send_image=True
    if send_image and not image_path:image_path=random_image(uid,ai_id)
    if fs["learning"]:learn_from_conversation(prompt,reply,scoped_memory)
    save_conversation(uid,ai_id,message or "",reply,image_path);return {"reply":reply,"user_id":uid,"ai_id":ai_id,"image":image_path}

class AIHandler(SimpleHTTPRequestHandler):
    def send_auth(self,token):self.send_header("Set-Cookie",f"AI_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000")
    def send_active_cookie(self,ai_id):self.send_header("Set-Cookie",f"AI_active={ai_id}; Path=/; SameSite=Lax; Max-Age=31536000")
    def send_json(self,data,uid=None,status=200,ai_id=None,session_token=None):
        out=json.dumps(data,ensure_ascii=False).encode();self.send_response(status);self.send_header("Content-Type","application/json")
        if uid:self.send_header("Set-Cookie",f"AI_user={uid}; Path=/; Max-Age=31536000; SameSite=Lax")
        if ai_id:self.send_active_cookie(ai_id)
        if session_token:self.send_auth(session_token)
        self.send_header("Content-Length",str(len(out)));self.end_headers();self.wfile.write(out)
    def auth_required(self):
        uid=current_user(self)
        if not uid:self.send_json({"ok":False,"error":"Authentication required"},None,401);return None
        return uid
    def do_GET(self):
        path=urlparse(self.path).path;q=parse_qs(urlparse(self.path).query)
        if path=="/api/health":return self.send_json({"ok":True,"server":"AI","host":PUBLIC_HOSTNAME,"port":PORT,"url":PUBLIC_URL,"lan_ip":_lan_ip()},None,200)
        if path=="/api/proactive":
            uid,ai_id=active_ai(self)
            if not uid:return self.send_json({"ok":False,"error":"Authentication required"},None,401)
            result=proactive(uid,ai_id,q.get("last_activity",[0])[0]);return self.send_json(result or {"message":None},uid,200,ai_id)
        if path=="/api/auth/me":
            uid=current_user(self)
            if not uid:return self.send_json({"authenticated":False})
            a=get_accounts().get("users",{}).get(uid,{});return self.send_json({"authenticated":True,"user_id":uid,"email":a.get("email"),"username":a.get("username"),"max_ais":MAX_AIS_PER_ACCOUNT,"ais":list_ais(uid)})
        if path=="/api/settings":
            uid,ai_id=active_ai(self)
            if not uid:return self.send_json({"error":"Authentication required"},None,401)
            return self.send_json(load_settings(uid,ai_id),uid,200,ai_id)
        if path=="/api/user":
            uid,ai_id=active_ai(self)
            if not uid:return self.send_json({"error":"Authentication required"},None,401)
            return self.send_json(load_conversation(uid,ai_id),uid,200,ai_id)
        if path=="/api/ais":
            uid=self.auth_required()
            if uid:return self.send_json({"ais":list_ais(uid),"max":MAX_AIS_PER_ACCOUNT},uid)
        super().do_GET()
    def do_POST(self):
        try:
            path=urlparse(self.path).path;content_type=self.headers.get("Content-Type","")
            if path=="/chat":
                uid,ai_id=active_ai(self)
                if not uid:return self.send_json({"error":"Authentication required"},None,401)
                length=int(self.headers.get("Content-Length",0))
                if "multipart/form-data" in content_type:
                    raw=self.rfile.read(length);parsed=BytesParser(policy=default).parsebytes((f"Content-Type: {content_type}\r\n\r\n").encode()+raw);fields={};image_data=None;image_name=None
                    if parsed.is_multipart():
                        for part in parsed.iter_parts():
                            cd=part.get("Content-Disposition","");nm=re.search(r'name="([^"]+)"',cd);fn=re.search(r'filename="([^"]*)"',cd)
                            if not nm:continue
                            if fn:image_name=fn.group(1);image_data=part.get_payload(decode=True)
                            else:fields[nm.group(1)]=part.get_content()
                    result=_chat_result(uid,ai_id,fields.get("message",""),image_data,image_name)
                else:
                    data=json.loads(self.rfile.read(length).decode("utf-8"));result=_chat_result(uid,ai_id,data.get("message",""))
                return self.send_json(result,uid,200,ai_id)
            if path=="/api/profile_photo" or path=="/api/ai_photo":
                uid,ai_id=active_ai(self)
                if not uid:return self.send_json({"error":"Authentication required"},None,401)
                length=int(self.headers.get("Content-Length",0));raw=self.rfile.read(length);parsed=BytesParser(policy=default).parsebytes((f"Content-Type: {content_type}\r\n\r\n").encode()+raw);file_data=None;file_name=None
                if parsed.is_multipart():
                    for part in parsed.iter_parts():
                        cd=part.get("Content-Disposition","")
                        if 'name="file"' in cd:
                            m=re.search(r'filename="([^"]*)"',cd);file_name=m.group(1) if m else None;file_data=part.get_payload(decode=True);break
                if not file_data:return self.send_json({"error":"No image uploaded"},uid,400,ai_id)
                if path=="/api/profile_photo":
                    name=save_upload(file_data,file_name or "profile.jpg",account_root(uid));url=f"/users/{uid}/{name}";s=load_settings(uid,ai_id);s["profile_photo"]=url;save_settings(uid,ai_id,s);return self.send_json({"ok":True,"profile_photo":url},uid,200,ai_id)
                name=save_upload(file_data,file_name or "ai_photo.jpg",ai_photo_dir(uid,ai_id));return self.send_json({"ok":True,"image":f"/users/{uid}/ais/{ai_id}/ai_photos/{name}"},uid,200,ai_id)
            if path=="/api/settings":
                uid,ai_id=active_ai(self)
                if not uid:return self.send_json({"error":"Authentication required"},None,401)
                length=int(self.headers.get("Content-Length",0));data=json.loads(self.rfile.read(length).decode("utf-8"));save_settings(uid,ai_id,data);return self.send_json(load_settings(uid,ai_id),uid,200,ai_id)
            if path=="/api/ai/select":
                uid=self.auth_required()
                if not uid:return
                length=int(self.headers.get("Content-Length",0));data=json.loads(self.rfile.read(length).decode("utf-8"));ai_id=clean_id(data.get("ai_id"))
                if not set_active(uid,ai_id):return self.send_json({"error":"AI not found"},uid,404)
                return self.send_json({"ok":True,"ai_id":ai_id},uid,200,ai_id)
            if path=="/api/ai/create":
                uid=self.auth_required()
                if not uid:return
                ai_id=create_ai(uid)
                if not ai_id:return self.send_json({"error":"Maximum of 3 AIs reached"},uid,400)
                return self.send_json({"ok":True,"ai_id":ai_id},uid,200,ai_id)
            if path=="/api/ai/delete":
                uid=self.auth_required()
                if not uid:return
                length=int(self.headers.get("Content-Length",0));data=json.loads(self.rfile.read(length).decode("utf-8"));ai_id=clean_id(data.get("ai_id"))
                if not delete_ai(uid,ai_id):return self.send_json({"error":"Cannot delete AI"},uid,400)
                return self.send_json({"ok":True},uid)
            if path=="/api/auth/logout":
                token=cookie(self,"AI_session");sessions=get_sessions();sessions.pop(token,None);save_json(SESSIONS_FILE,sessions);return self.send_json({"ok":True})
            if path=="/api/auth/login" or path=="/api/auth/register":
                length=int(self.headers.get("Content-Length",0));data=json.loads(self.rfile.read(length).decode("utf-8"));accounts=get_accounts();users=accounts.setdefault("users",{});email=normalize_email(data.get("email"));password=str(data.get("password","")).strip()
                if not valid_email(email) or len(password)<6:return self.send_json({"error":"Valid email and password of at least 6 characters required"},None,400)
                existing=next(((uid,u) for uid,u in users.items() if normalize_email(u.get("email"))==email),None)
                if path.endswith("register"):
                    if existing:return self.send_json({"error":"Account already exists"},None,409)
                    uid="U-"+uuid.uuid4().hex[:16];users[uid]={"email":email,"username":str(data.get("username","")).strip()[:60],"password":hash_password(password)};save_json(AUTH_FILE,accounts);ensure_first_ai(uid)
                else:
                    if not existing or not verify_password(password,existing[1].get("password","")):return self.send_json({"error":"Invalid email or password"},None,401)
                    uid=existing[0];ensure_first_ai(uid)
                token=create_session(uid);return self.send_json({"ok":True,"user_id":uid,"ais":list_ais(uid)},uid,200,session_token=token)
            self.send_error(404)
        except Exception as e:
            print("SERVER ERROR:",e);self.send_error(500,str(e))

if __name__ == "__main__":
    start_mdns()
    print("================================")
    print("LOCAL AI SERVER")
    print("================================")
    print(f"LAN:    http://{_lan_ip()}:{PORT}/")
    print(f"PUBLIC: {PUBLIC_URL}")
    print("================================")
    ThreadingHTTPServer(("0.0.0.0",PORT),AIHandler).serve_forever()
