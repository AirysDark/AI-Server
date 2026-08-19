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
  const params=new URLSearchParams(location.search);
  const chatId=params.get('chat');
  if(chatId) await loadSelectedChat(chatId); else await loadMemory();
  startProactive();
 }catch(e){
  console.error('AI boot failed',e);
  const chat=document.getElementById('chat');
  if(chat){chat.innerHTML='<div class="msg AI"><div class="message-content">Unable to load this AI. '+String(e.message||e)+'</div></div>'}
 }
}

async function loadSelectedChat(chatId){
 const result=await apiPost('/api/chats/open',{conversation_id:chatId});
 if(!result||result.ok===false)throw Error(result?.error||'Could not open conversation');
 const data=result.data||result;
 $('chat').innerHTML='';
 (data.conversation||result.conversation||[]).forEach(loadConversationEntry);
 sessionStorage.setItem('selectedConversation',JSON.stringify({conversation_id:chatId,data:data}));
}

$('msg').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}});
window.addEventListener('load',boot);
