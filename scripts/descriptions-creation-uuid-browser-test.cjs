// Focused creation regression: no backend, production data or external requests.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const {readFileSync}=require('node:fs'),{join}=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{})});
 try{
  const page=await browser.newPage(),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/*',route=>route.abort());
  await page.setContent('<section id="descriptions"></section>');
  await page.evaluate(()=>{
   Object.defineProperty(crypto,'randomUUID',{value:undefined});
   window.fixture={id:'existing-template',name:'Modèle conservé',platform:'youtube',revision:7,sections:[{id:'existing-section',name:'Section conservée',heading:'Titre 😀',text:'Texte intact',after_text:'',mode:'manual',hide_if_empty:false,merchants:[],links:[{id:'existing-link',label:'Lien conservé',reference_url:'https://example.com/original',link_id:'',source_id:''}]}]};
   window.api=async(path,options)=>{
    if(path.endsWith('/save')){window.saved=JSON.parse(options.body);return {...window.saved,id:fixture.id,revision:8}}
    if(path.endsWith('/templates'))return {items:[structuredClone(fixture)]};
    if(path.endsWith('/drafts'))return {items:[]};
    if(path.endsWith('/catalogue'))return {items:[],partners:[]};
    if(path.endsWith('/preview'))return {text:'Texte intact',problems:[]};
    throw Error('Unexpected request: '+path);
   };
  });
  for(const file of ['uuid.js','descriptions.js'])await page.addScriptTag({content:readFileSync(join(__dirname,'../admin',file),'utf8')});
  await page.evaluate(()=>LinksDescriptions.load());
  const section=page.locator('[data-section-id="existing-section"]');
  await section.locator(':scope > summary > span').click();
  await section.getByRole('button',{name:'Ajouter un lien permanent',exact:true}).click();
  await section.getByRole('button',{name:'Ajouter une sous-section marchande',exact:true}).click();
  const merchant=section.locator('.description-merchant');
  await merchant.locator(':scope > summary > span').click();
  await merchant.getByRole('button',{name:'Ajouter un lien permanent',exact:true}).click();
  await page.getByRole('button',{name:'Ajouter une section',exact:true}).click();
  await page.getByRole('button',{name:'Enregistrer le modèle',exact:true}).click();
  await page.waitForFunction(()=>window.saved);
  const {saved,fixture}=await page.evaluate(()=>({saved,fixture}));
  const ids=[saved.sections[0].links[1].id,saved.sections[0].merchants[0].id,saved.sections[0].merchants[0].links[0].id,saved.sections[1].id];
  assert.equal(new Set(ids).size,4);
  for(const id of ids)assert.match(id,/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  assert.equal(saved.expected_revision,7);
  assert.equal(saved.sections[0].id,fixture.sections[0].id);
  assert.equal(saved.sections[0].text,fixture.sections[0].text);
  assert.equal(saved.sections[0].heading,fixture.sections[0].heading);
  assert.deepEqual(saved.sections[0].links[0],fixture.sections[0].links[0]);
  assert.deepEqual(errors,[]);
  console.log('PASS: permanent links, sections and merchant subsections create secure UUIDs without randomUUID; existing content and revision preserved.');
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
