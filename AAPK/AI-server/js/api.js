const $=id=>document.getElementById(id);

async function apiGet(path){
 const r=await fetch(path,{credentials:'same-origin'});
 const j=await r.json();
 if(!r.ok)throw Error(j.error||'Request failed');
 return j;
}

async function apiPost(path,data){
 const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify(data)});
 const j=await r.json();
 if(!r.ok)throw Error(j.error||'Request failed');
 return j;
}

async function post(path,data){return apiPost(path,data)}
