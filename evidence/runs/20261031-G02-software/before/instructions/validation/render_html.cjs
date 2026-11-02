const fs=require('fs');
const path=require('path');
const {pathToFileURL}=require('url');
const root=path.resolve(__dirname,'..');
const workspace=path.resolve(root,'..');
function documentHref(target){
  const relative=path.relative(workspace,target);
  if(relative!==''&&!relative.startsWith('..'+path.sep)&&!path.isAbsolute(relative)){
    return path.relative(root,target).split(path.sep).map(part=>encodeURIComponent(part)).join('/');
  }
  return pathToFileURL(target).href;
}
const markedPath=process.env.BMS_MARKED_MODULE || 'C:/Users/ADMIN/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/marked/lib/marked.esm.js';

(async()=>{
  let marked;
  try { marked=require(markedPath).marked; }
  catch { marked=(await import(pathToFileURL(markedPath).href)).marked; }
  const docs=[
    ['guide.md','guide','问题解答与路线'],
    ['specs/acceptance.md','acceptance','G00—G07 验收标准'],
    ['specs/measurement.md','measurement','驱动与测量分层'],
    ['specs/data.md','data','数据、标定与 SOC'],
    ['MIGRATION.md','migration','旧 instructions 怎样改'],
    ['WORKFLOW.md','workflow','执行与证据链'],
    ['references/open-questions.md','questions','待确认项'],
    ['STATUS.md','status','当前项目状态'],
    ['README.md','files','规范包文件导航'],
    ['references/source-map.md','sources','依据与来源'],
  ];
  const internal=new Map(docs.map(d=>[path.resolve(root,d[0]),d[1]]));
  const esc=s=>s.replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const nav=docs.map((d,i)=>`<a href="#${d[1]}"><span>${String(i+1).padStart(2,'0')}</span>${d[2]}</a>`).join('');
  const content=docs.map(([file,id,label],index)=>{
    let html=marked.parse(fs.readFileSync(path.join(root,file),'utf8'),{gfm:true});
    html=html.replace(/href="([^"]+)"/g,(all,href)=>{
      if(/^(https?:|mailto:|#)/.test(href))return all;
      let decoded=decodeURI(href).replace(/^\/([A-Z]:\/)/i,'$1');
      let target=path.resolve(path.dirname(path.join(root,file)),decoded.split('#')[0]);
      return `href="${internal.has(target)?'#'+internal.get(target):documentHref(target)}"`;
    });
    html=html.replace(/<table>/g,'<div class="table-scroll" tabindex="0"><table>').replace(/<\/table>/g,'</table></div>');
    return `<details class="chapter" id="${id}" ${index===0?'open':''}><summary><span class="index">${String(index+1).padStart(2,'0')}</span><span>${label}</span><small>展开 / 收起</small></summary><article>${html}</article></details>`;
  }).join('\n');
  const html=`<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BMS 实施与验收指南</title>
<style>
:root{--ink:#183244;--muted:#62717c;--teal:#087f81;--line:#dce4e7;--paper:#fff;--canvas:#f3f5f3;--nav:#152f40}*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:25px}body{margin:0;background:var(--canvas);color:var(--ink);font:16px/1.85 "Microsoft YaHei","PingFang SC",system-ui,sans-serif}a{color:#087c85;text-decoration-thickness:1px;text-underline-offset:3px}a:hover{color:#ba6335}header{padding:54px max(5vw,24px) 44px;background:var(--nav);color:white;border-top:7px solid #46b9b0}.hero{max-width:1310px;margin:auto}.eyebrow{font:12px/1.4 Consolas,monospace;letter-spacing:2px;color:#87d9cf}header h1{font-size:clamp(29px,3.1vw,46px);line-height:1.4;margin:14px 0}header p{max-width:860px;color:#d2e0e6;margin:0}header .tag{display:inline-block;margin:20px 8px 0 0;border:1px solid #4b6472;padding:3px 12px;border-radius:20px;font-size:12px;color:#d5ebe8}.layout{max-width:1450px;margin:30px auto;padding:0 24px;display:grid;grid-template-columns:235px minmax(0,1fr);gap:32px}.sidebar{position:sticky;top:22px;align-self:start}.sidebar nav{display:grid;gap:3px}.sidebar a{color:var(--ink);text-decoration:none;padding:8px 10px;border-radius:7px;font-size:14px}.sidebar a:hover{background:#e0eeeb}.sidebar a span{font:12px Consolas,monospace;color:var(--teal);margin-right:10px}.smallnote{font-size:12px;line-height:1.7;color:var(--muted);border-top:1px solid var(--line);padding:15px 10px}.toolbar{display:flex;gap:8px;margin:5px 0 17px;flex-wrap:wrap}button{font:inherit;font-size:13px;background:white;border:1px solid #cbd9dc;border-radius:6px;padding:6px 12px;cursor:pointer;color:var(--ink)}button:hover{border-color:var(--teal);color:var(--teal)}main{min-width:0}.milestones{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:23px}.milestones div{background:#e6efeb;padding:15px;border-radius:8px;border-top:3px solid var(--teal)}.milestones b{display:block;font-size:15px}.milestones span{font-size:12px;color:var(--muted)}.chapter{background:var(--paper);border:1px solid var(--line);border-radius:10px;margin-bottom:16px;overflow:hidden}.chapter summary{padding:20px 24px;cursor:pointer;display:flex;gap:13px;align-items:center;font-size:19px;font-weight:700;list-style:none}.chapter summary::-webkit-details-marker{display:none}.index{font:14px Consolas,monospace;color:var(--teal);background:#e6f3ef;border-radius:5px;padding:4px 7px}summary small{font-size:11px;font-weight:400;margin-left:auto;color:var(--muted);white-space:nowrap}.chapter[open] summary{border-bottom:1px solid var(--line)}article{padding:16px 32px 30px}article h1{font-size:27px;line-height:1.55;margin:16px 0 22px}article h2{font-size:21px;border-top:1px solid var(--line);padding-top:25px;margin-top:36px}article h3{font-size:18px;color:var(--teal);margin-top:24px}article p{margin:16px 0}article li{margin:7px 0}article ul,article ol{padding-left:25px}article strong{color:#133f51}code{font:14px/1.65 Consolas,"Microsoft YaHei",monospace;overflow-wrap:anywhere;background:#eef3f3;border-radius:3px;padding:2px 4px}pre{padding:19px;background:#142c3a;color:#e1f1ee;overflow-x:auto;border-radius:7px;line-height:1.7}pre code{background:none;color:inherit;overflow-wrap:normal;padding:0}.table-scroll{overflow-x:auto;margin:21px 0;border:1px solid var(--line);border-radius:7px}table{border-collapse:collapse;min-width:600px;width:100%;font-size:14px}th{background:#eaf1f1;text-align:left;color:#173d4c}th,td{padding:12px 14px;border-bottom:1px solid var(--line);vertical-align:top}tr:last-child td{border-bottom:0}td+td,th+th{border-left:1px solid #e9eded}blockquote{border-left:4px solid var(--teal);background:#eef6f3;padding:3px 20px;margin:20px 0}.footer{color:var(--muted);font-size:12px;text-align:center;padding:30px}.statusnote{border-left:4px solid #d09b46;padding:12px 16px;background:#fff6e7;font-size:13px;margin:0 0 20px}a,td,p,li{overflow-wrap:anywhere}
@media(max-width:1000px){.layout{grid-template-columns:190px minmax(0,1fr);gap:18px;padding:0 18px}.sidebar a{font-size:12px}article{padding:12px 22px 24px}.milestones{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:720px){header{padding:30px 21px}.layout{display:block;margin-top:18px;padding:0 12px}.sidebar{position:static;margin-bottom:20px}.sidebar nav{display:grid;grid-template-columns:1fr 1fr}.sidebar a{font-size:12px;padding:7px}.smallnote{display:none}.chapter summary{font-size:16px;padding:16px 13px;gap:8px}summary small{font-size:10px}article{padding:9px 17px 21px;font-size:15px}article h1{font-size:23px}article h2{font-size:20px}.milestones{gap:7px}.milestones div{padding:11px}.table-scroll{margin-left:0;margin-right:0}pre{font-size:12px;padding:13px}code{font-size:12px}.toolbar{margin:9px 0 17px}}
@media print{.sidebar,.toolbar,summary small{display:none}.layout{display:block;margin:0;padding:0}header{background:white;color:#142c3a;padding:15px;border-top:3px solid #142c3a}header p,.eyebrow{color:#234}header .tag{color:#234;border-color:#ccc}details{break-inside:auto}.chapter{border:0}article{padding:0}.table-scroll{overflow:visible}table{min-width:0;font-size:10px}pre{white-space:pre-wrap;background:#eee;color:#111}.chapter summary{padding:12px 0}body{font-size:11px}.milestones{display:none}a{color:#123;text-decoration:none}}
</style></head><body><header><div class="hero"><div class="eyebrow">BMS ENGINEERING NOTE · 2026.10.28</div><h1>从读数到闭环，再到可信数据</h1><p>把 ADC、标定、PWM、PI 与 SOC 放回同一条可追溯链路。先弄清每一层负责什么，再为每一步规定可测量的完成标准。</p><span class="tag">依据当前工程与课程资料</span><span class="tag">验收草案 · 硬件尚未实测</span><span class="tag">离线阅读 · 无外部依赖</span></div></header><div class="layout"><aside class="sidebar"><nav>${nav}</nav><div class="smallnote">C · 课程明确要求<br>E · 工程建议，正式验收前冻结<br>H · 硬件待确认，不代入猜测值<br><br>正式结果仍须回到原始数据。说明包完整不等于系统验收通过。</div></aside><main><div class="milestones"><div><b>01 测得可信</b><span>原码 / 标定 / 独立验证</span></div><div><b>02 控得稳定</b><span>PWM / 功率级 / PI</span></div><div><b>03 数据可追溯</b><span>时间 / 版本 / 参考 SOC</span></div><div><b>04 模型可复现</b><span>分组 / 评估 / 端侧一致</span></div></div><div class="statusnote">已完成：代码与资料审查、流程适配、文档和模板。尚未执行：新固件构建、烧录、台架标定、功率实验或模型训练。</div><div class="toolbar"><button id="expand">展开全部章节</button><button id="collapse">收起附录</button><button id="print">打印 / 保存 PDF</button><a href="${documentHref(path.join(root,'README.md'))}">打开规范包入口</a></div>${content}</main></div><div class="footer">说明源文件与模板位于 instructions · HTML 由本地 Markdown 生成 · 本文件不包含硬件控制接口</div>
<script>const chapters=[...document.querySelectorAll('.chapter')];document.querySelector('#expand').onclick=()=>chapters.forEach(d=>d.open=true);document.querySelector('#collapse').onclick=()=>chapters.forEach(d=>d.open=d.id==='guide');function reveal(){const el=document.getElementById(location.hash.slice(1));if(el&&el.tagName==='DETAILS'){el.open=true;requestAnimationFrame(()=>el.scrollIntoView());}}document.addEventListener('click',e=>{const a=e.target.closest('a');if(a&&a.getAttribute('href')?.startsWith('#')){const el=document.querySelector(a.getAttribute('href'));if(el)el.open=true;}});window.addEventListener('hashchange',reveal);reveal();document.querySelector('#print').onclick=()=>{chapters.forEach(d=>d.open=true);window.print();};window.addEventListener('beforeprint',()=>chapters.forEach(d=>d.open=true));</script></body></html>`;
  const output=path.join(root,'BMS实施与验收指南.html');fs.writeFileSync(output,html,'utf8');
  console.log(JSON.stringify({output,bytes:Buffer.byteLength(html),chapters:docs.length}));
})().catch(e=>{console.error(e);process.exitCode=1;});
