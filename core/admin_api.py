"""Administrator authentication and account/storage management."""
from __future__ import annotations
import hashlib,hmac,os,secrets,shutil,time
from core.config import STORAGE_DIR,USERS_DIR
from core.auth import hash_password
from core.storage import load_json,save_json
ADMIN_FILE=os.path.join(STORAGE_DIR,"admin.json");ADMIN_COOKIE="AI_admin_session";ADMIN_SESSIONS_FILE=os.path.join(STORAGE_DIR,"admin_sessions.json")
def _read(path,default):
 try:return load_json(path,default)
 except Exception:return default
def _write(path,data):save_json(path,data)
def _hash(password,salt=None):
 salt=salt or secrets.token_hex(16);return salt,hashlib.pbkdf2_hmac("sha256",password.encode(),salt.encode(),240000).hex()
def _verify(password,record):
 if not record or not record.get("hash") or not record.get("salt"):return False
 return hmac.compare_digest(_hash(password,record["salt"])[1],record["hash"])
def ensure_admin():
 data=_read(ADMIN_FILE,None)
 if isinstance(data,dict) and data.get("hash") and data.get("salt"):return data
 salt,digest=_hash("admin");data={"username":"admin","salt":salt,"hash":digest,"must_change_password":True,"created":time.time(),"updated":time.time()};_write(ADMIN_FILE,data);return data
def _sessions():return _read(ADMIN_SESSIONS_FILE,{})
def _cookie(handler,name):
 for part in handler.headers.get("Cookie","").split(";"):
  k,_,v=part.strip().partition("=")
  if k==name:return v
 return ""
def admin_user(handler):
 token=_cookie(handler,ADMIN_COOKIE);return _sessions().get(token) if token else None
def login(handler,username,password):
 admin=ensure_admin()
 if str(username).strip()!=admin.get("username","admin") or not _verify(str(password),admin):return {"ok":False,"error":"Invalid administrator credentials"},401,None
 token=secrets.token_urlsafe(32);sessions=_sessions();sessions[token]={"username":admin.get("username","admin"),"created":time.time()};_write(ADMIN_SESSIONS_FILE,sessions)
 return {"ok":True,"must_change_password":bool(admin.get("must_change_password",False))},200,token
def logout(handler):
 sessions=_sessions();sessions.pop(_cookie(handler,ADMIN_COOKIE),None);_write(ADMIN_SESSIONS_FILE,sessions)
def change_password(handler,old_password,new_password):
 if not admin_user(handler):return {"ok":False,"error":"Administrator authentication required"},401
 if len(str(new_password or ""))<8:return {"ok":False,"error":"New password must be at least 8 characters"},400
 admin=ensure_admin()
 if not _verify(str(old_password or ""),admin):return {"ok":False,"error":"Current password is incorrect"},401
 salt,digest=_hash(str(new_password));admin.update({"salt":salt,"hash":digest,"must_change_password":False,"updated":time.time()});_write(ADMIN_FILE,admin);return {"ok":True},200
def _server_module():
 import core.server_impl as server
 return server
def dashboard(handler):
 server=_server_module();accounts=server.get_accounts().get("users",{});result=[]
 for uid,account in accounts.items():
  ais=server.list_ais(uid);result.append({"user_id":uid,"email":account.get("email"),"username":account.get("username"),"banned":bool(account.get("banned",False)),"ai_count":len(ais),"ais":ais})
 return {"ok":True,"accounts":result,"storage_dir":STORAGE_DIR,"user_storage_dir":USERS_DIR},200
def account_detail(uid):
 server=_server_module();account=server.get_accounts().get("users",{}).get(uid)
 if not account:return {"ok":False,"error":"Account not found"},404
 return {"ok":True,"user_id":uid,"email":account.get("email"),"username":account.get("username"),"banned":bool(account.get("banned",False)),"account":{k:v for k,v in account.items() if k!="password"},"ais":server.list_ais(uid)},200
def update_account(uid,data):
 server=_server_module();accounts=server.get_accounts();account=accounts.setdefault("users",{}).get(uid)
 if not account:return {"ok":False,"error":"Account not found"},404
 for key in ("username","email","banned"):
  if key in data:account[key]=data[key]
 result={"ok":True}
 if data.get("reset_password"):
  temp=secrets.token_urlsafe(9);account["password"]=hash_password(temp);account["must_change_password"]=True;result["temporary_password"]=temp
 if data.get("change_password"):
  new=str(data.get("new_password") or "")
  if len(new)<6:return {"ok":False,"error":"Password must be at least 6 characters"},400
  account["password"]=hash_password(new);account["must_change_password"]=False
 server.save_json(server.AUTH_FILE,accounts);return result,200
