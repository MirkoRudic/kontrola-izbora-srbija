# 4.11.2026: izbor izbora u zaglavlju (A), izbori u adresi (D); "kroz izbore" prebacuje celu aplikaciju (C)
import re
P='app_body.html'; s=open(P).read()
def rep(old,new,cnt=1):
    global s
    assert s.count(old)>=1, old[:80]
    s=s.replace(old,new,cnt)
# --- zaglavlje
rep('<span class="sub">Parlamentarni izbori 25. 10. 2026</span>',
    '<span class="sub elw" id="elw"><label class="elb"><span class="vh">Izbori</span><select id="elsel" aria-label="Izbori"></select></label><label class="elc"><span>uporedi sa</span><select id="cmpsel" aria-label="Uporedi sa"></select></label></span>')
rep('</style>\n\n<div class="wrap">',
    '/*elx*/.elw{display:flex;flex-wrap:wrap;gap:6px 12px;align-items:center;margin-top:2px}.elw select{font:inherit;color:var(--ink);background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:5px 26px 5px 9px;min-height:36px;cursor:pointer;-webkit-appearance:none;appearance:none;background-image:linear-gradient(45deg,transparent 50%,currentColor 50%),linear-gradient(135deg,currentColor 50%,transparent 50%);background-position:calc(100% - 13px) 50%,calc(100% - 8px) 50%;background-size:5px 5px;background-repeat:no-repeat}.elw .elb select{font-weight:600;border-color:var(--accent)}.elw .elc{display:flex;align-items:center;gap:6px;color:var(--muted);font-size:13px}.vh{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}.elw.old .elb select{background-color:color-mix(in srgb,var(--accent) 12%,var(--panel))}@media (max-width:520px){.elw select{font-size:13.5px;min-height:40px}.elw .elb{flex:1 1 100%}.elw .elb select{width:100%}}\n</style>\n\n<div class="wrap">')
