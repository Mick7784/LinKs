/* Pure text tracking. All persisted offsets are Unicode code points. No network. */
(function(root){'use strict';
 const copy=value=>JSON.parse(JSON.stringify(value)),points=text=>Array.from(text),slice=(text,start,end)=>points(text).slice(start,end).join('');
 function toPoint(text,offset,right=false){
  offset=Math.max(0,Math.min(text.length,offset));
  if(offset>0&&offset<text.length&&/[\uD800-\uDBFF]/.test(text[offset-1])&&/[\uDC00-\uDFFF]/.test(text[offset]))offset+=right?1:-1;
  return points(text.slice(0,offset)).length;
 }
 const toUTF16=(text,offset)=>points(text).slice(0,offset).join('').length;
 function occurrences(text,quote){
  if(!quote)return [];const result=[];let offset=0,index;
  while((index=text.indexOf(quote,offset))!==-1){result.push({start:toPoint(text,index),end:toPoint(text,index+quote.length)});offset=index+quote.length;if(result.length>20)break}
  return result;
 }
 function candidates(text,anchors,definitions){
  const lines=[];let offset=0;for(const line of text.split('\n')){lines.push({text:line,start:offset,end:offset+points(line).length});offset+=points(line).length+1}
  const headings=[];
  for(const definition of definitions){
   if(!definition.heading)continue;
   const anchor=anchors.find(a=>a.id===definition.id),names=new Set([definition.heading.trim()]);
   if(anchor?.quote)names.add(anchor.quote.split('\n')[0].trim());
   for(const line of lines)if(names.has(line.text.trim()))headings.push({id:definition.id,start:line.start});
  }
  // Hashtags are only proposed for the explicit default section, never products.
  if(definitions.some(s=>s.id==='hashtags')){const line=lines.find(l=>/^#[^\s#]+(?:\s+#\S+)*\s*$/.test(l.text));if(line)headings.push({id:'hashtags',start:line.start})}
  headings.sort((a,b)=>a.start-b.start);const result={},chars=points(text);
  for(const heading of headings){let end=headings.find(h=>h.start>heading.start)?.start??chars.length;while(end>heading.start&&chars[end-1]==='\n')end--;const list=result[heading.id]||(result[heading.id]=[]);if(list.length<20)list.push({start:heading.start,end})}
  const summary=definitions.find(s=>s.id==='summary'&&!s.heading);
  if(summary&&headings.length){let end=headings[0].start;while(end>0&&chars[end-1]==='\n')end--;result.summary=[{start:0,end}]}
  return result;
 }
 function track(before,after,previous,definitions,{imported=false}={}){
  const old=points(before),next=points(after);let from=0,oldEnd=old.length,newEnd=next.length;
  while(from<oldEnd&&from<newEnd&&old[from]===next[from])from++;
  while(oldEnd>from&&newEnd>from&&old[oldEnd-1]===next[newEnd-1]){oldEnd--;newEnd--}
  if(before===after&&!imported)return copy(previous);
  const delta=newEnd-oldEnd,anchors=copy(previous),confirmed=anchors.filter(a=>a.status==='confirmed');
  const touched=confirmed.filter(a=>from===oldEnd?from>=a.start&&from<=a.end:from<a.end&&oldEnd>a.start);
  let owner=!imported&&touched.length===1&&from>=touched[0].start&&oldEnd<=touched[0].end?touched[0]:null;
  if(owner&&from===owner.start&&oldEnd===owner.end&&newEnd===from&&oldEnd>from)owner=null;
  // A cut section pasted at another section's boundary retains its own identity.
  // Do not absorb it into the neighbouring section merely because it touches it.
  const moved=previous.some(a=>a.status==='ambiguous'&&a.quote&&next.slice(from,newEnd).join('').includes(a.quote));
  if(owner&&from===oldEnd&&moved&&(from===owner.start||from===owner.end))owner=null;
  for(const anchor of anchors){
   const wasConfirmed=anchor.status==='confirmed';let located=null;
   if(!imported&&wasConfirmed){
    if(owner?.id===anchor.id)located={start:anchor.start,end:anchor.end+delta};
    else if(anchor.end<=from&&!(from===oldEnd&&anchor.start===from))located={start:anchor.start,end:anchor.end};
    else if(anchor.start>=oldEnd&&!(from===oldEnd&&anchor.end===from))located={start:anchor.start+delta,end:anchor.end+delta};
   }
   // A complete import establishes new boundaries. A unique old paragraph may
   // only be a prefix of the new section, so it is not sufficient confirmation.
   if(!located&&!imported){const matches=occurrences(after,anchor.quote);if(matches.length===1)located=matches[0]}
   if(located&&located.start>=0&&located.end<=next.length){Object.assign(anchor,located,{status:'confirmed',quote:next.slice(located.start,located.end).join(''),candidates:[]})}
   else Object.assign(anchor,{status:'ambiguous',start:null,end:null,candidates:[]});
  }
  // Do not silently let two section identities own the same text.
  const ordered=anchors.filter(a=>a.status==='confirmed'&&a.start<a.end).sort((a,b)=>a.start-b.start),overlap=new Set();
  for(let i=0;i<ordered.length;i++)for(let j=i+1;j<ordered.length&&ordered[j].start<ordered[i].end;j++){overlap.add(ordered[i].id);overlap.add(ordered[j].id)}
  for(const a of anchors)if(overlap.has(a.id))Object.assign(a,{status:'ambiguous',start:null,end:null});
  const proposed=candidates(after,anchors,definitions);
  for(const a of anchors)if(a.status==='ambiguous')a.candidates=proposed[a.id]||[];
  return anchors;
 }
 function bind(text,anchors,id,start,end){
  const size=points(text).length;
  if(!Number.isInteger(start)||!Number.isInteger(end)||start<0||end<start||end>size)throw Error('Sélection invalide.');
  if(anchors.some(a=>a.id!==id&&a.status==='confirmed'&&Math.max(a.start,start)<Math.min(a.end,end)))throw Error('Cette sélection chevauche une section confirmée. Ajustez-la ou dissociez d’abord cet emplacement.');
  if(!anchors.some(a=>a.id===id))throw Error('Section inconnue.');
  return anchors.map(a=>a.id===id?{id,status:'confirmed',start,end,quote:slice(text,start,end),candidates:[]}:copy(a));
 }
 const api={points,slice,toPoint,toUTF16,track,bind,candidates};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.DescriptionSections=api;
})(typeof window==='undefined'?globalThis:window);
