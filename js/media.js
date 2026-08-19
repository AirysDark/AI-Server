function applyBanner(url){
 const h=$('aiHeader');
 if(!h)return;
 h.style.backgroundImage=url?('url("'+String(url).replace(/"/g,'\\"')+'")'):'none';
}

async function uploadProfilePhoto(){
 try{
  const input=$('profilePhoto'); const status=$('profileStatus');
  const f=input?.files?.[0]; if(!f)return;
  if(status)status.innerText='Uploading...';
  const form=new FormData();form.append('file',f);
  const r=await fetch('/api/profile_photo',{method:'POST',body:form,credentials:'same-origin',cache:'no-store',headers:{'Accept':'application/json'}});
  const j=await parseResponse(r);
  const avatar=$('avatar');
  if(avatar&&j.profile_photo)avatar.src=j.profile_photo+'?v='+Date.now();
  if(status)status.innerText='Profile photo updated';
 }catch(e){const s=$('profileStatus');if(s)s.innerText='Upload failed: '+e.message;else console.error(e)}
}

async function uploadAIPhoto(){
 try{
  const input=$('aiPhoto'); const status=$('photoStatus');
  const f=input?.files?.[0];if(!f)return;
  if(status)status.innerText='Uploading...';
  const form=new FormData();form.append('file',f);
  const r=await fetch('/api/ai_photo',{method:'POST',body:form,credentials:'same-origin',cache:'no-store',headers:{'Accept':'application/json'}});
  const j=await parseResponse(r);
  if(status)status.innerText=j.image?'Photo uploaded to this AI private library.':'Photo uploaded';
 }catch(e){const s=$('photoStatus');if(s)s.innerText='Upload failed: '+e.message;else console.error(e)}
}

function compressBanner(file){return new Promise((resolve,reject)=>{const img=new Image(),reader=new FileReader();reader.onload=()=>{img.onload=()=>{const maxW=1600,maxH=500;let w=img.naturalWidth,h=img.naturalHeight;const scale=Math.min(1,maxW/w,maxH/h);w=Math.max(1,Math.round(w*scale));h=Math.max(1,Math.round(h*scale));const c=document.createElement('canvas');c.width=w;c.height=h;const ctx=c.getContext('2d');if(!ctx)return reject(Error('Could not create image canvas'));ctx.drawImage(img,0,0,w,h);resolve(c.toDataURL('image/jpeg',0.82))};img.onerror=()=>reject(Error('Could not read image'));img.src=reader.result};reader.onerror=()=>reject(Error('Could not read file'));reader.readAsDataURL(file)})}

async function saveBanner(file,statusId){
 const status=$(statusId);
 try{
  if(!file)return;
  if(status)status.innerText='Processing banner...';
  const data=await compressBanner(file);
  const s=await apiGet('/api/settings');
  s.banner_photo=data;
  const saved=await apiPost('/api/settings',s);
  applyBanner(saved.banner_photo||data);
  if(status)status.innerText='Banner updated';
 }catch(e){if(status)status.innerText='Banner upload failed: '+e.message;else console.error(e)}
}
function uploadBanner(){const f=$('bannerPhoto')?.files?.[0];saveBanner(f,'bannerStatus')}
function uploadBannerSettings(){const f=$('bannerPhotoSettings')?.files?.[0];saveBanner(f,'bannerStatus')}
