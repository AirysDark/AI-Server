function updateTokenProviderUI(){
 const provider=$('aiTokenProviderInput')?.value||'huggingface';
 const openai=provider==='openai';
 const label=$('apiTokenLabel'); if(label)label.innerText=openai?'OpenAI API Token':'Hugging Face API Token';
 const token=$('hfTokenInput'); if(token)token.placeholder=openai?'Enter the OpenAI API token':'Leave blank to use the server default token';
 const other=$('otherApiSettings'); if(other)other.style.display=openai?'block':'none';
 const link=$('tokenLink'); if(link){link.href=openai?'https://platform.openai.com/api-keys':'https://huggingface.co/settings/tokens';link.innerText=openai?'Create an OpenAI API key':'Create a Hugging Face token'}
 const endpoint=$('apiEndpointInput'); if(endpoint)endpoint.placeholder=openai?'https://api.openai.com/v1/chat/completions':'API endpoint';
 const model=$('apiModelInput'); if(model)model.placeholder=openai?'gpt-4o-mini':'Model name';
 const compatibility=$('apiCompatibilityText'); if(compatibility)compatibility.innerText=openai?'OpenAI API is supported through the server API adapter.':'Compatible with other AI APIs.';
}

function setValue(id,value){const el=$(id);if(el)el.value=value??'';return el}
function setChecked(id,value){const el=$(id);if(el)el.checked=!!value;return el}

function fillSettings(s){
 s=s||{};
 const aiName=$('aiName'); if(aiName)aiName.innerText=s.ai_name||'AI';
 document.title=s.ai_name||'AI';
 setValue('aiNameInput',s.ai_name||'AI');
 setValue('aiGenderInput',s.ai_gender||'');
 setValue('userNameInput',s.user_name||'');
 setValue('userGenderInput',s.user_gender||'');
 let provider=s.api_provider||'huggingface';
 if(provider==='openai_compatible')provider='openai';
 setValue('aiTokenProviderInput',provider);
 setValue('hfTokenInput',s.hf_token||'');
 setValue('apiEndpointInput',s.api_endpoint||'');
 setValue('apiModelInput',s.api_model||'');
 updateTokenProviderUI();
 const tokenStatus=$('tokenStatus'); if(tokenStatus)tokenStatus.innerText=s.hf_token?'This AI is using its own API token.':'This AI is using the server default API token.';
 setValue('description',s.description||'');
 setValue('background',s.background||'');
 setValue('userInfo',s.user_information||'');
 setValue('personality',s.personality||'');
 setValue('instructions',s.instructions||'');
 setValue('traits',(s.config?.traits||[]).join('\n'));
 setValue('rules',(s.config?.rules||[]).join('\n'));
 setChecked('onlineEnabled',s.features?.online_ai!==false);
 setChecked('learningEnabled',s.features?.learning!==false);
 setChecked('memoryEnabled',s.features?.long_term_memory!==false);
 setChecked('relevantEnabled',s.features?.relevant_memory!==false);
 setChecked('proactiveEnabled',s.proactive?.enabled===true);
 setChecked('imagesEnabled',s.features?.automatic_images===true);
 setChecked('proactiveImagesEnabled',s.features?.proactive_images===true);
 const accountInfo=$('accountInfo'); if(accountInfo&&typeof account!=='undefined'&&account)accountInfo.innerText=(account.username||'')+' • '+(account.email||'')+' • '+(account.user_id||'');
 const avatar=$('avatar'); if(avatar){if(s.profile_photo)avatar.src=s.profile_photo+'?v='+Date.now();else avatar.src='profile/default.png'}
 if(typeof applyBanner==='function')applyBanner(s.banner_photo||'');
 if(typeof updateTypingIndicator==='function')updateTypingIndicator(s.ai_name||'AI');
}

async function loadSettings(){let s=await(await fetch('/api/settings',{credentials:'same-origin',cache:'no-store'})).json();if(!s||s.error)throw Error(s?.error||'Could not load AI settings');fillSettings(s);return s}
function toggleSettings(){const el=$('settings');if(!el)return;el.style.display=el.style.display==='block'?'none':'block';loadSettings()}

function showAppNotice(message,title='AI-Server'){
 const old=document.getElementById('appNoticeOverlay');
 if(old)old.remove();
 const overlay=document.createElement('div');
 overlay.id='appNoticeOverlay';
 overlay.className='app-dialog-overlay';
 overlay.innerHTML='<div class="app-dialog" role="dialog" aria-modal="true" aria-labelledby="appNoticeTitle">'+
   '<div class="app-dialog-title" id="appNoticeTitle">'+esc(title)+'</div>'+
   '<div class="app-dialog-message">'+esc(message)+'</div>'+ 
   '<div class="app-dialog-actions"><button type="button" class="app-dialog-button" id="appNoticeOk">OK</button></div>'+ 
   '</div>';
 document.body.appendChild(overlay);
 const close=()=>{overlay.classList.remove('visible');setTimeout(()=>overlay.remove(),140)};
 document.getElementById('appNoticeOk').onclick=close;
 overlay.addEventListener('click',e=>{if(e.target===overlay)close()});
 const keyHandler=e=>{if(e.key==='Escape'||e.key==='Enter'){e.preventDefault();close();document.removeEventListener('keydown',keyHandler)}};
 document.addEventListener('keydown',keyHandler);
 requestAnimationFrame(()=>overlay.classList.add('visible'));
 setTimeout(()=>document.getElementById('appNoticeOk')?.focus(),50);
}

async function saveSettings(){
 let s=await(await fetch('/api/settings',{credentials:'same-origin',cache:'no-store'})).json();
 if(!s||s.error)throw Error(s?.error||'Could not load AI settings');
 s.ai_name=$('aiNameInput')?.value.trim()||'AI';
 s.ai_gender=$('aiGenderInput')?.value||'';
 s.user_name=$('userNameInput')?.value.trim()||'';
 s.user_gender=$('userGenderInput')?.value||'';
 s.api_provider=$('aiTokenProviderInput')?.value||'huggingface';
 s.hf_token=$('hfTokenInput')?.value.trim()||'';
 s.api_endpoint=$('apiEndpointInput')?.value.trim()||'';
 s.api_model=$('apiModelInput')?.value.trim()||'';
 s.description=$('description')?.value||'';
 s.background=$('background')?.value||'';
 s.user_information=$('userInfo')?.value||'';
 s.personality=$('personality')?.value||'';
 s.instructions=$('instructions')?.value||'';
 s.config=s.config||{};
 s.config.traits=($('traits')?.value||'').split('\n').map(x=>x.trim()).filter(Boolean);
 s.config.rules=($('rules')?.value||'').split('\n').map(x=>x.trim()).filter(Boolean);
 s.features={...(s.features||{}),online_ai:$('onlineEnabled')?.checked!==false,learning:$('learningEnabled')?.checked!==false,long_term_memory:$('memoryEnabled')?.checked!==false,relevant_memory:$('relevantEnabled')?.checked!==false,automatic_images:$('imagesEnabled')?.checked===true,proactive_images:$('proactiveImagesEnabled')?.checked===true};
 s.proactive={...(s.proactive||{}),enabled:$('proactiveEnabled')?.checked===true};
 let saved=await post('/api/settings',s);
 fillSettings(saved);
 showAppNotice('Settings saved');
}
