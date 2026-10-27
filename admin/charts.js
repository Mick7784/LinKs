"use strict";
(function(){
const fmt=new Intl.NumberFormat("fr-FR"),esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function ranking(series,max,{comparison=false}={}){
 const root=document.createElement("div");root.className="ranking-bars"+(comparison?" is-comparison":"");
 series.forEach((entry,index)=>{const line=document.createElement("div"),track=document.createElement("span"),bar=document.createElement("i");line.className="ranking-series"+(entry.tone?" tone-"+tone(entry.tone):"");if(entry.key)line.dataset.seriesKey=entry.key;line.title=entry.label+" : "+fmt.format(entry.value);line.setAttribute("role","img");line.setAttribute("aria-label",entry.label+" : "+fmt.format(entry.value));track.className="ranking-track";bar.style.width=Math.min(100,Math.max(0,entry.value/Math.max(max,1)*100))+"%";bar.className=index?"ranking-secondary":"ranking-primary";track.append(bar);line.append(track);if(series.length>1||comparison){const caption=document.createElement("small");caption.textContent=entry.label+" · "+fmt.format(entry.value);line.append(caption)}root.append(line)});
 return root;
}
function donut(root,items,{preview=false,query="",sort="input"}={}){
 const total=items.reduce((sum,item)=>sum+item[1],0),colors=["#22D3EE","#8B5CF6","#3B82F6","#0891B2","#6D28D9","#64748B"],radius=66,circumference=2*Math.PI*radius;
 if(!total){root.innerHTML='<p class="empty">Aucun événement sur cette période.</p>';return}
 const limit=preview?4:5,main=items.slice(0,limit),rest=items.slice(limit).reduce((n,x)=>n+x[1],0),segments=rest?[...main,["Autres sources",rest]]:main;
 let offset=0;
 const circles=segments.map(([name,value],index)=>{const length=value/total*circumference,result=`<circle class="donut-segment" cx="90" cy="90" r="${radius}" fill="none" stroke="${colors[index%colors.length]}" stroke-width="24" stroke-dasharray="${length} ${circumference-length}" stroke-dashoffset="${-offset}" transform="rotate(-90 90 90)"><title>${esc(name)} : ${fmt.format(value)}</title></circle>`;offset+=length;return result}).join("");
 root.innerHTML=`<div class="sources-layout"><div class="donut-wrap"><svg viewBox="0 0 180 180" role="img" aria-label="Répartition des événements ; valeurs dans la légende">${circles}<text class="donut-total" x="90" y="87" text-anchor="middle">${fmt.format(total)}</text><text class="donut-caption" x="90" y="107" text-anchor="middle">Événements</text></svg></div><div class="source-list"></div></div>`;
 const rows=(preview?segments:items).map(([name,value],index)=>({name,total:value,color:colors[Math.min(index,limit)%colors.length],details:[]}));
 StudioCollection.create(root.querySelector('.source-list'),{pageSize:preview?5:20,renderRow:item=>{const row=document.createElement('div');row.className='source-row';row.innerHTML=`<span class="source-dot"></span><span class="source-name">${esc(item.name)}</span><strong>${fmt.format(item.total)}</strong><small>${(item.total/total*100).toLocaleString("fr-FR",{maximumFractionDigits:1})} %</small>`;row.querySelector('.source-dot').style.backgroundColor=item.color;return row}}).setRows(rows,{sort,query,preview});
}
function timeline(root,detail,days,labels){
 const buckets=days.map(([day,views,clicks])=>({start:day,end:day,views,clicks})),width=Math.max(200,root.clientWidth),left=44,right=width-8,height=width>600?250:180,bottom=height+44,slot=(right-left)/Math.max(1,buckets.length),barWidth=Math.max(1,slot-3),peak=Math.max(1,...buckets.flatMap(x=>[x.views,x.clicks]));
 const magnitude=10**Math.floor(Math.log10(peak/4)),step=Math.max(1,Math.ceil(peak/4/magnitude)*magnitude),max=step*4;
 const short=d=>d.slice(8,10)+"/"+d.slice(5,7),description=b=>`${short(b.start)} : ${labels[0]?fmt.format(b.views)+" "+labels[0]+" · ":""}${fmt.format(b.clicks)} ${labels[1]}`,stride=Math.max(1,Math.ceil(buckets.length/Math.max(2,Math.floor((right-left)/58))));
 const groups=buckets.map((b,i)=>{const center=left+slot*(i+.5),halfWidth=Math.max(2,(barWidth-4)/2),offset=halfWidth/2+2;
 const series=[{value:b.views,cls:"visits-bar",x:center-offset},{value:b.clicks,cls:"clicks-bar",x:center+offset}];
 const bars=series.map(s=>{const h=s.value*height/max;return `<rect class="${s.cls} animated-bar" x="${s.x-halfWidth/2}" y="${bottom-h}" width="${halfWidth}" height="${h}" rx="${Math.min(4,halfWidth/3)}"/>`}).join("");
 const marker=(value,y,cls,x)=>`<g class="chart-value ${cls}"><rect x="${x-Math.max(12,String(value).length*3.6+5)}" y="${y-12}" width="${Math.max(24,String(value).length*7.2+10)}" height="17" rx="3"/><text text-anchor="middle" x="${x}" y="${y}">${fmt.format(value)}</text></g>`;
 const markers=slot>=58?series.filter(x=>x.value).map(x=>marker(x.value,bottom-x.value*height/max-9,x.cls+"-value",x.x)).join(""):"";
 const label=i%stride===0?`<text text-anchor="middle" x="${center}" y="${bottom+23}">${short(b.start)}</text>`:"";
 return `<g class="chart-bucket" role="button" tabindex="0" data-bucket="${i}" aria-label="${esc(description(b))}"><title>${esc(description(b))}</title><rect class="chart-hit" x="${left+i*slot}" y="0" width="${slot}" height="${bottom}"/>${bars}<g class="chart-values${slot>=Math.max(36,String(peak).length*8+12)?" always":""}">${markers}</g>${label}</g>`}).join("");
 const grid=Array.from({length:5},(_,i)=>{const y=bottom-i*height/4;return `<line class="chart-grid" x1="${left}" x2="${right}" y1="${y}" y2="${y}"/><text x="2" y="${y+4}">${fmt.format(i*step)}</text>`}).join("");
 root.innerHTML=`<svg viewBox="0 0 ${width} ${bottom+35}" role="group" aria-label="${esc(labels.filter(Boolean).join(" et "))} par jour">${grid}${groups}</svg><div class="chart-tooltip" role="tooltip" hidden></div>`;
 const show=index=>{const b=buckets[index];if(!b)return;detail.textContent=description(b);root.querySelectorAll("[data-bucket]").forEach(g=>g.classList.toggle("selected",Number(g.dataset.bucket)===index));const tooltip=root.querySelector('.chart-tooltip');tooltip.hidden=false;tooltip.innerHTML=`<strong>${esc(b.start.split('-').reverse().join('/'))}</strong>${labels[0]?`<span>${esc(labels[0])} : ${fmt.format(b.views)}</span>`:""}<span>${esc(labels[1])} : ${fmt.format(b.clicks)}</span>`;tooltip.style.left=`${Math.max(0,Math.min(root.clientWidth-155,(left+slot*(index+.5))/width*root.clientWidth-75))}px`};
 const select=event=>{const g=event.target.closest("[data-bucket]");if(g)show(Number(g.dataset.bucket))};root.onclick=select;root.onpointerover=select;if(root.chartFocusHandler)root.removeEventListener("focusin",root.chartFocusHandler);root.chartFocusHandler=select;root.addEventListener("focusin",select);root.onpointerleave=()=>{root.querySelector('.chart-tooltip').hidden=true};
 root.onkeydown=event=>{const g=event.target.closest("[data-bucket]");if(!g)return;if(event.key==="Enter"||event.key===" "){event.preventDefault();show(Number(g.dataset.bucket))}else if(event.key==="Escape"){root.querySelector('.chart-tooltip').hidden=true}else if(event.key==="ArrowRight"||event.key==="ArrowLeft"){event.preventDefault();const index=Math.max(0,Math.min(buckets.length-1,Number(g.dataset.bucket)+(event.key==="ArrowRight"?1:-1)));root.querySelector(`[data-bucket="${index}"]`).focus()}};
 detail.textContent=buckets.length?(matchMedia('(pointer:coarse)').matches?"Touchez une barre pour afficher les chiffres.":""):"Aucune donnée sur cette période.";
}
// Statistics use the same SVG/DOM primitives as the dashboard. Missing values
// remain missing; visual scales and visibility never change the report totals.
const toneNames=new Set(['public','tracked','sources','campaigns']);
const tone=key=>toneNames.has(key)?key:'public';
const chartStates=new WeakMap();
function plotModel(days,series,hidden=new Set()){
 const visible=series.filter(s=>!hidden.has(s.key));
 const values=days.map(row=>visible.map(s=>typeof row[s.index]==='number'&&Number.isFinite(row[s.index])&&row[s.index]>=0?row[s.index]:null));
 const peak=Math.max(0,...values.flat().filter(value=>value!==null));
 const magnitude=peak?10**Math.floor(Math.log10(peak/4)):1;
 const step=peak?Math.max(1,Math.ceil(peak/4/magnitude)*magnitude):1;
 return {visible,values,peak,step,max:step*4};
}
const dayLabel=(day,long=false)=>new Intl.DateTimeFormat('fr-FR',{day:'numeric',month:long?'long':'short',...(long?{year:'numeric'}:{}),timeZone:'UTC'}).format(new Date(day+'T12:00:00Z'));
function timeSeries(root,detail,days,series,{mode='line',active=()=>true,onSelectDay,selectedDay,navigation:showNavigation=true}={}){
 // The main root is shared with timeline(). Replacing children does not detach
 // its delegated handlers, which close over a different report and date range.
 root.onclick=root.onpointerover=root.onkeydown=root.onpointerleave=null;
 if(root.chartFocusHandler){root.removeEventListener('focusin',root.chartFocusHandler);delete root.chartFocusHandler}
 let state=chartStates.get(root);
 if(!state){state={hidden:new Set(),selected:null};chartStates.set(root,state);state.observer=new ResizeObserver(()=>{if(state.active?.()&&root.clientWidth>0&&state.width!==root.clientWidth)state.draw?.()});state.observer.observe(root)}
 Object.assign(state,{days,series,mode,active});
 if(selectedDay)state.selected=selectedDay;
 state.draw=()=>{
  if(!state.active()||!root.clientWidth)return;
  state.width=root.clientWidth;
  const model=plotModel(state.days,state.series,state.hidden),{visible,values,peak,step,max}=model;
  const outerWidth=Math.max(200,root.clientWidth),width=mode==='bars'?Math.max(outerWidth,days.length*Math.max(26,visible.length*12)+76):outerWidth;
  const height=outerWidth<500?200:230,left=62,right=width-18,top=24,bottom=top+height,slot=(right-left)/Math.max(1,days.length),x=i=>left+slot*(i+.5),y=value=>bottom-value/max*height;
  root.classList.add('statistics-time-chart');root.dataset.chartMode=mode;
  root.replaceChildren();
  const legend=document.createElement('div');legend.className='time-legend';legend.setAttribute('role','group');legend.setAttribute('aria-label','Séries du graphique');
  for(const s of series){const button=document.createElement('button');button.type='button';button.className='series-toggle tone-'+tone(s.tone)+(s.dashed?' is-dashed':'');button.dataset.seriesKey=s.key;button.setAttribute('aria-pressed',String(!state.hidden.has(s.key)));button.textContent=s.label;button.onclick=()=>{state.hidden.has(s.key)?state.hidden.delete(s.key):state.hidden.add(s.key);state.draw();root.querySelectorAll('.series-toggle').forEach(n=>{if(n.dataset.seriesKey===s.key)n.focus()})};legend.append(button)}
  root.append(legend);
  const viewport=document.createElement('div');viewport.className='time-viewport';viewport.tabIndex=mode==='bars'?0:-1;viewport.setAttribute('aria-label',mode==='bars'?'Activité quotidienne, défilement horizontal si nécessaire':'Évolution quotidienne');
  const stride=Math.max(1,Math.ceil(days.length/Math.max(1,Math.floor((right-left)/90))));
  const axisFmt=max>=1000000?new Intl.NumberFormat('fr-FR',{notation:'compact',maximumSignificantDigits:3}):fmt;
  const grid=Array.from({length:5},(_,i)=>{const value=i*step,at=y(value);return `<line class="time-grid" x1="${left}" x2="${right}" y1="${at}" y2="${at}"/><text class="time-axis" x="${left-10}" y="${at+4}" text-anchor="end">${esc(axisFmt.format(value))}</text>`}).join('');
  const crossesYear=days.length>1&&days[0][0].slice(0,4)!==days[days.length-1][0].slice(0,4);
  const axisDate=day=>crossesYear?new Intl.DateTimeFormat('fr-FR',{day:'numeric',month:'short',year:'2-digit',timeZone:'UTC'}).format(new Date(day+'T12:00:00Z')):dayLabel(day);
  const labels=days.map((row,i)=>i===0||i===days.length-1||i%stride===0&&days.length-1-i>=stride*.65?`<text class="time-axis time-date" text-anchor="${i===0?'start':i===days.length-1?'end':'middle'}" x="${i===0?left+3:i===days.length-1?right-3:x(i)}" y="${bottom+27}">${esc(axisDate(row[0]))}</text>`:'').join('');
  let marks='';
  if(mode==='line')for(let j=0;j<visible.length;j++){
   const s=visible[j],parts=[];let current=[];
   values.forEach((row,i)=>{if(row[j]===null){if(current.length)parts.push(current);current=[]}else current.push([x(i),y(row[j])])});if(current.length)parts.push(current);
   marks+=parts.map(points=>`<polyline class="time-line tone-${tone(s.tone)}${s.dashed?' is-dashed':''}" data-series-key="${esc(s.key)}" points="${points.map(p=>p.join(',')).join(' ')}"/>${points.length===1?`<circle class="time-point tone-${tone(s.tone)}" data-series-key="${esc(s.key)}" cx="${points[0][0]}" cy="${points[0][1]}" r="4"/>`:''}`).join('');
  }
  if(mode==='bars')values.forEach((row,i)=>row.forEach((value,j)=>{if(value===null)return;const barWidth=Math.min(24,(slot-6)/Math.max(1,visible.length)),s=visible[j];marks+=`<rect class="daily-bar tone-${tone(s.tone)}${s.dashed?' is-dashed':''}" data-series-key="${esc(s.key)}" x="${x(i)+(j-visible.length/2)*barWidth}" y="${y(value)}" width="${Math.max(1,barWidth-2)}" height="${value/max*height}" rx="2"/>`;}));
  const hits=days.map((row,i)=>`<g class="chart-bucket" data-bucket="${i}" tabindex="${i===0?'0':'-1'}" role="button" aria-label="${esc(dayLabel(row[0],true)+', '+visible.map((s,j)=>s.label+' : '+(values[i][j]===null?'non disponible':fmt.format(values[i][j]))).join(', '))}"><rect class="time-hit" x="${left+i*slot}" y="${top}" width="${slot}" height="${height}"/></g>`).join('');
  viewport.innerHTML=`<svg class="time-svg" width="${width}" height="${bottom+48}" viewBox="0 0 ${width} ${bottom+48}" role="group" aria-label="${esc(series.map(s=>s.label).join(' et '))} par jour">${grid}${labels}${marks}${hits}<g class="time-cursor" hidden><line y1="${top}" y2="${bottom}"/><g class="time-cursor-points"></g></g></svg>`;
  if(!visible.length||!peak){const empty=document.createElement('p');empty.className='time-empty';empty.textContent=!visible.length?'Activez une série pour afficher le graphique.':days.length&&values.flat().some(value=>value!==null)?'Aucune activité mesurée sur cette période.':'Aucune donnée disponible sur cette période.';viewport.append(empty)}
  const frame=document.createElement('div');frame.className='time-frame';frame.append(viewport);
  if(mode==='bars'){const axis=document.createElement('div');axis.className='time-fixed-axis';axis.setAttribute('aria-hidden','true');axis.innerHTML=`<svg width="${left}" height="${bottom+48}" viewBox="0 0 ${left} ${bottom+48}"><rect class="time-axis-backdrop" width="${left}" height="${bottom+48}"/>${Array.from({length:5},(_,i)=>`<text class="time-axis" x="${left-10}" y="${y(i*step)+4}" text-anchor="end">${esc(axisFmt.format(i*step))}</text>`).join('')}</svg>`;frame.append(axis)}
  root.append(frame);
  // Hide date labels partly covered by the fixed axis while scrolling daily bars.
  const fitDates=()=>{if(mode==='bars')viewport.querySelectorAll('.time-date').forEach(label=>{const box=label.getBBox();label.style.visibility=box.x-viewport.scrollLeft<left||box.x+box.width-viewport.scrollLeft>outerWidth?'hidden':''})};
  viewport.onscroll=fitDates;
  const tooltip=document.createElement('div');tooltip.className='chart-tooltip time-tooltip';tooltip.hidden=true;tooltip.setAttribute('role','tooltip');root.append(tooltip);
  const inspector=document.createElement('div');inspector.className='time-inspector';inspector.setAttribute('role','status');inspector.setAttribute('aria-live','polite');const reading=document.createElement('div');reading.className='time-reading';reading.append(inspector);root.append(reading);
  const navigation=document.createElement('div');navigation.className='time-navigation';
  const previous=document.createElement('button'),next=document.createElement('button'),slider=document.createElement('input');previous.type=next.type='button';previous.textContent='←';next.textContent='→';previous.setAttribute('aria-label','Jour précédent');next.setAttribute('aria-label','Jour suivant');slider.type='range';slider.min='0';slider.max=String(Math.max(0,days.length-1));slider.step='1';slider.setAttribute('aria-label','Jour à examiner');navigation.append(previous,slider,next);if(showNavigation)reading.append(navigation);
  const show=(index,{pointer=false,focus=false,commit=false}={})=>{
   if(!days.length)return;index=Math.max(0,Math.min(days.length-1,index));state.selected=days[index][0];slider.value=String(index);slider.setAttribute('aria-valuetext',dayLabel(days[index][0],true));previous.disabled=index===0;next.disabled=index===days.length-1;
   const title=dayLabel(days[index][0],true),numbers=visible.map((s,j)=>({s,text:s.label+' : '+(values[index][j]===null?'Non disponible':fmt.format(values[index][j]))}));
   inspector.replaceChildren();const heading=document.createElement('strong');heading.textContent=title;inspector.append(heading);for(const {s,text} of numbers){const value=document.createElement('span');value.className='inspector-value tone-'+tone(s.tone);value.dataset.seriesKey=s.key;value.textContent=text;inspector.append(value)}
   if(!visible.length){const text=document.createElement('span');text.textContent='Aucune série affichée.';inspector.append(text)}
   const description=title+' · '+numbers.map(x=>x.text).join(' · ');if(detail)detail.textContent=description;
   tooltip.innerHTML=`<strong>${esc(title)}</strong>${numbers.map(({text})=>`<span>${esc(text)}</span>`).join('')}`;tooltip.hidden=!pointer||!visible.length;
   tooltip.style.left=Math.max(0,Math.min(outerWidth-240,x(index)-viewport.scrollLeft-100))+'px';
   const cursor=viewport.querySelector('.time-cursor');cursor.removeAttribute('hidden');cursor.querySelector('line').setAttribute('x1',x(index));cursor.querySelector('line').setAttribute('x2',x(index));cursor.querySelector('.time-cursor-points').innerHTML=mode==='line'?numbers.map(({s},j)=>values[index][j]===null?'':`<circle class="time-point tone-${tone(s.tone)}" data-series-key="${esc(s.key)}" cx="${x(index)}" cy="${y(values[index][j])}" r="4"/>`).join(''):'';
   viewport.querySelectorAll('.chart-bucket').forEach((n,i)=>{n.classList.toggle('selected',i===index);n.tabIndex=i===index?0:-1});
   if(focus){viewport.querySelector(`[data-bucket="${index}"]`)?.focus();if(mode==='bars')viewport.scrollLeft=Math.max(0,x(index)-outerWidth/2)}
   if(commit)onSelectDay?.(state.selected);
  };
  state.selectDay=day=>{const index=days.findIndex(row=>row[0]===day);if(index<0)return;show(index);if(mode==='bars'&&(x(index)-viewport.scrollLeft<left||x(index)-viewport.scrollLeft>outerWidth))viewport.scrollLeft=Math.max(0,x(index)-outerWidth/2);fitDates()};
  const targetIndex=event=>{const bucket=event.target.closest?.('[data-bucket]');if(bucket)return Number(bucket.dataset.bucket);const rect=viewport.getBoundingClientRect();return Math.floor((event.clientX-rect.left+viewport.scrollLeft-left)/slot)};
  viewport.onpointermove=event=>{if(event.pointerType!=='touch')show(targetIndex(event),{pointer:true})};viewport.onclick=event=>show(targetIndex(event),{commit:true});viewport.onpointerleave=()=>tooltip.hidden=true;
  viewport.onfocusin=event=>{const bucket=event.target.closest('[data-bucket]');if(bucket)show(Number(bucket.dataset.bucket))};
  viewport.onkeydown=event=>{const focused=event.target.closest('[data-bucket]'),selected=focused?Number(focused.dataset.bucket):Math.max(0,days.findIndex(row=>row[0]===state.selected));if(['ArrowLeft','ArrowRight','Home','End','Enter',' '].includes(event.key)){event.preventDefault();show(event.key==='Home'?0:event.key==='End'?days.length-1:selected+(event.key==='ArrowLeft'?-1:event.key==='ArrowRight'?1:0),{focus:true,commit:true})}if(event.key==='Escape')tooltip.hidden=true};
  slider.oninput=()=>show(Number(slider.value),{commit:true});previous.onclick=()=>show(Number(slider.value)-1,{focus:mode==='bars',commit:true});next.onclick=()=>show(Number(slider.value)+1,{focus:mode==='bars',commit:true});
  slider.disabled=previous.disabled=next.disabled=!days.length;
  if(days.length){const selected=days.findIndex(row=>row[0]===state.selected),index=selected>=0?selected:days.length-1;show(index);if(mode==='bars')viewport.scrollLeft=Math.max(0,x(index)-outerWidth/2)}else inspector.textContent='Aucune date disponible.';
  fitDates();
 };
 state.draw();
}
// Category identity determines colour, never row order or volume. Numbers and
// exact legends provide a second cue without ornamental textures.
const sourceSlots={site:0,youtube:3,instagram:1,facebook:2,mail:4,newsletter:6,qr:5,tiktok:7,discord:6,other:4};
function sourceHash(key){let hash=0;for(const char of String(key))hash=(hash*31+char.codePointAt(0))>>>0;return hash}
function sourceColor(key){if(key==='unknown')return 'var(--chart-category-unknown)';return 'var(--chart-category-'+(Object.hasOwn(sourceSlots,key)?sourceSlots[key]:sourceHash(key)%8)+')'}
function distribution(root,items,{query='',sort='input',category='source',onSelect=()=>{}}={}){
 root.classList.add('source-distribution');
 const total=items.reduce((sum,row)=>sum+row[1],0),positive=items.filter(row=>row[1]>0),ring=positive.length>=2&&positive.length<=6&&positive.every(row=>String(row[0]).length<=42);
 if(!total){root.innerHTML='<p class="empty">Aucune visite ou ouverture mesurée pour cette période et cette source.</p>';return}
 root.innerHTML=`<div class="source-overview"><strong class="source-total">${fmt.format(total)}</strong><span>visites et ouvertures · ${fmt.format(positive.length)} ${esc(category)}(s)</span></div><div class="sources-layout"><div class="donut-wrap" ${ring?'':'hidden'}></div><div class="source-list"></div></div><p class="source-inspector" role="status" aria-live="polite">${ring?'Choisissez un segment ou sa légende pour lire ses valeurs.':'Répartition par '+esc(category)+' · barres proportionnelles au total.'}</p>`;
 const pct=value=>value>0&&value/total*100<.1?'<0,1 %':(value/total*100).toLocaleString('fr-FR',{maximumFractionDigits:1})+' %';
 const select=(key,name,value,activate=false)=>{
  root.querySelector('.source-inspector').textContent=name+' : '+fmt.format(value)+' visites et ouvertures · '+pct(value);
  root.querySelectorAll('[data-source-key]').forEach(n=>{const selected=n.dataset.sourceKey===key;n.classList.toggle('selected',selected);n.setAttribute('aria-pressed',String(selected))});
  if(ring){root.querySelector('.donut-total').textContent=fmt.format(value);root.querySelector('.donut-caption').textContent=pct(value)}
  onSelect({key,name,value,activate});
 };
 if(ring){
  let offset=0;const circumference=2*Math.PI*66;
  const markers=[];
  const segments=positive.map(([name,value,key=name],index)=>{
   const length=value/total*circumference,angle=(offset+length/2)/circumference*2*Math.PI-Math.PI/2;
   if(value/total>=.08){const x=90+66*Math.cos(angle),y=90+66*Math.sin(angle);markers.push(`<g class="source-segment-number" aria-hidden="true"><circle cx="${x}" cy="${y}" r="10"/><text x="${x}" y="${y+4}" text-anchor="middle">${index+1}</text></g>`)}
   const gap=Math.min(2.5,length*.15),result=`<circle class="donut-segment" data-source-key="${esc(key)}" data-source-color="${esc(sourceColor(key))}" tabindex="0" role="button" aria-pressed="false" aria-label="${esc(name+' : '+fmt.format(value)+' · '+pct(value))}" cx="90" cy="90" r="66" fill="none" stroke="${esc(sourceColor(key))}" stroke-width="24" stroke-dasharray="${length-gap} ${circumference-length+gap}" stroke-dashoffset="${-offset-gap/2}" transform="rotate(-90 90 90)"><title>${esc(name+' : '+fmt.format(value)+' · '+pct(value))}</title></circle>`;offset+=length;return result;
  }).join('');
  root.querySelector('.donut-wrap').innerHTML=`<svg viewBox="0 0 180 180" role="group" aria-label="Répartition des visites et ouvertures par ${esc(category)}">${segments}${markers.join('')}<text class="donut-total" x="90" y="87" text-anchor="middle">${fmt.format(total)}</text><text class="donut-caption" x="90" y="107" text-anchor="middle">Total</text></svg>`;
  const nodes=[...root.querySelectorAll('.donut-segment')];
  nodes.forEach((node,index)=>{
   const row=positive[index],show=()=>select(node.dataset.sourceKey,row[0],row[1]);node.onpointerenter=node.onfocus=show;node.onclick=()=>select(node.dataset.sourceKey,row[0],row[1],true);
   node.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();select(node.dataset.sourceKey,row[0],row[1],true)}else if(['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){event.preventDefault();nodes[event.key==='Home'?0:event.key==='End'?nodes.length-1:(index+(event.key==='ArrowLeft'?-1:1)+nodes.length)%nodes.length].focus()}};
  });
 }
 const rows=positive.map(([name,value,key=name,details=[]],index)=>({name,total:value,key:String(key),number:index+1,details}));
 StudioCollection.create(root.querySelector('.source-list'),{pageSize:20,renderRow:item=>{
  const node=document.createElement('div');node.className='source-row source-stat-row';node.dataset.sourceKey=item.key;node.tabIndex=0;node.setAttribute('role','button');node.setAttribute('aria-pressed','false');node.setAttribute('aria-label',item.name+' : '+fmt.format(item.total)+' · '+pct(item.total));
  node.innerHTML=`<span class="source-dot${ring?' source-number':''}" aria-hidden="true">${ring?item.number:''}</span><span class="source-name">${esc(item.name)}</span><strong>${fmt.format(item.total)}</strong><small>${pct(item.total)}</small>${ring?'':'<span class="source-share-track"><i></i></span>'}`;
  node.style.setProperty('--source-color',sourceColor(item.key));
  const bar=node.querySelector('i');if(bar)bar.style.width=(item.total/total*100)+'%';
  node.onpointerenter=node.onfocus=()=>select(item.key,item.name,item.total);node.onclick=()=>select(item.key,item.name,item.total,true);node.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();select(item.key,item.name,item.total,true)}};return node;
 }}).setRows(rows,{sort,query});
}
(typeof window==='undefined'?globalThis:window).StudioCharts={donut,ranking,timeline,timeSeries,distribution,plotModel,sourceColor,selectDay:(root,day)=>chartStates.get(root)?.selectDay?.(day)};
})();
