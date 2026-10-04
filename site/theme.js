"use strict";
window.LinksTheme=(()=>{
 let schema,library;
 const base=document.currentScript?.src.includes('/preview/')?'/preview/':'/';
 const ready=Promise.all([fetch(base+'theme-tokens.json').then(r=>r.json()),fetch(base+'asset-library.json').then(r=>r.json())]).then(([s,l])=>{schema=s.tokens;library=l;return {schema,library}});
 function asset(value){if(!value?.startsWith('system:'))return value;return library?.backgrounds.find(x=>x.id===value.slice(7))?.url||''}
 function validate(key,value){const spec=schema[key];if(!spec)return false;if(spec.type==='color')return typeof value==='string'&&/^#[a-f\d]{6}([a-f\d]{2})?$/i.test(value);if(spec.type==='number'||spec.type==='length')return typeof value==='number'&&Number.isFinite(value)&&value>=spec.min&&value<=spec.max;if(spec.type==='enum')return spec.options.includes(value);return value==='none'||typeof value==='string'&&(/^\/uploads\/[a-f\d-]{36}\.(png|jpg|webp|gif)$/.test(value)||value.startsWith('system:')&&library.backgrounds.some(x=>x.id===value.slice(7)))}
 function cssValue(key,value){const type=schema[key].type;if(type==='length')return value+'px';if(type==='image'){if(value==='none')return 'none';return `url("${asset(value)}")`}return String(value)}
 async function apply(theme,doc=document){await ready;const root=doc.documentElement;for(const key of Object.keys(schema))root.style.removeProperty(key);delete root.dataset.linksTheme;delete root.dataset.linksIconMode;delete root.dataset.linksMotion;root.removeAttribute('data-links-card-image');
  if(!theme||theme.id==='links-original'||!Object.entries(theme.tokens||{}).some(([key,value])=>schema[key]&&value!==schema[key].default))return;
  root.dataset.linksTheme='custom';const values={...Object.fromEntries(Object.entries(schema).map(([k,v])=>[k,v.default])),...theme.tokens};
  for(const [key,value] of Object.entries(values)){if(validate(key,value))root.style.setProperty(key,cssValue(key,value))}
  root.dataset.linksIconMode=values['--links-icon-color-mode'];root.dataset.linksMotion=values['--links-motion'];root.toggleAttribute('data-links-card-image',values['--links-card-image']!=='none');
 }
 function contrast(a,b){function lum(c){const rgb=c.slice(1,7).match(/../g).map(x=>parseInt(x,16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722}const x=lum(a),y=lum(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)}
 return {ready,asset,apply,validate,cssValue,contrast};
})();
