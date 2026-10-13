'use strict';
const $ = id => document.getElementById(id);
const typeNames = {conference:'Conference paper',journal:'Journal article',chapter:'Book chapter',book:'Book',poster:'Conference poster',abstract:'Conference abstract',thesis:'Thesis',preprint:'Preprint',report:'Report',other:'Other publication'};
let dataset, manifest, decryptedPDF = null, shown = 30, filtered = [], localToken = null;
let toastTimer, objectURLs = [];
function el(tag, text, cls) { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n; }
function safeURL(value) { try { const u = new URL(value); return ['http:', 'https:'].includes(u.protocol) && !u.username && !u.password ? u.href : null; } catch { return null; } }
function anchor(text, url, cls) { const a = el('a', text, cls); const href = safeURL(url); if (!href) return el('span', text); a.href = href; a.target = '_blank'; a.rel = 'noopener noreferrer'; return a; }
function toast(text) { $('toast').textContent = text; $('toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => {$('toast').hidden = true;}, 4000); }
function download(blob, filename) { const url = URL.createObjectURL(blob); objectURLs.push(url); const a = el('a'); a.href = url; a.download = filename; document.body.append(a); a.click(); a.remove(); setTimeout(() => {URL.revokeObjectURL(url); objectURLs = objectURLs.filter(x => x !== url);}, 30000); }
function bytes64(s) { return Uint8Array.from(atob(s), c => c.charCodeAt(0)); }
async function decrypt(bundle, passphrase) {
  if (bundle.format !== 'PublicationGroup:v1' || bundle.algorithm !== 'AES-256-GCM' || bundle.kdf !== 'PBKDF2-SHA256' || bundle.iterations !== 600000) throw Error('Unsupported encrypted format');
  if (!globalThis.crypto?.subtle) throw Error('Decryption needs HTTPS or localhost and a browser with Web Crypto support.');
  const base = await crypto.subtle.importKey('raw', new TextEncoder().encode(passphrase), 'PBKDF2', false, ['deriveKey']);
  const key = await crypto.subtle.deriveKey({name:'PBKDF2',hash:'SHA-256',salt:bytes64(bundle.salt),iterations:bundle.iterations}, base, {name:'AES-GCM',length:256}, false, ['decrypt']);
  const clear = await crypto.subtle.decrypt({name:'AES-GCM',iv:bytes64(bundle.iv),additionalData:new TextEncoder().encode('PublicationGroup:v1'),tagLength:128}, key, bytes64(bundle.ciphertext));
  return JSON.parse(new TextDecoder().decode(clear));
}
async function fetchJSON(path) { const r = await fetch(path, {cache:'no-store'}); if (!r.ok) throw Error(`Could not load ${path} (HTTP ${r.status})`); return r.json(); }
function option(value, name) { const n = el('option', name); n.value = value; return n; }
function displayName(name) {
  if(name===name.toLocaleUpperCase() && name!==name.toLocaleLowerCase()) return name.toLocaleLowerCase().split(' ').map((w,i)=>i&&['da','de','do','das','dos','e','van','von'].includes(w)?w:w.charAt(0).toLocaleUpperCase()+w.slice(1)).join(' ');
  return name;
}
function setTheme(value) { document.documentElement.dataset.theme=value; try{localStorage.setItem('pubgroup-theme',value);}catch{} }
let savedTheme='system';try{savedTheme=localStorage.getItem('pubgroup-theme')||'system';}catch{}
if(!['light','dark','system'].includes(savedTheme))savedTheme='system';
$('themeSelect').value=savedTheme;setTheme(savedTheme);
$('themeSelect').addEventListener('change',()=>setTheme($('themeSelect').value));
function records() { return dataset.catalogue || dataset.publications; }
function setup(data) {
  if (data.schema_version !== 1 || !Array.isArray(data.publications)) throw Error('Unsupported collection schema');
  data.researchers=data.researchers.map(r=>({...r,name:displayName(r.name)})).sort((a,b)=>a.name.localeCompare(b.name,'pt',{sensitivity:'base'}));
  dataset = data;
  $('unlockPanel').hidden = true; $('library').hidden = false;
  $('groupLabel').textContent = data.group;
  $('updateLabel').textContent = `Collected ${data.generated_at.slice(0,16).replace('T',' ')} · ${data.timezone} · ${data.total_catalogue} records in the catalogue`;
  $('versionLabel').textContent = `${data.version} · build ${data.build}`;
  $('privacyBadge').textContent = manifest.encrypted ? 'Decrypted in this browser' : 'Public data export';
  $('lockButton').hidden = !manifest.encrypted;
  const years = [...new Set(records().filter(p=>p.date).map(p=>p.date.slice(0,4)))].sort().reverse();
  $('yearFilter').replaceChildren(option('', 'All years'), ...years.map(y=>option(y,y)));
  const defaultYear = String(data.current_year);
  if (!years.includes(defaultYear)) $('yearFilter').append(option(defaultYear,`${defaultYear} (no records)`));
  $('yearFilter').value = /^\d{4}$/.test(data.period_label) ? data.period_label : '';
  $('typeFilter').replaceChildren(option('','All types'), ...Object.keys(typeNames).filter(t=>records().some(p=>p.type===t)).map(t=>option(t,typeNames[t])));
  $('researcherFilter').replaceChildren(option('','All researchers'), ...data.researchers.map(r=>option(r.id,r.name)));
  $('pdfButton').textContent = `Download PDF · ${data.period_label}`;
  $('pdfButton').disabled = !manifest.pdf && !decryptedPDF;
  const bad = data.sources.filter(s=>s.status!=='ok');
  const rejected = data.sources.reduce((a,s)=>a+(s.rejected_count||0),0);
  const fetched = data.sources.map(s=>s.fetched_at).filter(Boolean).sort();
  $('coverageNotice').classList.toggle('warning',bad.length>0||rejected>0);
  $('coverageNotice').textContent = `${data.sources.length-bad.length}/${data.sources.length} profiles read. ${bad.length ? `${bad.length} sources need attention; saved records are retained where available. ` : ''}${rejected ? `${rejected} citations need review. ` : ''}Report period: ${data.period_label}. ${fetched.length ? `Source data fetched ${fetched[0].slice(0,10)}${fetched.at(-1).slice(0,10)!==fetched[0].slice(0,10)?' to '+fetched.at(-1).slice(0,10):''}. `:''}Conference months are taken from sourced event dates where available.`;
  const c=data.changes;
  $('changeSummary').textContent=c.baseline?'First collection: baseline established.':`Across the catalogue: ${c.new.length} new, ${c.updated.length} updated, ${c.no_longer_listed.length} no longer listed. `;
  renderSources(); applyFilters();
}
function applyFilters() {
  if(!dataset)return;
  const q=$('searchInput').value.trim().toLocaleLowerCase(), year=$('yearFilter').value, kind=$('typeFilter').value, person=$('researcherFilter').value, status=$('statusFilter').value;
  const newIDs=new Set(dataset.changes.new);
  filtered=records().filter(p=>(!year||p.date?.slice(0,4)===year)&&(!kind||p.type===kind)&&(!person||p.researcher_ids.includes(person))&&(!status||p.status===status)&&(!$('newFilter').checked||newIDs.has(p.id))&&(!q||[p.title,...p.authors,p.venue,p.doi].join(' ').toLocaleLowerCase().includes(q)));
  // Numeric date components preserve unknown-month ordering.
  const key=p=>(p.activity_date||p.date||'').split('-').map(Number);
  filtered.sort((a,b)=>{const x=key(a),y=key(b);for(let i=0;i<3;i++){const d=(y[i]||0)-(x[i]||0);if(d)return d;}return b.title.localeCompare(a.title);});
  shown=30; renderList(); renderCounts();
}
function renderList() {
  $('resultCount').textContent=`(${filtered.length})`;
  const list=$('publicationList'); list.replaceChildren();
  if(!filtered.length)list.append(el('div','No publications match these filters.','panel empty'));
  const newIDs=new Set(dataset.changes.new);
  filtered.slice(0,shown).forEach((p,index)=>{
    const card=el('article',undefined,'publication');card.append(el('div',String(index+1).padStart(2,'0'),'pub-index'));
    const body=el('div');const meta=el('div',undefined,'pub-meta');
    meta.append(el('span',(p.activity_date_source==='conference'?p.activity_date+' · event month':p.date)||'Date unknown','pub-date'),el('span',typeNames[p.type]||p.type,'pill'),el('span',p.status,'pill'));
    if(newIDs.has(p.id))meta.append(el('span','New','pill new'));
    body.append(meta,el('h3',p.title),el('p',p.authors.map(displayName).join('; '),'authors'));
    if(p.venue)body.append(el('p',p.venue,'venue'));
    const names=p.researcher_ids.map(id=>dataset.researchers.find(r=>r.id===id)?.name||id).join(' · ');
    body.append(el('p',names,'venue'));
    const actions=el('div',undefined,'pub-actions');
    if(safeURL(p.url))actions.append(anchor('Open publication ↗',p.url,'button'));
    else actions.append(el('span','No publication link listed','muted small'));
    const copy=el('button','Copy BibTeX','button');copy.type='button';copy.addEventListener('click',async()=>{
      try{await navigator.clipboard.writeText(p.bibtex);toast('BibTeX copied');}catch{download(new Blob([p.bibtex],{type:'text/plain;charset=utf-8'}),p.id+'.bib');toast('Clipboard unavailable; BibTeX downloaded');}
    });actions.append(copy);body.append(actions);
    const details=el('details',undefined,'details');details.append(el('summary','Citation, dates & sources'));
    details.append(el('p',`Date source: ${p.date_source}. First seen: ${(p.first_seen||'').slice(0,10)}.${p.publisher_date?' DOI publication date: '+p.publisher_date+'.':''}`));
    if(p.event){const note=el('p',`Conference: ${p.event.start_date} to ${p.event.end_date}. `);note.append(anchor('Date source',p.event.source_url));details.append(note);}
    if(p.warnings?.length)details.append(el('p',p.warnings.join('; ')));
    if(p.doi_check)details.append(el('p',`DOI check: ${p.doi_check.status} · ${p.doi_check.source}`));
    const sources=el('p');p.sources.forEach((s,i)=>{if(i)sources.append(document.createTextNode(' · '));sources.append(anchor(dataset.researchers.find(r=>r.id===s.researcher_id)?.name||'CV source',s.url));});details.append(sources,el('pre',p.bibtex));
    p.links?.filter(u=>u!==p.url&&safeURL(u)).forEach(u=>{const line=el('p');line.append(anchor(u,u));details.append(line);});
    // All source-provided strings enter the DOM as text, never HTML.
    body.append(details);card.append(body);list.append(card);
  });
  $('loadMore').hidden=shown>=filtered.length;
}
function countBy(values) { const counts={};values.forEach(x=>counts[x]=(counts[x]||0)+1);return counts; }
function bars(target, counts, names) { const holder=$(target);holder.replaceChildren();const entries=Object.entries(counts).sort((a,b)=>b[1]-a[1]),max=Math.max(1,...entries.map(e=>e[1]));entries.forEach(([key,v])=>{const row=el('div',undefined,'bar-row'),label=el('div',undefined,'bar-label');label.append(el('span',names[key]||key),el('strong',String(v)));const track=el('div',undefined,'bar-track'),fill=el('div',undefined,'bar-fill');fill.style.width=(v/max*100)+'%';track.append(fill);row.append(label,track);holder.append(row);});if(!entries.length)holder.append(el('p','No matching records.','muted')); }
function renderCounts() {
  const newIDs=new Set(dataset.changes.new);
  $('totalStat').textContent=filtered.length;
  $('conferenceStat').textContent=filtered.filter(p=>['conference','poster','abstract'].includes(p.type)).length;
  $('researcherStat').textContent=new Set(filtered.flatMap(p=>p.researcher_ids)).size;
  $('newStat').textContent=filtered.filter(p=>newIDs.has(p.id)).length;
  bars('typeChart',countBy(filtered.map(p=>p.type)),typeNames);
  const monthly=Array(12).fill(0),eventMonths=Array(12).fill(0),publicationMonths=Array(12).fill(0);
  const unknown=filtered.filter(p=>(p.activity_date||p.date||'').length<7).length;
  filtered.forEach(p=>{const dt=p.activity_date||p.date||'';if(dt.length<7)return;const i=Number(dt.slice(5,7))-1;monthly[i]++;(p.activity_date_source==='conference'?eventMonths:publicationMonths)[i]++;});
  $('monthNote').textContent=`${unknown} outputs have no known month. Conference contributions use the event month when their publication month is missing. ${$('yearFilter').value?'Showing '+$('yearFilter').value+'.':'Calendar months combined across the filtered years.'}`;
  const months=el('div',undefined,'months'),max=Math.max(1,...monthly);
  monthly.forEach((n,i)=>{const col=el('div',undefined,'month'),bar=el('div',undefined,'month-bar');bar.style.height=(n/max*140)+'px';bar.title=`${publicationMonths[i]} publication dates; ${eventMonths[i]} event dates`;const publication=el('div',undefined,'month-publication'),event=el('div',undefined,'month-conference');publication.style.flex=String(publicationMonths[i]);event.style.flex=String(eventMonths[i]);bar.append(publication,event);col.append(el('span',String(n)),bar,el('span',['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][i]));months.append(col);});$('monthChart').replaceChildren(months);
}
function renderSources() {
  const holder=$('sourceList');holder.replaceChildren();
  const sources=dataset.researchers.map(r=>({name:r.name+' · CiênciaVitae',url:r.url}));
  sources.push({name:'Crossref · publication references',url:'https://api.crossref.org/'},{name:'DataCite · publication references',url:'https://api.datacite.org/'});
  dataset.reference_urls.forEach(u=>sources.push({name:new URL(u).hostname+new URL(u).pathname,url:u}));
  (dataset.calendar_sources||[]).forEach(s=>sources.push({name:s.name+' · conference dates',url:s.url}));
  const seen=new Set();sources.forEach(s=>{if(!safeURL(s.url)||seen.has(s.url))return;seen.add(s.url);const li=el('li');li.append(anchor(s.name,s.url));holder.append(li);});
  $('referenceLinks').replaceChildren();
}

function dialog(title, nodes) { $('dialogTitle').textContent=title;$('dialogContent').replaceChildren(...nodes);$('actionDialog').showModal(); }
async function localJob(mode) {
  if(!localToken||manifest.encrypted){
    const command=mode==='report'?`python3 -m pubgroup report --period ${$('yearFilter').value||'all'}`:'python3 -m pubgroup run --refresh';
    dialog('Run from the project folder',[el('p','The static website reads a saved collection. To collect fresh records or build a new LaTeX report, run the local tool.'),el('code',command+(manifest.encrypted?' --encrypt':'')),el('p','On GitHub, you can also run the supplied manual Actions workflow. Browser filters change the listing; the downloadable PDF has its own labelled period.')]);return;
  }
  const b=mode==='report'?$('buildPDFButton'):$('refreshButton');b.disabled=true;
  try{
    const response=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json','X-PubGroup-Token':localToken},body:JSON.stringify({mode,period:mode==='report'?($('yearFilter').value||'all'):undefined})});
    if(!response.ok)throw Error(await response.text());
    toast('Job started. The listing will update when it finishes.');
    let state;
    do {await new Promise(resolve=>setTimeout(resolve,1500));state=await fetchJSON('/api/status');}while(state.running);
    if(state.error)throw Error(state.error);
    manifest=await fetchJSON('manifest.json');decryptedPDF=null;setup(await fetchJSON(manifest.dataset));toast('Collection and report updated');
  }catch(e){dialog('Job could not finish',[el('p',e.message)]);}finally{b.disabled=false;}
}
$('unlockForm').addEventListener('submit',async e=>{e.preventDefault();const button=e.target.querySelector('button');button.disabled=true;$('unlockMessage').textContent='Decrypting…';try{const payload=await decrypt(await fetchJSON(manifest.bundle),$('passphrase').value);decryptedPDF=payload.pdf?new Blob([bytes64(payload.pdf)],{type:'application/pdf'}):null;setup(payload.dataset);$('passphrase').value='';$('unlockMessage').textContent='';}catch(e){$('unlockMessage').textContent=e.name==='OperationError'?'Passphrase incorrect or encrypted file damaged.':e.message;}finally{button.disabled=false;}});
$('lockButton').addEventListener('click',()=>{location.reload();});
['searchInput','yearFilter','typeFilter','researcherFilter','statusFilter','newFilter'].forEach(id=>$(id).addEventListener(id==='searchInput'?'input':'change',applyFilters));
$('loadMore').addEventListener('click',()=>{shown+=30;renderList();});
document.querySelectorAll('.tab').forEach(tab=>tab.addEventListener('click',()=>{document.querySelectorAll('.tab').forEach(t=>{const on=t===tab;t.classList.toggle('active',on);t.setAttribute('aria-pressed',String(on));$(t.dataset.panel).hidden=!on;});}));
$('bibButton').addEventListener('click',()=>download(new Blob([filtered.map(p=>p.bibtex).join('\n')],{type:'text/plain;charset=utf-8'}),'publications.bib'));
$('pdfButton').addEventListener('click',async()=>{if(decryptedPDF){download(decryptedPDF,`publications-${dataset.period_label}.pdf`);return;}try{const latest=await fetchJSON(manifest.dataset);if(latest.generated_at!==dataset.generated_at||latest.period_label!==dataset.period_label){setup(latest);toast('The prepared report changed; the library was refreshed. Click download again.');return;}const r=await fetch(manifest.pdf);if(!r.ok)throw Error('PDF unavailable');download(await r.blob(),`publications-${dataset.period_label}.pdf`);}catch(e){toast(e.message);}});
$('refreshButton').addEventListener('click',()=>localJob('run'));
(async()=>{try{manifest=await fetchJSON('manifest.json');if(manifest.encrypted){$('unlockPanel').hidden=false;$('privacyBadge').textContent='Encrypted export';}else setup(await fetchJSON(manifest.dataset));try{const status=await fetchJSON('/api/status');if(status.token&&!manifest.encrypted){localToken=status.token;const b=el('button','Build PDF for selected year','button quiet');b.id='buildPDFButton';b.addEventListener('click',()=>localJob('report'));document.querySelector('.hero-actions').append(b);$('privacyBadge').textContent='Local collector connected';}}catch{/* Static hosting has no local collector. */}}catch(e){$('loadError').hidden=false;$('loadErrorMessage').textContent=e.message;}})();
