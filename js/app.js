let account=null,lastActivity=Date.now(),timer=null;

function currentAiId(){
 return String(account?.ai_id||'').trim();
}

function conversationStorageKey(){
 const aiId=currentAiId();
 return aiId?'lastConversation:'+aiId:'lastConversation';
}

function clearSelectedConversation(){
 document.cookie='AI_chat=; Path=/; SameSite=Lax; Max-Age=0';
 try{
  sessionStorage.removeItem('selectedConversation');
  localStorage.removeItem(conversationStorageKey());
  const saved=JSON.parse(localStorage.getItem('lastConversation')||'null');
  if(saved&&(!saved.ai_id||saved.ai_id===currentAiId()))localStorage.removeItem('lastConversation');
  localStorage.removeItem('lastConversationId');
 }catch(e){}
}

function readLastConversationId(){
 const aiId=currentAiId();
 try{
  const scoped=JSON.parse(localStorage.getItem(conversationStorageKey())||'null');
  if(scoped&&scoped.conversation_id)return String(scoped.conversation_id);
 }catch(e){}
 try{
  const saved=JSON.parse(localStorage.getItem('lastConversation')||'null');
  if(saved&&saved.conversation_id&&saved.ai_id===aiId)return String(saved.conversation_id);
 }catch(e){}
 const cookie=document.cookie.split(';').map(x=>x.trim()).find(x=>x.startsWith('AI_chat='));
 return cookie?decodeURIComponent(cookie.slice('AI_chat='.length)):'';
}

function setSelectedConversation(id){
 const value=String(id||'').trim();
 if(!value)return;
 const aiId=currentAiId();
 document.cookie='AI_chat='+encodeURIComponent(value)+'; Path=/; SameSite=Lax; Max-Age=31536000';
 try{
  const saved={conversation_id:value,ai_id:aiId};
  localStorage.setItem(conversationStorageKey(),JSON.stringify(saved));
  localStorage.setItem('lastConversation',JSON.stringify(saved));
  localStorage.removeItem('lastConversationId');
 }catch(e){}
}

async function createAndSelectConversation(){
 clearSelectedConversation();
 const result=await apiPost('/api/chats/new',{});
 if(!result||result.ok===false||!result.conversation_id)throw Error(result?.error||'Could not create conversation');
 const id=String(result.conversation_id);
 setSelectedConversation(id);
 const chat=document.getElementById('chat');
 if(chat)chat.innerHTML='';
 sessionStorage.setItem('selectedConversation',JSON.stringify({conversation_id:id,data:{conversation:[]}}));
 return id;
}

async function restoreOrCreateConversation(preferredId=''){
 const id=String(preferredId||readLastConversationId()||'').trim();
 if(id){
  try{
   await loadSelectedChat(id);
   return id;
  }catch(e){
   console.warn('Saved conversation is not valid for this AI; creating a new one:',e);
   clearSelectedConversation();
  }
 }
 return await createAndSelectConversation();
}

async function boot(){
 try{
  const me=await (await fetch('/api/auth/me',{credentials:'same-origin',cache:'no-store'})).json();
  if(!me.authenticated){location.href='login.html';return}
  account=me;
  const s=await (await fetch('/api/settings',{credentials:'same-origin',cache:'no-store'})).json();
  if(!s||s.error)throw Error(s?.error||'Could not load AI settings');
  account.ai_id=String(s.ai_id||account.ai_id||'').trim();
  if(!s.setup_complete){location.href='setup.html';return}
  fillSettings(s);
  const params=new URLSearchParams(location.search);
  const chatId=params.get('chat');
  await restoreOrCreateConversation(chatId||'');
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
 setSelectedConversation(id);
 sessionStorage.setItem('selectedConversation',JSON.stringify({conversation_id:id,data:{conversation:conversation}}));
}

$('msg').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}});
window.addEventListener('load',boot);
