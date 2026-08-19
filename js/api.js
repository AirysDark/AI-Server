const $=id=>document.getElementById(id);

async function parseResponse(r){
 const text=await r.text();
 let j=null;
 try{j=text?JSON.parse(text):{};}catch(e){
  const preview=text.replace(/\s+/g,' ').slice(0,160);
  throw Error(r.ok?'Server returned invalid JSON'+(preview?' ('+preview+')':''):'Server error '+r.status+(preview?' ('+preview+')':''));
 }
 if(!r.ok)throw Error(j?.error||j?.message||('Request failed ('+r.status+')'));
 return j;
}

async function apiGet(path){return parseResponse(await fetch(path,{credentials:'same-origin',cache:'no-store',headers:{'Accept':'application/json'}}))}
async function apiPost(path,data){return parseResponse(await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','Accept':'application/json'},credentials:'same-origin',cache:'no-store',body:JSON.stringify(data)}))}
async function post(path,data){return apiPost(path,data)}
