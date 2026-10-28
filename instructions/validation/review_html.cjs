const {chromium}=require('C:/Users/ADMIN/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const {pathToFileURL,fileURLToPath}=require('url');
const path=require('path');
const fs=require('fs');
(async()=>{
 const root=path.resolve(__dirname,'..');
 let browser;
 try { browser=await chromium.launch({headless:true}); }
 catch { browser=await chromium.launch({headless:true,channel:'msedge'}); }
 const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(pathToFileURL(path.join(root,'BMS实施与验收指南.html')).href);
 await page.screenshot({path:path.join(__dirname,'desktop.png')});
 await page.locator('nav a[href="#acceptance"]').click();
 if(!await page.locator('#acceptance').evaluate(el=>el.open))throw Error('Navigation did not expand acceptance');
 await page.locator('#acceptance').scrollIntoViewIfNeeded();
 await page.screenshot({path:path.join(__dirname,'acceptance.png')});
 await page.locator('#expand').click();
 const allOpen=await page.locator('.chapter').evaluateAll(es=>es.every(e=>e.open));
 if(!allOpen)throw Error('Expand-all failed');
 const links=await page.locator('a[href]').evaluateAll(es=>es.map(e=>e.href));
 const badLinks=links.filter(u=>u.startsWith('file:')&&!fs.existsSync(fileURLToPath(new URL(u.split('#')[0]))));
 const missingAnchors=await page.locator('a[href^="#"]').evaluateAll(es=>es.filter(e=>!document.getElementById(e.getAttribute('href').slice(1))).map(e=>e.href));
 await page.setViewportSize({width:390,height:844});
 await page.evaluate(()=>window.scrollTo(0,0));
 await page.screenshot({path:path.join(__dirname,'mobile.png')});
 const layout=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,chapters:document.querySelectorAll('.chapter').length,tables:document.querySelectorAll('table').length}));
 await page.locator('#collapse').click();
 const openAfterCollapse=await page.locator('.chapter').evaluateAll(es=>es.filter(e=>e.open).map(e=>e.id));
 const report={checked_at_utc:new Date().toISOString(),scope:'HTML layout, navigation, local links and expansion controls only',layout,allOpen,openAfterCollapse,badLinks,missingAnchors,errors,passed:layout.width>=layout.scroll&&allOpen&&openAfterCollapse.join()==='guide'&&!badLinks.length&&!missingAnchors.length&&!errors.length};
 fs.writeFileSync(path.join(__dirname,'html-report.json'),JSON.stringify(report,null,2));
 await browser.close();console.log(JSON.stringify(report,null,2));
 if(!report.passed)process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1});
