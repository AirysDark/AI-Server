const $=id=>document.getElementById(id);

async function post(path,data){
 const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
 const j=await r.json();
 if(!r.ok)throw Error(j.error||'Request failed');
 return j;
}