def _user_root(uid):return os.path.abspath(os.path.join(USERS_DIR,os.path.basename(uid)))
def _safe_target(uid,relative):
 root=_user_root(uid);target=os.path.abspath(os.path.join(root,str(relative or "").lstrip("/")));return target if target.startswith(root+os.sep) else None
def files(handler,uid=None,relative=""):
 root=os.path.abspath(USERS_DIR if not uid else _user_root(uid));target=os.path.abspath(os.path.join(root,str(relative or "").lstrip("/")))
 if not target.startswith(root+os.sep) and target!=root:return {"ok":False,"error":"Invalid path"},400
 if not os.path.isdir(target):return {"ok":False,"error":"Directory not found"},404
 items=[]
 for name in sorted(os.listdir(target),key=str.lower):
  p=os.path.join(target,name);items.append({"name":name,"directory":os.path.isdir(p),"size":os.path.getsize(p) if os.path.isfile(p) else None})
 return {"ok":True,"path":os.path.relpath(target,USERS_DIR),"items":items},200
def read_json_file(uid,relative):
 target=_safe_target(uid,relative)
 if not target or not os.path.isfile(target):return {"ok":False,"error":"File not found"},404
 if not target.lower().endswith(".json"):return {"ok":False,"error":"Only JSON files can be viewed here"},400
 return {"ok":True,"data":_read(target,{})},200
def update_json_file(uid,relative,data):
 target=_safe_target(uid,relative)
 if not target or not os.path.isfile(target):return {"ok":False,"error":"File not found"},404
 if not target.lower().endswith(".json"):return {"ok":False,"error":"Only JSON files can be edited here"},400
 _write(target,data);return {"ok":True},200
def delete_file(uid,relative):
 target=_safe_target(uid,relative)
 if not target or not os.path.isfile(target):return {"ok":False,"error":"File not found"},404
 os.remove(target);return {"ok":True},200
def delete_account(uid):
 server=_server_module();accounts=server.get_accounts();users=accounts.setdefault("users",{})
 if uid not in users:return {"ok":False,"error":"Account not found"},404
 users.pop(uid,None);server.save_json(server.AUTH_FILE,accounts);shutil.rmtree(_user_root(uid),ignore_errors=True);return {"ok":True},200
def handle_get(handler,path,query):
 if not path.startswith("/api/admin/"):return False
 if not admin_user(handler):handler.send_json({"ok":False,"error":"Administrator authentication required"},status=401);return True
 if path=="/api/admin/me":
  a=ensure_admin();handler.send_json({"ok":True,"username":a.get("username","admin"),"must_change_password":bool(a.get("must_change_password",False))});return True
 if path=="/api/admin/dashboard":d,s=dashboard(handler);handler.send_json(d,status=s);return True
 if path=="/api/admin/account":d,s=account_detail((query.get("uid") or [""])[0]);handler.send_json(d,status=s);return True
 if path=="/api/admin/files":d,s=files(handler,(query.get("uid") or [None])[0],(query.get("path") or [""])[0]);handler.send_json(d,status=s);return True
 if path=="/api/admin/file/read":d,s=read_json_file((query.get("uid") or [""])[0],(query.get("path") or [""])[0]);handler.send_json(d,status=s);return True
 return False
def handle_post(handler,path,data):
 if path=="/api/admin/login":return True,login(handler,data.get("username"),data.get("password"))
 if not path.startswith("/api/admin/"):return False,None
 if not admin_user(handler):handler.send_json({"ok":False,"error":"Administrator authentication required"},status=401);return True,None
 if path=="/api/admin/logout":logout(handler);handler.send_json({"ok":True});return True,None
 if path=="/api/admin/password":r,s=change_password(handler,data.get("old_password"),data.get("new_password"));handler.send_json(r,status=s);return True,None
 if path=="/api/admin/account/update":r,s=update_account(str(data.get("uid","")),data);handler.send_json(r,status=s);return True,None
 if path=="/api/admin/file/save":r,s=update_json_file(str(data.get("uid","")),str(data.get("path","")),data.get("data"));handler.send_json(r,status=s);return True,None
 if path=="/api/admin/file/delete":r,s=delete_file(str(data.get("uid","")),str(data.get("path","")));handler.send_json(r,status=s);return True,None
 if path=="/api/admin/account/delete":r,s=delete_account(str(data.get("uid","")));handler.send_json(r,status=s);return True,None
 return False,None
