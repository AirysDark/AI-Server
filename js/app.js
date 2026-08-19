let account=null,lastActivity=Date.now(),timer=null;

async function boot(){
 try{
  const me=await (await fetch('/api/auth/me',{credentials:'same-origin',cache:'no-store'})).json();
  if(!me.authenticated){location.href='login.html';return}
  account=me;
  const s=await (await fetch('/api/settings',{credentials:'same-origin',cache:'no-store'})).json();
  if(!s||s.error)throw Error(s?.error||'Could not load AI settings');
  if(!s.setup_complete){location.href='setup.html';return}
  fillSettings(s);
  const params=new URLSearchParams(location.search);
  const chatId=params.get('chat');
  if(chatId){try{localStorage.setItem('lastConversation',JSON.stringify({conversation_id:String(chatId),ai_id:s.ai_id||''}))}catch(e){};await loadSelectedChat(chatId)}
  else{
   let lastChat=null;
   try{const saved=JSON.parse(localStorage.getItem('lastConversation')||'null');if(saved&&saved.conversation_id&&(!saved.ai_id||saved.ai_id===s.ai_id))lastChat=saved.conversation_id}catch(e){}
   if(lastChat){
    try{await loadSelectedChat(lastChat)}catch(e){try{localStorage.removeItem('lastConversation')}catch(x){};await loadMemory()}
   }else await loadMemory();
  }
  startProactive();
 }catch(e){
  console.error('AI boot failed',e);
  const chat=document.getElementById('chat');
  if(chat)chat.innerHTML='<div class="msg AI"><div class="message-content">Unable to load this AI. '+String(e.message||e)+'</div></div>';
 }
}

async function loadSelectedChat(chatId){
 const id=String(chatId||'').trim();
 if(!id)throw Error('Missing conversation ID');
 const result=await apiPost('/api/chats/open',{conversation_id:id});
 if(!result||result.ok===false)throw Error(result?.error||'Could not open conversation');
 let conversation=Array.isArray(result.conversation)?result.conversation:null;
 if(!conversation&&result.data&&typeof result.data==='object')conversation=Array.isArray(result.data.conversation)?result.data.conversation:null;
 if(!conversation&&result.archive&&typeof result.archive==='object')conversation=Array.isArray(result.archive.conversation)?result.archive.conversation:null;
 if(!conversation){const fallback=await apiGet('/api/user');if(fallback&&Array.isArray(fallback.conversation))conversation=fallback.conversation}
 if(!Array.isArray(conversation))throw Error('Conversation archive has invalid format');
 const chat=document.getElementById('chat');
 if(!chat)throw Error('Chat element not found');
 chat.innerHTML='';
 conversation.forEach(loadConversationEntry);
 try{localStorage.setItem('lastConversation',JSON.stringify({conversation_id:id,ai_id:account?.ai_id||''}))}catch(e){}
 sessionStorage.setItem('selectedConversation',JSON.stringify({conversation_id:id,data:{conversation:conversation}}));
}

$('msg').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}});
window.addEventListener('load',boot);
