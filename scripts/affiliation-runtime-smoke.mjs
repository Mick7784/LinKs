// Exercises the shipped system Chromium on each image architecture, offline.
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),{chromium}=require('playwright-core');
const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/chromium',args:['--disable-dev-shm-usage']});
try{
 const page=await browser.newPage();await page.route('**/*',route=>route.abort());
 await page.setContent('<h1>LinKs browser ready</h1>');
 if(await page.locator('h1').textContent()!=='LinKs browser ready')throw new Error('Browser smoke failed');
 console.log('Affiliation Chromium runtime OK: '+process.arch);
}finally{await browser.close()}
