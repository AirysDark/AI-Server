function updateTypingIndicator(name){$('typing').innerText=(name||'AI')+' is typing...'}

function add(text,type,time=new Date()){
 let d=document.createElement('div');d.className='msg '+type;
 let n=document.createElement('div');n.innerText=text;d.appendChild(n);
 let t=document.createElement('span');t.className='timestamp';t.innerText=(typeof time==='string'?new Date(time):time).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});d.appendChild(t);
 $('chat').appendChild(d);$('chat').scrollTop=$('chat').scrollHeight;
}

function addImage(url,type,time=new Date()){
 let d=document.createElement('div');d.className='msg '+type;
 let i=document.createElement('img');i.src=url;i.className='image-preview';i.alt='Photo';d.appendChild(i);
 let t=document.createElement('span');t.className='timestamp';t.innerText=(typeof time==='string'?new Date(time):time).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});d.appendChild(t);
 $('chat').appendChild(d);$('chat').scrollTop=$('chat').scrollHeight;
}

async function loadMemory(){
 try{
  let j=await(await fetch('/api/user')).json();
  $('chat').innerHTML='';
  (j.conversation||[]).forEach(c=>{
   if(c.user)add(c.user,'user',c.timestamp);
   if(c.image)addImage(c.image,c.user?'user':'AI',c.timestamp);
   if(c.AI)add(c.AI,'AI',c.timestamp);
  });
 }catch(e){console.log(e)}
}

async function send(){
 let text=$('msg').value.trim(),file=$('chatImage').files[0];
 if(!text&&!file)return;
 lastActivity=Date.now();
 if(text)add(text,'user');
 if(file)addImage(URL.createObjectURL(file),'user');
 $('msg').value='';$('chatImage').value='';$('send').disabled=true;
 updateTypingIndicator($('aiName').innerText||'AI');$('typing').style.display='block';
 try{
  let r;
  if(file){let f=new FormData();f.append('message',text);f.append('image',file);r=await fetch('/chat',{method:'POST',body:f})}
  else r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text})});
  let j=await r.json();
  if(!r.ok)throw Error(j.error||'Chat failed');
  add(j.reply||'AI did not reply','AI');
  if(j.image)addImage(j.image,'AI');
 }catch(e){add('AI error: '+e.message,'AI')}
 finally{$('send').disabled=false;$('typing').style.display='none';$('msg').focus()}
}

async function checkProactive(){
 if(document.visibilityState!=='visible')return;
 try{
  let j=await(await fetch('/api/proactive?last_activity='+lastActivity)).json();
  if(j.message){updateTypingIndicator($('aiName').innerText||'AI');add(j.message,'AI');if(j.image)addImage(j.image,'AI');lastActivity=Date.now()}
 }catch(e){}
}
function startProactive(){if(timer)clearInterval(timer);timer=setInterval(checkProactive,30000)}
function clearChat(){if(confirm('Clear the chat display?'))$('chat').innerHTML=''}
