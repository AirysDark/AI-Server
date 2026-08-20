"""PythonAnywhere WSGI entry point for AI-server."""
import io
import os
import sys
import json
import uuid
import logging
from dotenv import load_dotenv
PROJECT_DIR=os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(PROJECT_DIR,".env"),override=False)
if PROJECT_DIR not in sys.path:sys.path.insert(0,PROJECT_DIR)
os.chdir(PROJECT_DIR)
from core.logging_setup import setup_logging,log_access
setup_logging()
from server import AIHandler
from core.auth import current_user,get_accounts,hash_password,normalize_email,valid_email,create_session
from core.ai_manager import active_ai,ensure_first_ai,list_ais
from core.storage import save_json
from core.config import AUTH_FILE
from core.local_model_bridge import handle_wsgi_upload
import chats_api
from reset_auth import request_reset,reset_password
class _WSGIConnection:
 def __init__(self,request_bytes):self._rfile=io.BytesIO(request_bytes);self._wfile=io.BytesIO()
 def makefile(self,mode,buffering=None):return self._rfile if "r" in mode else self._wfile
 def settimeout(self,value):pass
 def gettimeout(self):return None
 def shutdown(self,how):pass
 def close(self):pass
class _WSGIRequestHandler(AIHandler):
 def setup(self):self.connection=self.request;self.rfile=self.connection.makefile("rb",self.rbufsize);self.wfile=self.connection.makefile("wb",self.wbufsize)
 def finish(self):pass
 def address_string(self):return self.client_address[0]
def _direct_json(environ,start_response,status,data,extra_headers=None):
 body=json.dumps(data,ensure_ascii=False).encode("utf-8");headers=[("Content-Type","application/json; charset=utf-8"),("Content-Length",str(len(body)))]
 if extra_headers:headers.extend(extra_headers)
 start_response(status,headers);return [body]
def _read_json(body):
 try:return json.loads(body.decode("utf-8")) if body else {}
 except Exception:return None
def _auth_route(environ,start_response,method,path,body):
 if path not in ("/api/auth/register","/api/auth/forgot-password","/api/auth/reset-password"):return None
 if method!="POST":return _direct_json(environ,start_response,"405 Method Not Allowed",{"ok":False,"error":"Method not allowed"})
 data=_read_json(body)
 if data is None:return _direct_json(environ,start_response,"400 Bad Request",{"ok":False,"error":"Invalid JSON"})
 if path=="/api/auth/register":
  email=normalize_email(data.get("email"));password=str(data.get("password",""));confirm=str(data.get("confirm_password",""))
  if not valid_email(email) or len(password)<8:return _direct_json(environ,start_response,"400 Bad Request",{"error":"Valid email and password of at least 8 characters required"})
  if password!=confirm:return _direct_json(environ,start_response,"400 Bad Request",{"error":"Passwords do not match"})
  accounts=get_accounts();users=accounts.setdefault("users",{});existing=next(((user_id,user) for user_id,user in users.items() if normalize_email(user.get("email"))==email),None)
  if existing:return _direct_json(environ,start_response,"409 Conflict",{"error":"Account already exists"})
  uid="U-"+uuid.uuid4().hex[:16];users[uid]={"email":email,"username":str(data.get("username","")).strip()[:60],"password":hash_password(password)};save_json(AUTH_FILE,accounts);ensure_first_ai(uid);session=create_session(uid)
  headers=[("Set-Cookie",f"AI_session={session}; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000"),("Set-Cookie",f"AI_user={uid}; Path=/; SameSite=Lax; Max-Age=31536000")]
  return _direct_json(environ,start_response,"200 OK",{"ok":True,"user_id":uid,"ais":list_ais(uid)},headers)
 if path=="/api/auth/forgot-password":
  email=normalize_email(data.get("email"))
  if not valid_email(email):return _direct_json(environ,start_response,"400 Bad Request",{"ok":False,"error":"Valid email address required"})
  try:request_reset(email)
  except Exception as exc:logging.getLogger(__name__).exception("PASSWORD RESET EMAIL ERROR");return _direct_json(environ,start_response,"500 Internal Server Error",{"ok":False,"error":"Unable to send reset email right now"})
  return _direct_json(environ,start_response,"200 OK",{"ok":True,"message":"If that email belongs to an account, a reset link has been sent."})
 token=str(data.get("token",""));password=str(data.get("password",""));confirm=str(data.get("confirm_password",""))
 if password!=confirm:return _direct_json(environ,start_response,"400 Bad Request",{"ok":False,"error":"Passwords do not match"})
 ok,message=reset_password(token,password)
 if not ok:return _direct_json(environ,start_response,"400 Bad Request",{"ok":False,"error":message})
 return _direct_json(environ,start_response,"200 OK",{"ok":True,"message":message})
