function updateTypingIndicator(name){$('typing').innerText=(name||'AI')+' is typing...'}
function formatTime(time){const d=time instanceof Date?time:new Date(typeof time==='number'?time*1000:time);return Number.isNaN(d.getTime())?'':d.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}
function getSelectedConversationId(){const cookie=document.cookie.split(';').map(x=>x.trim()).find(x=>x.startsWith('AI_chat='));return cookie?decodeURIComponent(cookie.slice('AI_chat='.length)):''}
function saveSelectedConversation(id){
 const value=String(id||'').trim();
 if(!value)return;
 document.cookie='AI_chat='+encodeURIComponent(value)+'; Path=/; SameSite=Lax; Max-Age=31536000';
 try{localStorage.setItem('lastConversation',JSON.stringify({conversation_id:value,ai_id:''}));localStorage.setItem('lastConversationId',value)}catch(e){}
}
function clearSelectedConversation(){
 document.cookie='AI_chat=; Path=/; SameSite=Lax; Max-Age=0';
 try{localStorage.removeItem('lastConversation');localStorage.removeItem('lastConversationId')}catch(e){}
}
async function ensureSelectedConversation(){
 const existing=getSelectedConversationId();
 if(existing){
  try{
   const opened=await apiPost('/api/chats/open',{conversation_id:existing});
   if(opened&&opened.ok!==false){saveSelectedConversation(existing);return existing}
  }catch(e){console.warn('Active conversation is stale; creating a new one',e)}
  clearSelectedConversation();
 }
 const result=await apiPost('/api/chats/new',{});
 if(!result||result.ok===false||!result.conversation_id)throw Error(result?.error||'Could not create a conversation');
 const id=String(result.conversation_id);
 saveSelectedConversation(id);
 return id;
}

const COPY_ICON='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 8V5a3 3 0 0 1 3-3h8a3 3 0 0 1 3 3v8a3 3 0 0 1-3 3h-3v3a3 3 0 0 1-3 3H5a3 3 0 0 1-3-3v-8a3 3 0 0 1 3-3h3Zm2 0h3a3 3 0 0 1 3 3v6h3a1 1 0 0 0 1-1V5a1 1 0 0 0-1-1h-8a1 1 0 0 0 1 1v3Zm3 2H5a1 1 0 0 0-1 1v8a1 1 0 0 0-1-1v-8a1 1 0 0 0 1 1v3Z"/></svg>';
const THUMB_UP_ICON='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 10v11H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3Zm2 11h7.2a2 2 0 0 0 1.94-1.52l2-8A2 2 0 0 0 18.2 9H14l.73-3.65A2.7 2.7 0 0 0 12.09 2L9 7.2V21Z"/></svg>';
const THUMB_DOWN_ICON='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M17 14V3h3a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2h-3ZM15 3H7.8a2 2 0 0 0-1.94 1.52l-2 8A2 2 0 0 0 5.8 15H10l-.73 3.65A2.7 2.7 0 0 0 11.91 22L15 16.8V3Z"/></svg>';

function addMessageActions(container,text,message,type){
 if(type!=='AI')return;
 const actions=document.createElement('div');actions.className='message-actions';
 const copy=document.createElement('button');copy.type='button';copy.className='message-action feedback';copy.innerHTML=COPY_ICON;copy.title='Copy response';copy.setAttribute('aria-label','Copy response');copy.onclick=async()=>{try{await navigator.clipboard.writeText(text);copy.classList.add('selected');copy.title='Copied';setTimeout(()=>{copy.classList.remove('selected');copy.title='Copy response'},1200)}catch{copy.title='Copy failed';setTimeout(()=>copy.title='Copy response',1200)}};
 const up=document.createElement('button');up.type='button';up.className='message-action feedback';up.innerHTML=THUMB_UP_ICON;up.title='Good response';up.setAttribute('aria-label','Thumbs up');
 const down=document.createElement('button');down.type='button';down.className='message-action feedback';down.innerHTML=THUMB_DOWN_ICON;down.title='Bad response';down.setAttribute('aria-label','Thumbs down');
 const sendFeedback=async(rating,button)=>{up.classList.remove('selected');down.classList.remove('selected');button.classList.add('selected');try{const settings=await apiGet('/api/settings');settings._feedback_queue=Array.isArray(settings._feedback_queue)?settings._feedback_queue:[];settings._feedback_queue.push({message:String(message||''),reply:String(text||''),rating});settings._feedback_queue=settings._feedback_queue.slice(-100);await apiPost('/api/settings',settings)}catch(e){console.error('Feedback failed',e);button.classList.remove('selected')}};
 up.onclick=()=>sendFeedback('up',up);down.onclick=()=>sendFeedback('down',down);actions.append(copy,up,down);container.appendChild(actions);
}

