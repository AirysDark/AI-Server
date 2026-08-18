let account=null,lastActivity=Date.now(),timer=null;

async function boot(){
 try{
  let me=await(await fetch('/api/auth/me')).json();
  if(!me.authenticated){location.href='login.html';return}
  account=me;
  let s=await(await fetch('/api/settings')).json();
  if(!s.setup_complete){location.href='setup.html';return}
  fillSettings(s);
  await loadMemory();
  startProactive();
 }catch(e){console.error(e);location.href='login.html'}
}

$('msg').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}});
window.addEventListener('load',boot);
