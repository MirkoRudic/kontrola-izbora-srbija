# 5.11.2026: mandati (250 tačaka) u koloni brojčanika, za svake izbore; klik otvara veći prikaz i spisak
P='app_body.html';s=open(P).read()
def rep(o,n):
    global s; assert o in s,o[:70]; s=s.replace(o,n,1)
JS=r"""
// ---------- mandati: zvanična raspodela RIK-a (redni broj liste, mandati, skraćenica, puni naziv) ----------
const MND={
 '2026':{src:'RIK, konačni rezultati 5. 11. 2026',l:[[1,103,'SNS','Ujedinjena Srbija – Aleksandar Vučić'],[3,140,'SL','Studentska lista – Studenti pobeđuju'],[4,1,'SDP','Rasim Ljajić – Ljudski'],[5,2,'SVM','Savez vojvođanskih Mađara'],[6,1,'PZU','Usame Zukorlić – Pokret za ujedinjenje'],[10,1,'SDA','SDA – Čuvari Sandžaka'],[17,2,'AK','Albanska koalicija']]},
 '2023':{src:'RIK, izbori 17. 12. 2023',l:[[1,129,'SNS','Aleksandar Vučić – Srbija ne sme da stane'],[2,18,'SPS','Ivica Dačić – SPS, JS, Zeleni'],[5,13,'NADA','Nacionalno okupljanje – NADA'],[6,6,'SVM','Savez vojvođanskih Mađara'],[7,65,'SPN','Srbija protiv nasilja'],[8,2,'SPP','Zukorlić – SPP, DSHV'],[9,2,'SDA','SDA Sandžaka'],[13,1,'PDD','Partija za demokratsko delovanje (Kamberi)'],[14,13,'MI–GIN','Mi – glas iz naroda (Nestorović)'],[16,1,'RS','Ruska stranka']]},
 '2022':{src:'RIK, izbori 3. 4. 2022',l:[[1,120,'SNS','Aleksandar Vučić – Zajedno možemo sve'],[2,31,'SPS','Ivica Dačić – SPS, JS'],[3,5,'SVM','Savez vojvođanskih Mađara'],[5,38,'UZPS','Ujedinjeni za pobedu Srbije'],[6,15,'NADA','Nacionalno okupljanje – NADA'],[7,10,'Zav.','Zavetnici'],[8,3,'SPP','Muftijin amanet – SPP'],[9,13,'Moramo','Moramo – Akcija, Ekološki ustanak, Ne davimo Beograd'],[11,10,'Dveri–POKS','Patriotski blok – Dveri, POKS'],[12,2,'ZZV','Zajedno za Vojvodinu'],[13,2,'SDA','SDA Sandžaka'],[16,1,'KAD','Koalicija Albanaca doline']]},
 '2020':{src:'RIK, izbori 21. 6. 2020',l:[[1,188,'SNS','Aleksandar Vučić – Za našu decu'],[2,32,'SPS','Ivica Dačić – SPS, JS'],[4,9,'SVM','Savez vojvođanskih Mađara'],[5,11,'SPAS','Aleksandar Šapić – Pobeda za Srbiju'],[8,4,'SPP','Zukorlić – SPP'],[11,3,'SDA','SDA Sandžaka'],[16,3,'ADA','Albanska demokratska alternativa']]}};
const MCOLS={SNS:'#3d7ab8',SPS:'#d08a2c',SL:'#c0504d',SPN:'#d4603a',UZPS:'#d4603a',NADA:'#4a8ab0','MI–GIN':'#8c6d3f',SVM:'#3a9a6a',SPP:'#2f8f8a',PZU:'#2f8f8a',SDA:'#6aa84f',Moramo:'#9bbb3c','Dveri–POKS':'#9a4a2f','Zav.':'#7a5cad',SPAS:'#5b6b7a',ZZV:'#b0882a',KAD:'#c8457f',ADA:'#c8457f',AK:'#c8457f',PDD:'#c8457f',RS:'#a85a8a',SDP:'#5a5aa8'};const MCOL=(y,i,ab)=>MCOLS[ab]||COL26[(i-1)%COL26.length];
const SEATS=(()=>{const R=10,N=250,rs=[...Array(R)].map((_,k)=>.42+.58*k/(R-1)),T=rs.reduce((a,b)=>a+b,0);let ns=rs.map(r=>Math.round(N*r/T));ns[R-1]+=N-ns.reduce((a,b)=>a+b,0);
  const pts=[];rs.forEach((r,k)=>{for(let j=0;j<ns[k];j++){const a=Math.PI*(1-(ns[k]===1?.5:j/(ns[k]-1)));pts.push([a,100+95*r*Math.cos(a),100-95*r*Math.sin(a)])}});
  return pts.sort((p,q)=>q[0]-p[0]||0)})();
function hemiSvg(y,big){const M=MND[y];if(!M)return '';const cols=[];M.l.forEach(([i,m,ab])=>{for(let k=0;k<m;k++)cols.push(MCOL(y,i,ab))});
  return `<svg viewBox="0 0 200 104" role="img" aria-label="${esc(M.l.map(x=>x[2]+' '+x[1]).join(', '))}"${big?' class="hmb"':''}>${SEATS.map((p,k)=>`<circle cx="${p[1].toFixed(1)}" cy="${p[2].toFixed(1)}" r="2.55" fill="${cols[k]||'#ccc'}"/>`).join('')}<text x="100" y="96" text-anchor="middle" class="hmn">250</text></svg>`}
function mndBtn(){if(!MND[EL])return '';return `<button type="button" class="mnd" id="mndb" aria-label="Mandati – parlamentarni izbori ${YD[EL]}, otvori spisak">${hemiSvg(EL)}<span class="mnl">mandati ${EL}</span></button>`}
function mndOpen(){const M=MND[EL];if(!M)return;let d=document.getElementById('mndd');if(!d){d=document.createElement('dialog');d.id='mndd';d.className='mndd';document.body.appendChild(d);d.addEventListener('click',e=>{if(e.target===d||e.target.closest('[data-x]'))d.close()})}
  const L=[...M.l].sort((a,b)=>b[1]-a[1]);
  d.innerHTML=`<div class="mndi"><div class="mndh"><b>Mandati – parlamentarni izbori ${YD[EL]}</b><button type="button" class="mndx" data-x aria-label="Zatvori">✕</button></div>${hemiSvg(EL,1)}
  <ul class="mndl">${L.map(([i,m,ab,nm])=>`<li><span class="mdot" style="background:${MCOL(EL,i,ab)}"></span><b>${esc(ab)}</b><span class="mnv">${m}</span><span class="small">${esc(nm)} · lista ${i}</span></li>`).join('')}</ul>
  <div class="small">Izvor: ${esc(M.src)}. Ukupno 250 mandata; prag 3 % birača koji su glasali, za liste nacionalnih manjina prirodni prag. Raspored tačaka: liste redom sa glasačkog listića.</div></div>`;
  try{d.showModal()}catch(e){d.setAttribute('open','')}}
document.addEventListener('click',e=>{if(e.target.closest('#mndb'))mndOpen()});
"""
rep("function progHtml(mob){",JS+"function progHtml(mob){")
rep("return `<div class=\"pg pgm\">${sim}${pre}${shapes}<div class=\"cnt c3\">","return `<div class=\"pg pgm\">${sim}${pre}${shapes}${mndBtn()}<div class=\"cnt c3\">")
rep("+sim+pre+shapes+`<div class=\"pgc\">","+sim+pre+shapes+mndBtn()+`<div class=\"pgc\">")
CSS=(".mnd{font:inherit;color:var(--ink);background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:6px 8px 4px;cursor:pointer;display:flex;flex-direction:column;align-items:center;gap:0;width:100%;margin:8px 0 0}"
 ".mnd:hover{border-color:var(--accent)}.mnd svg{width:100%;max-width:220px;height:auto;display:block}.mnl{font-size:11px;color:var(--muted);letter-spacing:.04em;text-transform:uppercase}"
 ".hmn{font-size:15px;font-weight:700;fill:var(--ink)}.pgm .mnd{flex-direction:row;justify-content:center;gap:10px;margin:8px 0}.pgm .mnd svg{max-width:160px}"
 "dialog.mndd{border:1px solid var(--line);border-radius:14px;background:var(--panel);color:var(--ink);padding:0;width:min(560px,calc(100vw - 32px));max-height:calc(100vh - 32px)}dialog.mndd::backdrop{background:rgba(0,0,0,.45)}"
 ".mndi{padding:14px 16px 16px;display:flex;flex-direction:column;gap:10px}.mndh{display:flex;justify-content:space-between;align-items:center;gap:8px}.mndx{font:inherit;min-width:40px;min-height:40px;border:1px solid var(--line);border-radius:10px;background:transparent;color:var(--ink);cursor:pointer}"
 ".hmb{width:100%;height:auto}.mndl{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:6px}.mndl li{display:grid;grid-template-columns:14px auto 1fr;gap:2px 8px;align-items:center}.mndl .mnv{justify-self:end;font-variant-numeric:tabular-nums;font-weight:700}.mndl .small{grid-column:2/4}.mdot{width:12px;height:12px;border-radius:50%}")
rep("/*elx*/","/*elx*/"+CSS)
open(P,'w').write(s);print('ok')
