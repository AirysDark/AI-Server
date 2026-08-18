let account=null,lastActivity=Date.now(),timer=null;

async function boot(){
 try{
  let me=await(await fetch('/api/auth/me',{credentials:'same-origin',cache:'no-store'})).json();
  if(!me.authenticated){location.href='login.html';return}
  account=me;
  let s=await(await fetch('/api/settings',{credentials:'same-origin',cache:'no-store'})).json();
  if(!s||s.error)throw Error(s?.error||'Could not load AI settings');
  if(!s.setup_complete){location.href='setup.html';return}
  fillSettings(s);
  await loadMemory();
  startProactive();
 }catch(e){
  console.error('AI boot failed',e);
  const chat=document.getElementById('chat');
  if(chat){chat.innerHTML='<div class="msg AI"><div class="message-content">Unable to load this AI. '+String(e.message||e)+'</div></div>'}
 }
}

$('msg').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}});
window.addEventListener('load',boot);