# --- stanje i pomoćne funkcije (posle OLDY/YRS)
rep("const sumK=(arr,k)=>",
r"""let EL='2026',CMP='2023';
const YD={'2026':'25. 10. 2026','2023':'17. 12. 2023','2022':'3. 4. 2022','2020':'21. 6. 2020'};
const objY=(r,y)=>!r?null:y==='2026'?r.z:y==='2023'?r.y:y==='2022'?r.y22:y==='2020'?r.y20:null;
const S22=["SNS","SPS","SVM","Šešelj – SRS","Ujedinjeni (UZPS)","NADA","Zavetnici","Zukorlić – SPP","Moramo","Suverenisti","Dveri – POKS","Vojvođani","SDA Sandžaka","Tadić – SDS","Alb. dem. alternativa","Koalicija Albanaca doline","Otete bebe","Romska partija","Ruski manjinski savez"];
const S20=["SNS","SPS","Šešelj – SRS","SVM","Šapić – SPAS","POKS","Ujedinjena dem. Srbija","Zukorlić – SPP","Metla 2020","Stamatović – Zdrava Srbija","SDA Sandžaka","Zavetnici","Narodni blok (Ilić)","PSG (Trifunović)","Suverenisti","Alb. dem. alternativa","1 od 5 miliona","Nek maske padnu","Ruska stranka","Č. Jovanović – LDP","Levijatan"];
const SN=y=>y==='2026'?S26:y==='2023'?S23:y==='2022'?S22:S20;
const PK={SNS:{2026:1,2023:1,2022:1,2020:1},SPS:{2026:2,2023:2,2022:2,2020:2},SVM:{2026:5,2023:6,2022:3,2020:4},SRS:{2023:3,2022:4,2020:3},SPP:{2026:6,2023:8,2022:8,2020:8},SDA:{2026:10,2023:9,2022:13,2020:11},ZAV:{2023:4,2022:7,2020:12},NADA:{2023:5,2022:6},RUS:{2026:7,2023:16,2020:19},SUV:{2022:10,2020:15}};
const pkOf=(y,i)=>{for(const k in PK)if(PK[k][y]===i)return k;return null};
function setEL(y,c){EL=y;if(c!==undefined)CMP=c;if(CMP===EL)CMP=EL==='2026'?'2023':'2026';btab=EL;if(EL==='2026'||EL==='2023'){PT=EL;OT=EL}elUI()}
function elUI(){const a=document.getElementById('elsel'),b=document.getElementById('cmpsel'),w=document.getElementById('elw');if(!a||!IDX)return;
  a.innerHTML=YRS().map(y=>`<option value="${y}"${y===EL?' selected':''}>Parlamentarni izbori ${YD[y]}</option>`).join('');
  b.innerHTML=YRS().filter(y=>y!==EL).concat(['nema']).map(y=>`<option value="${y}"${y===CMP?' selected':''}>${y==='nema'?'bez poređenja':y}</option>`).join('');
  w.classList.toggle('old',EL!=='2026')}
const sumK=(arr,k)=>""")
# --- opšti prikaz rezultata za bilo koji par izbora
rep("function results(r,notes){\n",
r"""function resultsG(r,notes){
  const A=objY(r,EL),two=CMP!=='nema',B=two?objY(r,CMP):null,r2={z:A,y:B,partial:false};
  const H=`<thead><tr><th></th><th class="n">${EL}</th>${two?`<th class="n">${CMP}</th><th class="n">Razlika</th>`:''}</tr></thead>`;
  const rw=(label,key,base,sub,good,iB,iA)=>{if(two)return row(label,key,base,r2,sub,good,iB,iA);const v=A?(key==='list'?A.lists[iA]:A[key]):null;return `<tr><th scope="row">${label}${sub?`<small class="rs">${sub}</small>`:''}</th>${cell(v,A&&base?A[base]:null)}</tr>`};
  let lr='';
  if(A&&A.lists){const idx=[1,2];A.lists.map((v,i)=>[v||0,i+1]).sort((p,q)=>q[0]-p[0]).forEach(([v,i])=>{if(idx.length<5&&!idx.includes(i)&&v>0)idx.push(i)});
    lr=idx.map(i=>{const k=pkOf(EL,i),j=k&&two?PK[k][CMP]:null;return rw(esc(SN(EL)[i-1]),'list','valid',`lista ${i}${j&&j!==i?` · ${CMP}: lista ${j}`:''}`,k==='SNS'||k==='SPS'?-1:0,j?j-1:-1,i-1)}).join('')}
  const miss=!A?`<div class="note">Nema podataka za izbore ${YD[EL]}${ST.sid?' za ovo BM (novo BM ili nije povezano sa tadašnjim BM)':''}.</div>`:(two&&!B?`<div class="small" style="margin-bottom:6px">Za izbore ${YD[CMP]} nema podataka${ST.sid?' za ovo BM':''}.</div>`:'');
  const old=[EL,CMP].some(y=>y==='2022'||y==='2020')?`<div class="small" style="margin-top:6px">Za 2022. i 2020. RIK nema rezultate po biračkim mestima; brojevi su pročitani iz zapisnika biračkih odbora${A&&A.pr?(ST.sid?'. Zbir glasova lista se ne slaže sa brojem važećih listića'+(A.gz?' već u samom zapisniku (greška biračkog odbora)':''):`. Za ${fmt(A.pr)} BM zbir glasova u zapisniku se ne slaže sa brojem važećih listića`):''}.${A&&A.nap&&ST.sid?' Napomena čitanja: '+esc(A.nap):''}</div>`:'';
  const pon=two?'<div class="small" style="margin-top:4px">Liste se porede samo kad je ista stranka nastupila i na drugim izborima (SNS, SPS, SVM, SRS, SPP, SDA…); koalicije se razlikuju od izbora do izbora.</div>':'';
  return `<div class="sec"><h3>Rezultati – parlamentarni izbori ${YD[EL]}</h3>${miss}${lr?`<div class="tbl"><table class="res cmp">${H}<tbody>${lr}</tbody></table></div>`:''}${old}${pon}
  <div class="mrow"><button class="more" id="more">DETALJNO</button></div></div></div>
  <div class="sec"><div class="tbl tbl2"><table class="res cmp">${H}<tbody>
    ${rw('Upisani birači','voters',null)}
    ${rw('Izašlo','out','voters','',1)}
    ${rw('Važeći listići','valid','out')}
    ${rw('Nevažeći listići','invalid','out')}
  </tbody></table></div>
  ${notes?`<div class="foot1">${notes}</div>`:''}<div class="mrow btnrow">${dnBtn}${bibBtn}${shBtn}</div></div>`}
function results(r,notes){
  if(EL!=='2026'||CMP!=='2023')return resultsG(r,notes);
""")
# --- brojčanik dve najjače liste za izabrane izbore; obrada (RIK/zapisnici) samo za 2026
rep("function top2Html(z){if(!z||!z.valid||!z.lists)return t2Wait();",
    "function top2Html(z){const NM=SN(EL);if(EL!=='2026'){z=objY(_CR,EL);if(!z||!z.valid)return `<div class=\"t2 t2e\"><span>Nema podataka</span><span>za ${EL}.</span></div>`}if(!z||!z.valid||!z.lists)return t2Wait();")
