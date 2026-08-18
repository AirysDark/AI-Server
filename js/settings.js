function fillSettings(s){
 $('aiName').innerText=s.ai_name||'AI';
 document.title=s.ai_name||'AI';
 $('aiNameInput').value=s.ai_name||'AI';
 $('aiGenderInput').value=s.ai_gender||'';
 $('userNameInput').value=s.user_name||'';
 $('userGenderInput').value=s.user_gender||'';
 $('hfTokenInput').value=s.hf_token||'';
 $('tokenStatus').innerText=s.hf_token?'This AI is using its own token.':'This AI is using the server default token.';
 $('description').value=s.description||'';
 $('background').value=s.background||'';
 $('userInfo').value=s.user_information||'';
 $('personality').value=s.personality||'';
 $('instructions').value=s.instructions||'';
 $('traits').value=(s.config?.traits||[]).join('\n');
 $('rules').value=(s.config?.rules||[]).join('\n');
 $('onlineEnabled').checked=s.features?.online_ai!==false;
 $('learningEnabled').checked=s.features?.learning!==false;
 $('memoryEnabled').checked=s.features?.long_term_memory!==false;
 $('relevantEnabled').checked=s.features?.relevant_memory!==false;
 $('proactiveEnabled').checked=s.proactive?.enabled===true;
 $('imagesEnabled').checked=s.features?.automatic_images===true;
 $('proactiveImagesEnabled').checked=s.features?.proactive_images===true;
 $('accountInfo').innerText=(account.username||'')+' • '+(account.email||'')+' • '+(account.user_id||'');
 if(s.profile_photo)$('avatar').src=s.profile_photo+'?v='+Date.now();else $('avatar').src='profile/default.png';
 applyBanner(s.banner_photo||'');
 updateTypingIndicator(s.ai_name||'AI');
}

async function loadSettings(){let s=await(await fetch('/api/settings')).json();fillSettings(s)}
function toggleSettings(){$('settings').style.display=$('settings').style.display==='block'?'none':'block';loadSettings()}

async function saveSettings(){
 let s=await(await fetch('/api/settings')).json();
 s.ai_name=$('aiNameInput').value.trim()||'AI';
 s.ai_gender=$('aiGenderInput').value;
 s.user_name=$('userNameInput').value.trim();
 s.user_gender=$('userGenderInput').value;
 s.hf_token=$('hfTokenInput').value.trim();
 s.description=$('description').value;
 s.background=$('background').value;
 s.user_information=$('userInfo').value;
 s.personality=$('personality').value;
 s.instructions=$('instructions').value;
 s.config=s.config||{};
 s.config.traits=$('traits').value.split('\n').map(x=>x.trim()).filter(Boolean);
 s.config.rules=$('rules').value.split('\n').map(x=>x.trim()).filter(Boolean);
 s.features={...(s.features||{}),online_ai:$('onlineEnabled').checked,learning:$('learningEnabled').checked,long_term_memory:$('memoryEnabled').checked,relevant_memory:$('relevantEnabled').checked,automatic_images:$('imagesEnabled').checked,proactive_images:$('proactiveImagesEnabled').checked};
 s.proactive={...(s.proactive||{}),enabled:$('proactiveEnabled').checked};
 let saved=await post('/api/settings',s);
 fillSettings(saved);
 alert('Settings saved');
}
