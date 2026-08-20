function updateTokenProviderUI(){
 const provider=$('aiTokenProviderInput')?.value||'huggingface';const local=provider==='local';const openai=provider==='openai';const google=provider==='google';const openrouter=provider==='openrouter';
 const label=$('apiTokenLabel');if(label)label.innerText=local?'Local AI (no API key)':google?'Google AI Studio API Key':openrouter?'OpenRouter API Key':openai?'OpenAI API Token':'Hugging Face API Token';
 const token=$('hfTokenInput');if(token){token.placeholder=local?'No API key required':google?'Enter this AI\'s Google AI Studio Gemini API key':openrouter?'Enter this AI\'s OpenRouter API key':openai?'Enter this AI\'s OpenAI API token':'Enter this AI\'s Hugging Face API token';token.disabled=local;token.value=local?'':token.value}
 const localSection=$('localModelSection');if(localSection)localSection.style.display=local?'block':'none';
 const other=$('otherApiSettings');if(other)other.style.display=(openai||google||openrouter)?'block':'none';
 const link=$('tokenLink');if(link){link.style.display=local?'none':'inline-block';link.href=google?'https://aistudio.google.com/app/apikey':openrouter?'https://openrouter.ai/keys':openai?'https://platform.openai.com/api-keys':'https://huggingface.co/settings/tokens';link.innerText=google?'Create a Google AI Studio API key':openrouter?'Create an OpenRouter API key':openai?'Create an OpenAI API key':'Create a Hugging Face token'}
 const endpoint=$('apiEndpointInput');const model=$('apiModelInput');
 if(google&&endpoint&&(!endpoint.value||endpoint.value.includes('/openai/chat/completions')))endpoint.value='https://generativelanguage.googleapis.com/v1beta';
 if(openrouter&&endpoint&&(!endpoint.value||endpoint.value.includes('api.openai.com')))endpoint.value='https://openrouter.ai/api/v1/chat/completions';
 if(local){if(endpoint)endpoint.value='';if(model)model.value=model.value||'SmolLM2-1.7B-Instruct-Q3_K_M'}
 if(google&&model&&['gemini-2.5-flash','gemini-3.6-flash','gemini-3.5-flash','gemini-3.5-flash-lite','gemini-3.1-flash-lite'].includes(model.value.trim()))model.value='';
 if(endpoint)endpoint.placeholder=google?'https://generativelanguage.googleapis.com/v1beta':openrouter?'https://openrouter.ai/api/v1/chat/completions':openai?'https://api.openai.com/v1/chat/completions':local?'Not used by Local AI':'API endpoint';
 if(model)model.placeholder=google?'Leave blank to auto-select an available Gemini model':openrouter?'Select a free OpenRouter model':local?'Uploaded GGUF model':'gpt-4o-mini';
 const compatibility=$('apiCompatibilityText');if(compatibility)compatibility.innerText=local?'This AI runs its uploaded GGUF locally on the AI-Server. No external API is used.':google?'This AI uses its own Google AI Studio API key.':openrouter?'This AI uses its own OpenRouter API key and OpenRouter free-model routing.':openai?'This AI uses its own OpenAI API token.':'This AI uses its own Hugging Face API token.';
 if(local){const status=$('tokenStatus');if(status)status.innerText='Local AI selected — choose a GGUF file below.'}
 if(local)loadLocalModelStatus();
}
function setValue(id,value){const el=$(id);if(el)el.value=value??'';return el}
function setChecked(id,value){const el=$(id);if(el)el.checked=!!value;return el}
function setTelegramStatus(s){const el=$('telegramStatus');if(!el)return;if(s?.enabled){el.innerText='Telegram connected'+(s.username?' as @'+s.username:'')+'.';}else if(s?.configured){el.innerText='Telegram token configured, but the bot is not connected.';}else{el.innerText='Telegram is not connected.'}}
function setLocalModelStatus(data){const el=$('localModelStatus');if(!el)return;if(data?.configured){const mb=(Number(data.size||0)/1024/1024).toFixed(1);el.innerText=`Local model: ${data.filename} (${mb} MB)`;}else{el.innerText='No local model uploaded for this AI.'}}
async function loadLocalModelStatus(){try{const r=await fetch('/api/local-model',{credentials:'same-origin',cache:'no-store'});const data=await r.json();setLocalModelStatus(data)}catch(e){const el=$('localModelStatus');if(el)el.innerText='Could not check local model: '+e.message}}
async function uploadLocalModel(){
 const input=$('localModelInput');const file=input?.files?.[0];if(!file)return;
 if(!file.name.toLowerCase().endsWith('.gguf')){showAppNotice('Please select a .gguf model file.','Local AI');input.value='';return}
 const status=$('localModelStatus');if(status)status.innerText=`Uploading ${file.name} (${(file.size/1024/1024).toFixed(1)} MB)...`;
 try{
  const response=await fetch('/api/local-model',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/octet-stream','X-Local-Model-Name':file.name},body:file});
  const data=await response.json();if(!response.ok||!data.ok)throw new Error(data.error||`Upload failed (${response.status})`);
  setLocalModelStatus({configured:true,filename:data.filename,size:data.size});
  const provider=$('aiTokenProviderInput');if(provider)provider.value='local';updateTokenProviderUI();
  showAppNotice(`${data.filename} uploaded and Local AI is now selected.`,'Local AI');
 }catch(e){if(status)status.innerText='Upload failed: '+e.message;showAppNotice('Local model upload failed: '+e.message,'Local AI Error')}finally{input.value=''}
}
function fillSettings(s){
 s=s||{};const aiName=$('aiName');if(aiName)aiName.innerText=s.ai_name||'AI';document.title=s.ai_name||'AI';
 setValue('aiNameInput',s.ai_name||'AI');setValue('aiGenderInput',s.ai_gender||'');setValue('userNameInput',s.user_name||'');setValue('userGenderInput',s.user_gender||'');
 let provider=s.api_provider||'huggingface';if(provider==='openai_compatible')provider='openai';setValue('aiTokenProviderInput',provider);
 const providerToken=provider==='local'?'':provider==='google'?(s.google_token||s.gemini_api_key||s.api_token||s.hf_token||''):provider==='openrouter'?(s.openrouter_token||s.api_token||s.openai_token||''):provider==='openai'?(s.openai_token||s.api_token||s.hf_token||''):(s.hf_token||s.api_token||'');
 setValue('hfTokenInput',providerToken);setValue('apiEndpointInput',s.api_endpoint||'');setValue('apiModelInput',s.api_model||'');setValue('telegramBotTokenInput',s.telegram_bot_token||'');updateTokenProviderUI();
 const tokenStatus=$('tokenStatus');if(tokenStatus&&provider!=='local')tokenStatus.innerText=providerToken?'This AI has its own API token configured.':'No API token is configured for this AI.';
 setTelegramStatus({enabled:!!s.telegram_enabled,configured:!!s.telegram_bot_token,username:s.telegram_bot_username||''});
 setValue('description',s.description||'');setValue('background',s.background||'');setValue('userInfo',s.user_information||'');setValue('personality',s.personality||'');setValue('instructions',s.instructions||'');setValue('traits',(s.config?.traits||[]).join('\n'));setValue('rules',(s.config?.rules||[]).join('\n'));
 setChecked('onlineEnabled',s.features?.online_ai!==false);setChecked('learningEnabled',s.features?.learning!==false);setChecked('memoryEnabled',s.features?.long_term_memory!==false);setChecked('relevantEnabled',s.features?.relevant_memory!==false);setChecked('proactiveEnabled',s.proactive?.enabled===true);setChecked('imagesEnabled',s.features?.automatic_images===true);setChecked('proactiveImagesEnabled',s.features?.proactive_images===true);
 const accountInfo=$('accountInfo');if(accountInfo&&typeof account!=='undefined'&&account)accountInfo.innerText=(account.username||'')+' • '+(account.email||'')+' • '+(account.user_id||'');
 const avatar=$('avatar');if(avatar){if(s.profile_photo)avatar.src=s.profile_photo+'?v='+Date.now();else if(avatar.getAttribute('src')!=='')avatar.src='profile/default.png'}
 if(typeof applyBanner==='function')applyBanner(s.banner_photo||'');if(typeof updateTypingIndicator==='function')updateTypingIndicator(s.ai_name||'AI');
}
async function loadSettings(){const s=await apiGet('/api/settings');fillSettings(s);loadLocalModelStatus();return s}
function toggleSettings(){const el=$('settings');if(!el)return;el.style.display=el.style.display==='block'?'none':'block';loadSettings().catch(e=>showAppNotice('Could not load settings: '+e.message,'Error'))}
function showAppNotice(message,title='AI-Server'){const old=document.getElementById('appNoticeOverlay');if(old)old.remove();const overlay=document.createElement('div');overlay.id='appNoticeOverlay';overlay.className='app-dialog-overlay';overlay.innerHTML='<div class="app-dialog" role="dialog"><div class="app-dialog-title">'+esc(title)+'</div><div class="app-dialog-message">'+esc(message)+'</div><div class="app-dialog-actions"><button type="button" class="app-dialog-button" id="appNoticeOk">OK</button></div></div>';document.body.appendChild(overlay);const close=()=>overlay.remove();document.getElementById('appNoticeOk').onclick=close;requestAnimationFrame(()=>overlay.classList.add('visible'))}
async function connectTelegram(){
 const token=$('telegramBotTokenInput')?.value.trim()||'';if(!token){showAppNotice('Enter this AI\'s Telegram Bot Token first.','Telegram');return}
 try{await apiPost('/api/settings',{...(await apiGet('/api/settings')),telegram_bot_token:token});const result=await apiPost('/api/telegram/connect',{});setTelegramStatus(result);showAppNotice(result.username?'Telegram connected as @'+result.username+'.':'Telegram connected.','Telegram')}catch(e){showAppNotice('Telegram connection failed: '+e.message,'Telegram Error')}
}
async function disconnectTelegram(){try{const result=await apiPost('/api/telegram/disconnect',{});setTelegramStatus(result);showAppNotice('Telegram disconnected.','Telegram')}catch(e){showAppNotice('Telegram disconnect failed: '+e.message,'Telegram Error')}}
async function saveSettings(){
 const saveButton=document.querySelector('button[onclick="saveSettings()"]');const original=saveButton?.innerText;if(saveButton){saveButton.disabled=true;saveButton.innerText='Saving...'}
 try{
  let s=await apiGet('/api/settings');const provider=$('aiTokenProviderInput')?.value||'huggingface';const token=provider==='local'?'':($('hfTokenInput')?.value.trim()||'');
  s.ai_name=$('aiNameInput')?.value.trim()||'AI';s.ai_gender=$('aiGenderInput')?.value||'';s.user_name=$('userNameInput')?.value.trim()||'';s.user_gender=$('userGenderInput')?.value||'';s.api_provider=provider;s.api_token=token;
  if(provider==='local'){s.hf_token='';s.openai_token='';s.google_token='';s.openrouter_token='';s.api_endpoint='';s.api_model=s.api_model||'SmolLM2-1.7B-Instruct-Q3_K_M'}
  else {if(provider==='huggingface')s.hf_token=token;if(provider==='google')s.google_token=token;if(provider==='openrouter')s.openrouter_token=token;if(provider==='openai')s.openai_token=token;s.api_endpoint=$('apiEndpointInput')?.value.trim()||'';s.api_model=$('apiModelInput')?.value.trim()||'';}
  s.telegram_bot_token=$('telegramBotTokenInput')?.value.trim()||s.telegram_bot_token||'';s.description=$('description')?.value||'';s.background=$('background')?.value||'';s.user_information=$('userInfo')?.value||'';s.personality=$('personality')?.value||'';s.instructions=$('instructions')?.value||'';s.config=s.config||{};s.config.traits=($('traits')?.value||'').split('\n').map(x=>x.trim()).filter(Boolean);s.config.rules=($('rules')?.value||'').split('\n').map(x=>x.trim()).filter(Boolean);s.features={...(s.features||{}),online_ai:$('onlineEnabled')?.checked!==false,learning:$('learningEnabled')?.checked!==false,long_term_memory:$('memoryEnabled')?.checked!==false,relevant_memory:$('relevantEnabled')?.checked!==false,automatic_images:$('imagesEnabled')?.checked===true,proactive_images:$('proactiveImagesEnabled')?.checked===true};s.proactive={...(s.proactive||{}),enabled:$('proactiveEnabled')?.checked===true};
  const saved=await apiPost('/api/settings',s);fillSettings(saved);showAppNotice('Settings saved');
 }catch(e){console.error('saveSettings failed',e);showAppNotice('Save failed: '+e.message,'Save Error')}
 finally{if(saveButton){saveButton.disabled=false;saveButton.innerText=original||'Save Settings'}}
}
