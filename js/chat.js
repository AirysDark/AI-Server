function updateTypingIndicator(name){$('typing').innerText=(name||'AI')+' is typing...'}

function formatTime(time){return (typeof time==='string'?new Date(time):time).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}

function addMessageActions(container, text, message, type){
 if(type!=='AI')return;
 const actions=document.createElement('div');actions.className='message-actions';
 const copy=document.createElement('button');copy.type='button';copy.className='message-action';copy.innerText='Copy';copy.onclick=async()=>{try{await navigator.clipboard.writeText(text);copy.innerText='Copied';setTimeout(()=>copy.innerText='Copy',1200)}catch{copy.innerText='Copy failed';setTimeout(()=>copy.innerText='Copy',1200)}};
 const up=document.createElement('button');up.type='button';up.className='message-action feedback';up.innerText='👍';
 const down=document.createElement('button');down.type='button';down.className='message-action feedback';down.innerText='👎';
 const sendFeedback=async(rating,button)=>{
   up.classList.remove('selected');down.classList.remove('selected');button.classList.add('selected');
   try{
     const settings=await apiGet('/api/settings');
     settings._feedback_queue=Array.isArray(settings._feedback_queue)?settings._feedback_queue:[];
     settings._feedback_queue.push({message:String(message||''),reply:String(text||''),rating});
     settings._feedback_queue=settings._feedback_queue.slice(-100);
     await apiPost('/api/settings',settings);
   }catch(e){console.error('Feedback failed',e)}
 };
 up.onclick=()=>sendFeedback('up',up);down.onclick=()=>sendFeedback('down',down);
 actions.append(copy,up,down);container.appendChild(actions);
}

function add(text,type,time=new Date(),message=''){
 const d=document.createElement('div');d.className='msg '+type;
 const n=document.createElement('div');n.className='message-content';
 if(type==='AI' && typeof renderMarkdown==='function'){n.innerHTML=renderMarkdown(text);bindCopyCode(n)}else n.innerText=text;
 d.appendChild(n);
 const t=document.createElement('span');t.className='timestamp';t.innerText=formatTime(time);d.appendChild(t);
 addMessageActions(d,text,message,type);
 $('chat').appendChild(d);$('chat').scrollTop=$('chat').scrollHeight;
}

function addImage(url,type,time=new Date()){
 const d=document.createElement('div');d.className='msg '+type;
 const i=document.createElement('img');i.src=url;i.className='image-preview';i.alt='Photo';d.appendChild(i);
 const t=document.createElement('span');t.className='timestamp';t.innerText=formatTime(time);d.appendChild(t);
 $('chat').appendChild(d);$('chat').scrollTop=$('chat').scrollHeight;
}

async function loadMemory(){
 try{
  const j=await apiGet('/api/user');$('chat').innerHTML='';
  (j.conversation||[]).forEach(c=>{
   if(c.user)add(c.user,'user',c.timestamp,c.user);
   if(c.image)addImage(c.image,c.user?'user':'AI',c.timestamp);
   if(c.AI)add(c.AI,'AI',c.timestamp,c.user||'');
  });
 }catch(e){console.log(e)}
}

async function send(){
 const text=$('msg').value.trim(),file=$('chatImage').files[0];if(!text&&!file)return;
 lastActivity=Date.now();if(text)add(text,'user',new Date(),text);if(file)addImage(URL.createObjectURL(file),'user');
 $('msg').value='';$('chatImage').value='';$('send').disabled=true;updateTypingIndicator($('aiName').innerText||'AI');$('typing').style.display='block';
 try{
  let r;
  if(file){const f=new FormData();f.append('message',text);f.append('image',file);r=await fetch('/chat',{method:'POST',body:f})}
  else r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text})});
  const j=await r.json();if(!r.ok)throw Error(j.error||'Chat failed');
  add(j.reply||'AI did not reply','AI',new Date(),text);if(j.image)addImage(j.image,'AI');
 }catch(e){add('AI error: '+e.message,'AI',new Date(),text)}
 finally{$('send').disabled=false;$('typing').style.display='none';$('msg').focus()}
}

async function checkProactive(){
 if(document.visibilityState!=='visible')return;
 try{const j=await apiGet('/api/proactive?last_activity='+lastActivity);if(j.message){updateTypingIndicator($('aiName').innerText||'AI');add(j.message,'AI',new Date(),'[Proactive check-in]');if(j.image)addImage(j.image,'AI');lastActivity=Date.now()}}catch(e){}
}
function startProactive(){if(timer)clearInterval(timer);timer=setInterval(checkProactive,30000)}
function clearChat(){if(confirm('Clear the chat display?'))$('chat').innerHTML=''}
