function applyBanner(url){
 const h=$('aiHeader');
 if(url)h.style.backgroundImage='url("'+url.replace(/"/g,'\\"')+'")';
 else h.style.backgroundImage='none';
}

async function uploadProfilePhoto(){
 try{
  let f=$('profilePhoto').files[0];if(!f)return;
  let form=new FormData();form.append('file',f);
  let r=await fetch('/api/profile_photo',{method:'POST',body:form});let j=await r.json();
  if(!r.ok)throw Error(j.error||'Upload failed');
  $('avatar').src=j.profile_photo+'?v='+Date.now();$('profileStatus').innerText='Profile photo updated';
 }catch(e){$('profileStatus').innerText=e.message}
}

async function uploadAIPhoto(){
 try{
  let f=$('aiPhoto').files[0];if(!f)return;
  let form=new FormData();form.append('file',f);
  let r=await fetch('/api/ai_photo',{method:'POST',body:form});let j=await r.json();
  $('photoStatus').innerText=r.ok?'Photo uploaded to this AI private library.':(j.error||'Upload failed');
 }catch(e){$('photoStatus').innerText=e.message}
}

function compressBanner(file){return new Promise((resolve,reject)=>{const img=new Image();const reader=new FileReader();reader.onload=()=>{img.onload=()=>{const maxW=1600,maxH=500;let w=img.naturalWidth,h=img.naturalHeight;const scale=Math.min(1,maxW/w,maxH/h);w=Math.max(1,Math.round(w*scale));h=Math.max(1,Math.round(h*scale));const c=document.createElement('canvas');c.width=w;c.height=h;const ctx=c.getContext('2d');ctx.drawImage(img,0,0,w,h);resolve(c.toDataURL('image/jpeg',0.82))};img.onerror=()=>reject(Error('Could not read image'));img.src=reader.result};reader.onerror=()=>reject(Error('Could not read file'));reader.readAsDataURL(file)})}

async function saveBanner(file,statusId){
 try{
  if(!file)return;$(statusId).innerText='Processing banner...';
  const data=await compressBanner(file);let s=await(await fetch('/api/settings')).json();s.banner_photo=data;
  let saved=await post('/api/settings',s);applyBanner(saved.banner_photo||data);$(statusId).innerText='Banner updated';
 }catch(e){$(statusId).innerText='Banner upload failed: '+e.message}
}
function uploadBanner(){const f=$('bannerPhoto').files[0];saveBanner(f,'bannerStatus')}
function uploadBannerSettings(){const f=$('bannerPhotoSettings').files[0];saveBanner(f,'bannerStatus')}
