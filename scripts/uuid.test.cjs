const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../admin/uuid.js'),'utf8');
function generator(crypto){const context={window:{},crypto,Math:Object.assign(Object.create(Math),{random(){throw Error('Math.random is forbidden')}})};vm.runInNewContext(source,context);return context.window.LinksUUID}
test('uses native randomUUID with its Crypto receiver',()=>{
 const crypto={randomUUID(){assert.equal(this,crypto);return 'native'},getRandomValues(){assert.fail('fallback must not run')}};
 assert.equal(generator(crypto)(),'native');
});
test('fallback sets v4 and RFC variant bits, retaining all other random bits',()=>{
 for(const value of [0,255]){
  let calls=0;const crypto={getRandomValues(bytes){assert.equal(this,crypto);assert.equal(bytes.length,16);bytes.fill(value);calls++;return bytes}};
  assert.equal(generator(crypto)(),value?'ffffffff-ffff-4fff-bfff-ffffffffffff':'00000000-0000-4000-8000-000000000000');assert.equal(calls,1);
 }
});
test('fallback produces canonical distinct UUIDs using real cryptographic bytes',()=>{
 const crypto=require('node:crypto').webcrypto,uuid=generator({randomUUID:false,getRandomValues:crypto.getRandomValues.bind(crypto)}),ids=new Set();
 for(let i=0;i<1000;i++){const id=uuid();assert.match(id,/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);ids.add(id)}assert.equal(ids.size,1000);
});
test('missing cryptographic APIs fail explicitly without weak identifiers',()=>{
 for(const crypto of [undefined,{}, {randomUUID:'unavailable',getRandomValues:null}])assert.throws(generator(crypto),/génération sécurisée d’identifiants est indisponible/);
 assert.throws(generator({getRandomValues(){throw Error('Entropy unavailable')}}),/Entropy unavailable/);
});
test('admin UUID calls stay centralized and helper loads before consumers',()=>{
 const dir=path.join(__dirname,'../admin'),html=fs.readFileSync(path.join(dir,'index.html'),'utf8');
 for(const file of fs.readdirSync(dir).filter(f=>f.endsWith('.js')&&f!=='uuid.js')){
  const source=fs.readFileSync(path.join(dir,file),'utf8');assert.doesNotMatch(source,/\brandomUUID\s*\(/,file);
  if(source.includes('window.LinksUUID()'))assert(html.indexOf('/uuid.js')<html.indexOf('/'+file),file);
 }
 assert.doesNotMatch(source,/Math\.random/);
});