rep("aria-label=\"${t.map(x=>esc(S26[x.i-1])+' '+pc(x.v)).join(', ')}\"","aria-label=\"${t.map(x=>esc(NM[x.i-1])+' '+pc(x.v)).join(', ')}\"")
rep("background:${COL26[x.i-1]}\"></div></div><div class=\"t2l\"><b title=\"${esc(S26[x.i-1])}\">${x.i===3?'SL':esc(S26[x.i-1])}</b>",
    "background:${EL==='2026'?COL26[x.i-1]:({SNS:COL26[0],SPS:COL26[1]})[pkOf(EL,x.i)]||COL26[(x.i+2)%COL26.length]}\"></div></div><div class=\"t2l\"><b title=\"${esc(NM[x.i-1])}\">${EL==='2026'&&x.i===3?'SL':esc(NM[x.i-1].split(/ – | \\(/)[0])}</b>")
rep("const shapes=`<div class=\"pgs\">${top2Html(_CR&&_CR.z)}${shpHtml(",
    "const shapes=EL!=='2026'?`<div class=\"pgs\">${top2Html(_CR&&_CR.z)}<div class=\"small\" style=\"align-self:center;padding:8px\">Parlamentarni izbori ${YD[EL]}.<br>Obrada RIK-a i zapisnika ispod važi za 2026.</div></div>`:`<div class=\"pgs\">${top2Html(_CR&&_CR.z)}${shpHtml(")
# --- tabele opština/regiona i BM: kolone za izabrane izbore
rep("""function kidsTable(rows,head){return `<div class="sec"><h3>${head}</h3><div class="tbl"><table class="kids"><thead><tr><th>Naziv</th><th class="n" style="text-align:right">BM</th><th class="n" style="text-align:right">Izašlo 2026</th><th class="n" style="text-align:right">2023</th></tr></thead><tbody>""",
"""function kidsTable(rows,head){if(EL!=='2026'||CMP!=='2023')return kidsTableG(rows,head);return `<div class="sec"><h3>${head}</h3><div class="tbl"><table class="kids"><thead><tr><th>Naziv</th><th class="n" style="text-align:right">BM</th><th class="n" style="text-align:right">Izašlo 2026</th><th class="n" style="text-align:right">2023</th></tr></thead><tbody>""")
rep("function curCnt(){",
r"""function kidsTableG(rows,head){const two=CMP!=='nema',iz=o=>o&&o.voters?pct(o.out,o.voters):'<span class="dim">—</span>';
  return `<div class="sec"><h3>${head}</h3><div class="tbl"><table class="kids"><thead><tr><th>Naziv</th><th class="n" style="text-align:right">BM</th><th class="n" style="text-align:right">Izašlo ${EL}</th>${two?`<th class="n" style="text-align:right">${CMP}</th>`:''}</tr></thead><tbody>
  ${rows.map(r=>`<tr data-k="${esc(r.k)}"><td class="nm" title="${esc(r.name)}">${esc(r.name)}</td><td class="n">${fmt(r.n)}</td><td class="n">${iz(objY(r,EL))}</td>${two?`<td class="n">${iz(objY(r,CMP))}</td>`:''}</tr>`).join('')}</tbody></table></div></div>`}
function curCnt(){""")
rep("return {k:'r:'+g.id,name:RLAB[g.name]||g.name,n:x.n,y:x.y,z:x.z,done:x.done,",
    "return {k:'r:'+g.id,name:RLAB[g.name]||g.name,n:x.n,y:x.y,y22:x.y22,y20:x.y20,z:x.z,done:x.done,")
rep("return {k:'u:'+id,name:u.short,n:u.nbm,y:u.y23,z:x.z,done:x.done,",
    "return {k:'u:'+id,name:u.short,n:u.nbm,y:u.y23,y22:x.y22,y20:x.y20,z:x.z,done:x.done,")
