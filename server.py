"""Stable AI Server entry point."""
import os
ROOT=os.path.dirname(os.path.abspath(__file__));os.chdir(ROOT)
from core.logging_setup import setup_logging,log_access
setup_logging()
from http.server import ThreadingHTTPServer
from core.server_impl import AIHandler
from core.stage3_bridge import apply as _apply_stage3
from core.stage4_bridge import apply as _apply_stage4
from core.stage5_profile_bridge import apply as _apply_stage5
_apply_stage3();_apply_stage4();_apply_stage5()
import chats_api
chats_api.install_handler_routes(AIHandler,__import__("core.server_impl",fromlist=["AIHandler"]))
from core.admin_bridge import install_handler_routes as _install_admin_routes
_install_admin_routes(AIHandler)
PORT=__import__("core.config",fromlist=["PORT"]).PORT
PUBLIC_URL=__import__("core.config",fromlist=["PUBLIC_URL"]).PUBLIC_URL

_original_log_request = getattr(AIHandler,"log_message",None)
def _log_message(self,format,*args):
    message = format % args if args else format
    log_access(f"{self.address_string()} {message}")
    if _original_log_request:
        _original_log_request(self,format,*args)
AIHandler.log_message = _log_message

if __name__=="__main__":
    print("================================");print("LOCAL AI SERVER");print("================================");print(f"PORT:   {PORT}");print(f"PUBLIC: {PUBLIC_URL}");print("================================");ThreadingHTTPServer(("0.0.0.0",PORT),AIHandler).serve_forever()
