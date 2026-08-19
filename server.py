"""Stable AI Server entry point."""
import os
from http.server import ThreadingHTTPServer
ROOT=os.path.dirname(os.path.abspath(__file__));os.chdir(ROOT)
from core.server_impl import AIHandler
from core.stage3_bridge import apply as _apply_stage3
from core.stage4_bridge import apply as _apply_stage4
_apply_stage3();_apply_stage4()
import chats_api
chats_api.install_handler_routes(AIHandler,__import__("core.server_impl",fromlist=["AIHandler"]))
from core.admin_bridge import install_handler_routes as _install_admin_routes
_install_admin_routes(AIHandler)
PORT=__import__("core.config",fromlist=["PORT"]).PORT
PUBLIC_URL=__import__("core.config",fromlist=["PUBLIC_URL"]).PUBLIC_URL
if __name__=="__main__":
    print("================================");print("LOCAL AI SERVER");print("================================");print(f"PORT:   {PORT}");print(f"PUBLIC: {PUBLIC_URL}");print("================================");ThreadingHTTPServer(("0.0.0.0",PORT),AIHandler).serve_forever()