# spisak BM u opštini
rep("""<th class="n" style="text-align:right">Izašlo 2026</th><th class="n" style="text-align:right">2023</th></tr></thead><tbody>
        ${fl.map(s=>{""",
"""<th class="n" style="text-align:right">Izašlo ${EL}</th>${CMP!=='nema'?`<th class="n" style="text-align:right">${CMP}</th>`:''}</tr></thead><tbody>
        ${fl.map(s=>{const iz=o=>o&&o.voters?pct(o.out,o.voters):'<span class="dim">—</span>',sr={z:zOf(liveBM(ST.uid,s.sid)),y:s.y23,y22:s.y22,y20:s.y20};if(EL!=='2026'||CMP!=='2023'){const g=sigOf(ST.uid,s.sid),mk=(g.p?' <b style="color:var(--org)">P</b>':'')+(g.ne.length?' <b style="color:var(--bad)">!</b>':'')+(g.x?' <b style="color:var(--bad)">✕</b>':'');return `<tr data-k="s:${s.sid}"><td class="nm" title="${esc(s.name)}"><b>${s.n}</b> ${esc(s.name)}${mk}</td><td class="n">${iz(objY(sr,EL))}</td>${CMP!=='nema'?`<td class="n">${iz(objY(sr,CMP))}</td>`:''}</tr>`}""")
# --- kroz izbore: klik prebacuje celu aplikaciju
rep("P.querySelectorAll('button.kroz[data-b]').forEach(b=>b.onclick=()=>{btab=b.dataset.b;ST.view='ballot';render()});",
    "P.querySelectorAll('button.kroz[data-b]').forEach(b=>b.onclick=()=>{setEL(b.dataset.b);ST.view='main';render._keep=true;render();renderCol();setHash()});")
rep("return `<li><button type=\"button\" class=\"kroz\" data-b=\"${y}\">","return `<li><button type=\"button\" class=\"kroz${y===EL?' on':''}\" data-b=\"${y}\" aria-pressed=\"${y===EL}\">")
rep("button.kroz .small{grid-column:2}","button.kroz .small{grid-column:2}button.kroz.on{border:2px solid var(--accent);background:color-mix(in srgb,var(--accent) 12%,var(--panel))}")
rep("return `<div class=\"sec\"><h3>Ovo BM kroz izbore</h3><ul class=\"kroz\">${li}</ul></div>`}",
    "return `<div class=\"sec\"><h3>Ovo BM kroz izbore</h3><ul class=\"kroz\">${li}</ul><div class=\"small\" style=\"margin-top:6px\">Klik na godinu prebacuje celu aplikaciju na te izbore.</div></div>`}")
# --- adresa: #2022~2023/o1-bm1
rep("function setHash(){let h='';setHash._h=null;",
    "function setHash(){let h='';setHash._h=null;const yp=EL!=='2026'||CMP!=='2023'?EL+(CMP!=='2023'?'~'+CMP:''):'';")
rep("  setHash._h=h?'#'+h:'';try{",
    "  if(yp)h=yp+(h?'/'+h:'');setHash._h=h?'#'+h:'';try{")
rep("async function fromHash(){const m=/^#(?:r(\\d+)|o(\\d+)(?:-n(\\d+))?(?:-bm(\\d+))?(?:-(prim|ne|pon))?)$/.exec(location.hash);",
    "async function fromHash(){let hs=location.hash;const ym=/^#(2026|2023|2022|2020)(?:~(2026|2023|2022|2020|nema))?(?:\\/|$)/.exec(hs);if(ym&&YRS().includes(ym[1])){setEL(ym[1],ym[2]&&(ym[2]==='nema'||YRS().includes(ym[2]))?ym[2]:'2023');hs='#'+hs.slice(ym[0].length)}else setEL('2026','2023');\n  const m=/^#(?:r(\\d+)|o(\\d+)(?:-n(\\d+))?(?:-bm(\\d+))?(?:-(prim|ne|pon))?)$/.exec(hs);")
# INFO_DIFF tekst
rep("INFO_DIFF='Razlika = 2026 minus 2023:","INFO_DIFF='Razlika = izabrani izbori minus izbori za poređenje:")
open(P,'w').write(s); print('ok')
# (render poziva elUI; promena padajućih menija — dodato ručno, vidi app_body.html)