def _conversation_route(environ,start_response,method,path,body):
 if path not in ("/api/chats","/api/chats/new","/api/chats/open","/api/chats/rename"):return None
 class CookieHandler:
  def __init__(self,cookie):self.headers={"Cookie":cookie or ""}
 request=CookieHandler(environ.get("HTTP_COOKIE",""));uid=current_user(request)
 if not uid:return _direct_json(environ,start_response,"401 Unauthorized",{"ok":False,"error":"Authentication required"})
 _,ai_id=active_ai(request)
 if not ai_id:ai_id=ensure_first_ai(uid)
 if method=="GET" and path=="/api/chats":return _direct_json(environ,start_response,"200 OK",{"ok":True,"chats":chats_api.list_chats(uid,ai_id),"ai_id":ai_id})
 data=_read_json(body)
 if data is None:return _direct_json(environ,start_response,"400 Bad Request",{"ok":False,"error":"Invalid JSON"})
 if method=="POST" and path=="/api/chats/new":return _direct_json(environ,start_response,"200 OK",chats_api.new_chat(uid,ai_id))
 if method=="POST" and path=="/api/chats/rename":
  conversation_id=str(data.get("conversation_id","")).strip()
  if not conversation_id:return _direct_json(environ,start_response,"400 Bad Request",{"ok":False,"error":"conversation_id required"})
  if not chats_api.rename_chat(uid,ai_id,conversation_id,data.get("title")):return _direct_json(environ,start_response,"400 Bad Request",{"ok":False,"error":"Unable to rename conversation"})
  return _direct_json(environ,start_response,"200 OK",{"ok":True,"conversation_id":conversation_id})
 if method=="POST" and path=="/api/chats/open":
  conversation_id=str(data.get("conversation_id","")).strip()
  if not conversation_id:return _direct_json(environ,start_response,"400 Bad Request",{"ok":False,"error":"conversation_id required"})
  result=chats_api.open_chat(uid,ai_id,conversation_id)
  if result is None:return _direct_json(environ,start_response,"404 Not Found",{"ok":False,"error":"Conversation not found"})
  return _direct_json(environ,start_response,"200 OK",{"ok":True,"conversation":result})
 return _direct_json(environ,start_response,"405 Method Not Allowed",{"ok":False,"error":"Method not allowed"})
def application(environ,start_response):
 method=environ.get("REQUEST_METHOD","GET");path=environ.get("PATH_INFO") or "/";query=environ.get("QUERY_STRING","");request_target=path+("?"+query if query else "");header_lines=[]
 for key,value in environ.items():
  if key.startswith("HTTP_"):header_lines.append(f"{key[5:].replace('_','-')}: {value}")
 if environ.get("CONTENT_TYPE"):header_lines.append(f"Content-Type: {environ['CONTENT_TYPE']}")
 if environ.get("CONTENT_LENGTH"):header_lines.append(f"Content-Length: {environ['CONTENT_LENGTH']}")
 log_access(f"{environ.get('REMOTE_ADDR','-')} {method} {request_target}")
 # Stream large GGUF uploads directly to disk. Do this before the generic
 # body read, otherwise an 800+ MB model would be copied into Python RAM.
 if method=="POST" and path=="/api/local-model":
  return handle_wsgi_upload(environ,start_response)
 body_length=int(environ.get("CONTENT_LENGTH") or 0);body=environ["wsgi.input"].read(body_length) if body_length else b""
 direct=_auth_route(environ,start_response,method,path,body)
 if direct is not None:return direct
 direct=_conversation_route(environ,start_response,method,path,body)
 if direct is not None:return direct
 raw_request=(f"{method} {request_target} HTTP/1.1\r\n"+"\r\n".join(header_lines)+"\r\n\r\n").encode("iso-8859-1")+body
 connection=_WSGIConnection(raw_request);handler=_WSGIRequestHandler.__new__(_WSGIRequestHandler);handler.request=connection;handler.requestline="";handler.client_address=(environ.get("REMOTE_ADDR","127.0.0.1"),0);handler.server=type("WSGIServer",(),{"server_name":"ai-server.ddns.net","server_port":80})();handler.directory=PROJECT_DIR;handler.setup();handler.handle_one_request()
 response=connection._wfile.getvalue();separator=response.find(b"\r\n\r\n")
 if separator<0:
  logging.getLogger(__name__).error("Invalid HTTP response from AI server");start_response("500 Internal Server Error",[("Content-Type","text/plain; charset=utf-8")]);return [b"Invalid HTTP response from AI server"]
 header_block=response[:separator].decode("iso-8859-1");response_body=response[separator+4:];lines=header_block.split("\r\n");parts=lines[0].split(" ",2);status=f"{parts[1]} {parts[2]}" if len(parts)>=3 else "500 Internal Server Error";response_headers=[]
 for line in lines[1:]:
  if ":" not in line:continue
  name,value=line.split(":",1)
  if name.lower() in ("transfer-encoding","connection","server","date"):continue
  response_headers.append((name.strip(),value.strip()))
 if not any(name.lower()=="content-length" for name,_ in response_headers):response_headers.append(("Content-Length",str(len(response_body))))
 start_response(status,response_headers);return [response_body]