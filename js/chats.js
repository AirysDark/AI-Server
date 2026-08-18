function esc(s){const d=document.createElement('div');d.textContent=String(s??'');return d.innerHTML}
function chatTime(v){if(!v)return '';const d=new Date(Number(v)*1000);return d.toLocaleDateString([], {month:'short',day:'numeric'})+' '+d.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}

function closeRenameDialog(){const el=$('renameDialog');if(el)el.remove()}
function showRenameDialog(id,currentTitle){
 closeRenameDialog();
 const overlay=document.createElement('div');overlay.id='renameDialog';overlay.className='rename-overlay';
 overlay.innerHTML='<div class="rename-dialog" role="dialog" aria-modal="true" aria-labelledby="renameTitle"><div class="rename-dialog-title" id="renameTitle">Rename conversation</div><div class="rename-dialog-subtitle">Give this chat a name you will recognize.</div><input id="renameInput" class="rename-input" type="text" maxlength="80" autocomplete="off"><div class="rename-dialog-actions"><button type="button" class="rename-cancel">Cancel</button><button type="button" class="rename-save">Save</button></div></div>';
 document.body.appendChild(overlay);
 const input=$('renameInput');input.value=currentTitle==='New chat'?'':(currentTitle||'');
 const save=()=>{const clean=input.value.trim();if(!clean){input.focus();return}renameChatValue(id,clean)};
 overlay.querySelector('.rename-cancel').onclick=closeRenameDialog;overlay.querySelector('.rename-save').onclick=save;
 overlay.addEventListener('click',e=>{if(e.target===overlay)closeRenameDialog()});input.addEventListener('keydown',e=>{if(e.key==='Enter')save();if(e.key==='Escape')closeRenameDialog()});
 requestAnimationFrame(()=>{input.focus();input.select()});
}

async function renameChatValue(id,title){
 try{await apiPost('/api/chats/rename',{conversation_id:id,title});closeRenameDialog();await loadChats()}catch(e){closeRenameDialog();alert('Unable to rename chat: '+e.message)}
}

async function loadChats(){
 try{
  const j=await apiGet('/api/chats');
  $('aiLabel').innerText='Conversations with '+(j.ai_id||'this AI');
  const list=$('chatList');list.innerHTML='';
  if(!j.chats?.length){list.innerHTML='<div class="small">No conversations yet.</div>';return}
  j.chats.forEach(c=>{
   const row=document.createElement('button');row.className='chat-list-item'+(c.current?' current':'');row.type='button';row.innerHTML='<div class="chat-list-title">'+esc(c.title||'New chat')+'</div><div class="chat-list-time">'+esc(chatTime(c.updated))+'</div>';
   let pressTimer=null,longPress=false;
   const startPress=()=>{longPress=false;pressTimer=setTimeout(()=>{longPress=true;showRenameDialog(c.conversation_id,c.title||'New chat')},650)};
   const cancelPress=()=>{if(pressTimer){clearTimeout(pressTimer);pressTimer=null}};
   row.addEventListener('pointerdown',startPress);row.addEventListener('pointerup',cancelPress);row.addEventListener('pointerleave',cancelPress);row.addEventListener('pointercancel',cancelPress);
   row.onclick=()=>{if(!longPress)openChat(c.conversation_id);longPress=false};
   list.appendChild(row);
  });
 }catch(e){$('chatList').innerHTML='<div class="small">Unable to load chats: '+esc(e.message)+'</div>'}
}

async function newChat(){
 try{await apiPost('/api/chats/new',{});location.href='index.html'}catch(e){alert('Unable to start a new chat: '+e.message)}
}
async function openChat(id){
 if(id==='current'){location.href='index.html';return}
 try{await apiPost('/api/chats/open',{conversation_id:id});location.href='index.html'}catch(e){alert('Unable to open chat: '+e.message)}
}
loadChats();
