from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import json, os, uuid, re, random, time, hashlib, hmac, secrets, shutil, socket, struct, threading, atexit
from urllib.parse import urlparse, parse_qs
from email.parser import BytesParser
from email.policy import default
from brain import think, learn_from_conversation, record_feedback
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
    if not os.path.exists(path):return default
    try:
        with open(path,"r",encoding="utf-8") as f:return json.load(f)
    except Exception:return default

def save_json(path,data):
    if os.path.dirname(path):os.makedirs(os.path.dirname(path),exist_ok=True)
    with open(path,"w",encoding="utf-8") as f:json.dump(data,f,indent=2,ensure_ascii=False)

def cookie(handler,name):
    raw=handler.headers.get("Cookie","")
    for part in raw.split(";"):
        k,_,v=part.strip().partition("=")
        if k==name:return v
    return ""

def clean_id(value):return re.sub(r"[^A-Za-z0-9_-]","",str(value or ""))[:100]

def current_user(handler):
    token=cookie(handler,"AI_session")
    return clean_id(get_sessions().get(token,{}).get("user_id")) or None

def get_sessions():return load_json(SESSIONS_FILE,{})
def get_accounts():return load_json(AUTH_FILE,{"users":{}})
def valid_email(email):return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$",email or ""))
def normalize_email(email):return str(email or "").strip().lower()
def hash_password(password):return hashlib.sha256(str(password).encode()).hexdigest()
def verify_password(password,hashed):return hmac.compare_digest(hash_password(password),hashed)
def create_session(uid):
    token=secrets.token_urlsafe(32);sessions=get_sessions();sessions[token]={"user_id":uid,"created":time.time()};save_json(SESSIONS_FILE,sessions);return token

def account_root(uid):return os.path.join(USERS_DIR,clean_id(uid))
def ai_root(uid,ai_id):return os.path.join(account_root(uid),"ais",clean_id(ai_id))
def upload_dir(uid,ai_id):return os.path.join(ai_root(uid,ai_id),"uploads")
def ai_photo_dir(uid,ai_id):return os.path.join(ai_root(uid,ai_id),"ai_photos")
def safe_name(name):return re.sub(r"[^A-Za-z0-9._-]","_",os.path.basename(name or "upload"))[:120]
def save_upload(data,name,directory):
    os.makedirs(directory,exist_ok=True);name=safe_name(name);path=os.path.join(directory,name)
    with open(path,"wb") as f:f.write(data)
    return name

def features(s):
    f=s.get("features",{});return {"online_ai":f.get("online_ai",True),"learning":f.get("learning",True),"long_term_memory":f.get("long_term_memory",True),"relevant_memory":f.get("relevant_memory",True),"automatic_images":f.get("automatic_images",False),"proactive_images":f.get("proactive_images",False)}

def load_settings(uid,ai_id):return load_json(os.path.join(ai_root(uid,ai_id),"settings.json"),{"ai_name":"AI","features":{"online_ai":True,"learning":True}})
def save_settings(uid,ai_id,s):
    os.makedirs(ai_root(uid,ai_id),exist_ok=True);save_json(os.path.join(ai_root(uid,ai_id),"settings.json"),s)
def list_ais(uid):return load_json(AIS_FILE,{}).get(clean_id(uid),[])
def ensure_first_ai(uid):
    ais=load_json(AIS_FILE,{});uid=clean_id(uid)
    if not ais.get(uid):
        ai_id="AI-"+uuid.uuid4().hex[:12];ais[uid]=[ai_id];save_json(AIS_FILE,ais);save_settings(uid,ai_id,{"ai_id":ai_id,"user_id":uid,"ai_name":"AI","features":{"online_ai":True,"learning":True,"long_term_memory":True,"relevant_memory":True}})
def active_ai(handler):
    uid=current_user(handler)
    if not uid:return None,None
    ais=list_ais(uid);active=clean_id(cookie(handler,"AI_active"));ai_id=active if active in ais else (ais[0] if ais else None)
    if ai_id:ensure_first_ai(uid)
    return uid,ai_id
def set_active(uid,ai_id):return clean_id(ai_id) in list_ais(uid)
def load_conversation(uid,ai_id):return load_json(os.path.join(ai_root(uid,ai_id),"conversation.json"),{"conversation":[]})
def save_conversation(uid,ai_id,user,reply,image=None):
    path=os.path.join(ai_root(uid,ai_id),"conversation.json");data=load_conversation(uid,ai_id);data.setdefault("conversation",[]).append({"timestamp":datetime_now(),"user":user,"AI":reply,"image":image});data["conversation"]=data["conversation"][-500:];save_json(path,data)
def datetime_now():return __import__("datetime").datetime.now().isoformat()
def ai_profile(profile,prompt,s):return profile

def random_image(uid,ai_id):return None

def clean_reply(value):return str(value or "").strip()
def proactive(uid,ai_id,last_activity):return {"message":None}

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
    learn_from_conversation(prompt,reply,scoped_memory)
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
            if path=="/api/feedback":
                uid,ai_id=active_ai(self)
                if not uid:return self.send_json({"error":"Authentication required"},None,401)
                length=int(self.headers.get("Content-Length",0));data=json.loads(self.rfile.read(length).decode("utf-8"));message=str(data.get("message","")).strip();reply=str(data.get("reply","")).strip();rating=data.get("rating")
                if not message or not reply or rating not in ("up","down",1,-1):return self.send_json({"error":"message, reply and rating are required"},uid,400,ai_id)
                learning_path=os.path.join(ai_root(uid,ai_id),"learning_replies.json");score=record_feedback(message,reply,rating,learning_path,os.path.join(ai_root(uid,ai_id),"feedback.json"));return self.send_json({"ok":True,"score":score},uid,200,ai_id)
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
    start_mdns();print("================================");print("LOCAL AI SERVER");print("================================");print(f"LAN:    http://{_lan_ip()}:{PORT}/");print(f"PUBLIC: {PUBLIC_URL}");print("================================");ThreadingHTTPServer(("0.0.0.0",PORT),AIHandler).serve_forever()