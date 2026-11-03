// Build-time inventory only. Never reads environment variables or account data.
import {execFileSync} from 'node:child_process';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
function command(binary,args){try{return execFileSync(binary,args,{encoding:'utf8',timeout:15000,stdio:['ignore','pipe','pipe']}).trim()}catch{return null}}
let playwright=null;try{playwright=require('playwright-core/package.json').version}catch{}
let firefox=null;try{firefox=command(require('playwright-core').firefox.executablePath(),['--version'])}catch{}
const python=command('python3',['-c','import sys,sqlite3,json,PIL; print(json.dumps(dict(python=sys.version.split()[0],sqlite=sqlite3.sqlite_version,pillow=PIL.__version__)))']);
const packages=command('dpkg-query',['-W','-f=${Package}\t${Version}\n']);
console.log(JSON.stringify({node:process.version,platform:process.platform,architecture:process.arch,playwright,firefox,python:python?JSON.parse(python):null,chromium:command('chromium',['--version']),os_packages:packages?packages.split('\n'):null},null,2));