function add(text,type,time=new Date(),message=''){const d=document.createElement('div');d.className='msg '+type;const n=document.createElement('div');n.className='message-content';if(type==='AI'&&typeof renderMarkdown==='function'){n.innerHTML=renderMarkdown(text);bindCopyCode(n)}else n.innerText=text;d.appendChild(n);const t=document.createElement('span');t.className='timestamp';t.innerText=formatTime(time);d.appendChild(t);addMessageActions(d,text,message,type);$('chat').appendChild(d);$('chat').scrollTop=$('chat').scrollHeight}
function addImage(url,type,time=new Date()){const d=document.createElement('div');d.className='msg '+type;const i=document.createElement('img');i.src=url;i.className='image-preview';i.alt='Photo';d.appendChild(i);const t=document.createElement('span');t.className='timestamp';t.innerText=formatTime(time);d.appendChild(t);$('chat').appendChild(d);$('chat').scrollTop=$('chat').scrollHeight}

function loadConversationEntry(c){const user=c.user??c.user_message??(c.role==='user'?c.content:'');const ai=c.ai??c.AI??c.assistant??c.ai_reply??(c.role==='assistant'?c.content:'');const stamp=c.time??c.timestamp??new Date();if(user)add(user,'user',stamp,user);if(c.image)addImage(c.image,user?'user':'AI',stamp);if(ai)add(ai,'AI',stamp,user||'')}
async function loadMemory(){try{const j=await apiGet('/api/user');$('chat').innerHTML='';(j.conversation||[]).forEach(loadConversationEntry)}catch(e){console.error('Conversation load failed',e)}}

async function send(){const text=$('msg').value.trim(),file=$('chatImage').files[0];if(!text&&!file)return;lastActivity=Date.now();if(text)add(text,'user',new Date(),text);if(file)addImage(URL.createObjectURL(file),'user');$('msg').value='';$('chatImage').value='';$('send').disabled=true;updateTypingIndicator($('aiName').innerText||'AI');$('typing').style.display='block';try{const conversationId=await ensureSelectedConversation();let r;if(file){const f=new FormData();f.append('message',text);f.append('image',file);f.append('conversation_id',conversationId);r=await fetch('/chat',{method:'POST',body:f,credentials:'same-origin'})}else r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify({message:text,conversation_id:conversationId})});const j=await r.json();if(!r.ok)throw Error(j.error||'Chat failed');if(j.conversation_id)saveSelectedConversation(j.conversation_id);add(j.reply||'AI did not reply','AI',new Date(),text);if(j.image)addImage(j.image,'AI')}catch(e){add('AI error: '+e.message,'AI',new Date(),text)}finally{$('send').disabled=false;$('typing').style.display='none';$('msg').focus()}}
async function checkProactive(){if(document.visibilityState!=='visible')return;try{const j=await apiGet('/api/proactive?last_activity='+lastActivity);if(j.message){updateTypingIndicator($('aiName').innerText||'AI');add(j.message,'AI',new Date(),'[Proactive check-in]');if(j.image)addImage(j.image,'AI');lastActivity=Date.now()}}catch(e){}}
function startProactive(){if(timer)clearInterval(timer);timer=setInterval(checkProactive,30000)}
function clearChat(){if(confirm('Clear the chat display?'))$('chat').innerHTML=''}
