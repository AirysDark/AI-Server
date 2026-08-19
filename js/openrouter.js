(function(){
 const OPENROUTER_ENDPOINT='https://openrouter.ai/api/v1/chat/completions';
 const OPENROUTER_MODELS='https://openrouter.ai/api/v1/models';
 let baseUpdate=window.updateTokenProviderUI;
 let baseFill=window.fillSettings;
 let freeModels=[];
 function provider(){return document.getElementById('aiTokenProviderInput')?.value||'huggingface'}
 function ensureLocalOption(){
  const sel=document.getElementById('aiTokenProviderInput');if(!sel)return;
  if(!Array.from(sel.options).some(o=>o.value==='local')){const o=document.createElement('option');o.value='local';o.textContent='Local AI (SmolLM2)';sel.appendChild(o)}
 }
 function modelControl(){return document.getElementById('apiModelInput')}
 function setModelControl(models,current){
  const old=modelControl();if(!old)return;
  const select=document.createElement('select');select.id='apiModelInput';select.className=old.className||'input';select.setAttribute('aria-label','OpenRouter model');
  const list=models.slice();if(current&&!list.some(x=>x.id===current))list.unshift({id:current,name:current,deprecated:false});
  list.forEach(m=>{const o=document.createElement('option');o.value=m.id;o.textContent=(m.name||m.id)+(m.id.endsWith(':free')?' (free)':'');select.appendChild(o)});
  if(!list.length){const o=document.createElement('option');o.value=current||'openrouter/free';o.textContent=current||'openrouter/free';select.appendChild(o)}
  select.value=current||list[0]?.id||'openrouter/free';old.replaceWith(select);
 }
 async function loadFreeModels(current){
  try{
   const response=await fetch(OPENROUTER_MODELS,{cache:'no-store'});if(!response.ok)throw new Error('OpenRouter model catalog returned '+response.status);
   const data=await response.json();
   freeModels=(data.data||[]).filter(m=>m&&m.id&&m.pricing&&String(m.pricing.prompt)==='0'&&String(m.pricing.completion)==='0'&&!m.id.includes('embedding')&&!m.id.includes('rerank')&&!m.id.includes('transcription')).sort((a,b)=>(a.name||a.id).localeCompare(b.name||b.id));
   if(!freeModels.some(m=>m.id==='openrouter/free'))freeModels.unshift({id:'openrouter/free',name:'Free Models Router'});
   setModelControl(freeModels,current);
   const status=document.getElementById('tokenStatus');if(status)status.textContent=freeModels.length+' free OpenRouter models available.';
  }catch(e){
   setModelControl([{id:'openrouter/free',name:'Free Models Router'}],current||'openrouter/free');
   const status=document.getElementById('tokenStatus');if(status)status.textContent='Could not load OpenRouter model list; Free Models Router is available.';
   console.error('OpenRouter model catalog:',e);
  }
 }
 window.updateTokenProviderUI=function(){
  ensureLocalOption();
  const p=provider();
  if(p==='local'){
   const label=document.getElementById('apiTokenLabel');if(label)label.textContent='Local AI Model';
   const token=document.getElementById('hfTokenInput');if(token){token.value='';token.placeholder='Uses the server-local SmolLM2 model';token.disabled=true}
   const other=document.getElementById('otherApiSettings');if(other)other.style.display='none';
   const link=document.getElementById('tokenLink');if(link){link.removeAttribute('href');link.textContent='Local model — no API key required'}
   const endpoint=document.getElementById('apiEndpointInput');if(endpoint)endpoint.value='';
   const model=document.getElementById('apiModelInput');if(model)model.value='SmolLM2-1.7B-Instruct-Q4_K_M';
   const compatibility=document.getElementById('apiCompatibilityText');if(compatibility)compatibility.textContent='Forced local AI. This AI will use the server-local SmolLM2 model and never call an external API.';
   const status=document.getElementById('tokenStatus');if(status)status.textContent='Local AI enabled — no API token is used.';
   return;
  }
  const token=document.getElementById('hfTokenInput');if(token)token.disabled=false;
  if(p==='openrouter'){
   const label=document.getElementById('apiTokenLabel');if(label)label.textContent='OpenRouter API Key';
   if(token)token.placeholder='Enter this AI\'s OpenRouter API key';
   const other=document.getElementById('otherApiSettings');if(other)other.style.display='block';
   const link=document.getElementById('tokenLink');if(link){link.href='https://openrouter.ai/keys';link.textContent='Create an OpenRouter API key'}
   const endpoint=document.getElementById('apiEndpointInput');if(endpoint){if(!endpoint.value||endpoint.value.includes('api.openai.com'))endpoint.value=OPENROUTER_ENDPOINT;endpoint.placeholder=OPENROUTER_ENDPOINT}
   const compatibility=document.getElementById('apiCompatibilityText');if(compatibility)compatibility.textContent='OpenRouter API — OpenAI-compatible. Free models can be selected below.';
   const current=document.getElementById('apiModelInput')?.value||'openrouter/free';setModelControl(freeModels,current);loadFreeModels(current);return;
  }
  if(typeof baseUpdate==='function')baseUpdate();
 }
 window.fillSettings=function(s){
  ensureLocalOption();
  const data=Object.assign({},s||{});
  if(data.api_provider==='openrouter'){
   data.openai_token=data.openrouter_token||data.api_token||data.openai_token||'';data.api_provider='openrouter';data.api_endpoint=data.api_endpoint||OPENROUTER_ENDPOINT;data.api_model=data.api_model||'openrouter/free';
  }
  if(typeof baseFill==='function')baseFill(data);
  const sel=document.getElementById('aiTokenProviderInput');
  if((s||{}).api_provider==='openrouter'){
   if(sel)sel.value='openrouter';const token=document.getElementById('hfTokenInput');if(token)token.value=s.openrouter_token||s.api_token||s.openai_token||'';window.updateTokenProviderUI();
  }else if((s||{}).api_provider==='local'){
   if(sel)sel.value='local';window.updateTokenProviderUI();
  }
 }
 window.addEventListener('load',function(){ensureLocalOption();if(provider()==='openrouter'||provider()==='local')window.updateTokenProviderUI()});
})();
