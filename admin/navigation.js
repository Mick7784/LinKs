"use strict";
// Callers own routing and data loading; this helper only selects DOM views.
window.StudioNavigation={activate(id,views,buttons){
 for(const view of views)view.classList.toggle("active",view.id===id);
 for(const button of buttons){const active=button.dataset.tab===id;button.classList.toggle("active",active);if(active)button.setAttribute("aria-current","page");else button.removeAttribute("aria-current")}
},
// Section navigation keeps native buttons: Tab/Enter activate; arrows only move focus.
sectionBar(nav,label){
 nav.classList.add('workspace-tabs');
 if(label)nav.setAttribute('aria-label',label);
 nav.addEventListener('keydown',event=>{
  if(event.altKey||event.ctrlKey||event.metaKey||event.shiftKey)return;
  const buttons=[...nav.querySelectorAll('button:not(:disabled)')],index=buttons.indexOf(event.target);
  if(index<0)return;
  let next;
  if(event.key==='ArrowRight')next=(index+1)%buttons.length;
  else if(event.key==='ArrowLeft')next=(index+buttons.length-1)%buttons.length;
  else if(event.key==='Home')next=0;
  else if(event.key==='End')next=buttons.length-1;
  else return;
  event.preventDefault();buttons[next].focus();
 });
},
sectionFocus(root){
 const focused=document.activeElement,id=root.contains(focused)&&focused.closest('.workspace-tabs')?focused.id:'';
 return ()=>{if(id){const next=document.getElementById(id);if(next&&root.contains(next))next.focus({preventScroll:true})}};
}};
