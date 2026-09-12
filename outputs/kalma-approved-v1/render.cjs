const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const runtime = 'C:/Users/Alexa Magdalene/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
const { chromium } = require(path.join(runtime, 'playwright'));
const root = __dirname;
const frames = [
  ['ready', 'ready', .6], ['blink-half', 'blink', .04], ['blink-closed', 'blink', .10],
  ['listening-1', 'listening', .25], ['listening-2', 'listening', .65], ['listening-3', 'listening', 1.15],
  ['thinking-1', 'thinking', .4], ['thinking-2', 'thinking', 1.2], ['thinking-3', 'thinking', 2.2],
  ['speaking-1', 'speaking', .10], ['speaking-2', 'speaking', .3], ['speaking-3', 'speaking', .52],
  ['needs-attention', 'error', .6], ['encouragement', 'happy', .6]
];
const server = http.createServer((req, res) => {
  const relative = decodeURIComponent(new URL(req.url, 'http://localhost').pathname).slice(1) || 'index.html';
  const file = path.resolve(root, relative);
  if (!file.startsWith(root + path.sep) || !fs.existsSync(file)) { res.writeHead(404); res.end(); return; }
  res.setHeader('Content-Type', ({'.html':'text/html', '.js':'text/javascript','.png':'image/png','.svg':'image/svg+xml'})[path.extname(file)] || 'application/octet-stream');
  fs.createReadStream(file).pipe(res);
});
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch({executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1678, height: 937}, deviceScaleFactor: 1});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(origin + '/index.html?export=1');
    await page.locator('#stage img').evaluate(img => img.decode());
    await page.waitForFunction(() => !!window.kalmaPreview);
    fs.mkdirSync(path.join(root, 'frames'), {recursive: true});
    fs.mkdirSync(path.join(root, 'overlays'), {recursive: true});
    for (const [name, state, time] of frames) {
      const svg = await page.evaluate(({state,time}) => {
        kalmaPreview.setState(state); kalmaPreview.seek(time);
        return kalmaPreview.overlaySvg(state,time);
      }, {state,time});
      await page.locator('#stage').screenshot({path: path.join(root, 'frames', name + '.png')});
      fs.writeFileSync(path.join(root, 'overlays', name + '.svg'), svg);
    }
    assert.equal(errors.length, 0, errors.join('\n'));
    fs.writeFileSync(path.join(root,'manifest.json'), JSON.stringify({
      version:2, width:1678, height:937, base:'robot-base.png', baseHasTransparency:false,
      bodyFixedAcrossFrames:true, voiceMode:'demo rhythm; optional normalized level input',
      frames:frames.map(([name,state,time])=>({name,state,time,png:`frames/${name}.png`,overlay:`overlays/${name}.svg`}))
    },null,2));
    await page.goto(origin);
    await page.locator('button[data-state="listening"]').click();
    assert.equal(await page.locator('#stage').getAttribute('aria-label'), 'KALMA: listening');
    await page.locator('#pause').check();
    const first = await page.locator('#face').innerHTML();
    await page.waitForTimeout(200);
    assert.equal(await page.locator('#face').innerHTML(), first, 'Pause must freeze animation');
    await page.emulateMedia({reducedMotion:'reduce'});
    await page.locator('button[data-state="thinking"]').click();
    const reduced = await page.locator('#face').innerHTML();
    await page.waitForTimeout(200);
    assert.equal(await page.locator('#face').innerHTML(), reduced, 'Reduced motion must remain still');
    await page.setViewportSize({width:390,height:844});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth), 'Mobile overflow');
    await page.screenshot({path:path.join(root,'preview-mobile.png'),fullPage:true});
    await page.setViewportSize({width:1440,height:1000});
    await page.locator('button[data-state="ready"]').click();
    await page.screenshot({path:path.join(root,'preview-desktop.png'),fullPage:true});
    await page.goto(origin + '/contact-sheet.html');
    await page.evaluate(()=>Promise.all([...document.images].map(img=>img.decode())));
    await page.screenshot({path:path.join(root,'expression-sheet.png'),fullPage:true});
    console.log('PASS: 14 aligned frames, 14 SVG overlays, UI controls, pause, reduced motion, mobile width, and no script errors.');
    console.log('Rendering animation reel...');
    await page.goto(origin + '/index.html?export=1');
    await page.locator('#stage img').evaluate(img=>img.decode());
    const video = await page.evaluate(async () => {
      kalmaPreview.seek(.6);
      const canvas = document.createElement('canvas'); canvas.width = 1006; canvas.height = 562;
      const ctx = canvas.getContext('2d');
      const base = document.querySelector('#stage img');
      const sequence = [['ready',3],['blink',1],['listening',4],['thinking',4],['speaking',4],['error',3],['happy',3]];
      const type = MediaRecorder.isTypeSupported('video/webm;codecs=vp9') ? 'video/webm;codecs=vp9' : 'video/webm';
      const stream = canvas.captureStream(24);
      const recorder = new MediaRecorder(stream,{mimeType:type,videoBitsPerSecond:2500000});
      const chunks = []; recorder.ondataavailable = event => { if(event.data.size) chunks.push(event.data); };
      const done = new Promise(resolve => recorder.onstop = resolve);
      recorder.start();
      for (const [state,duration] of sequence) {
        const start = performance.now();
        while ((performance.now()-start)/1000 < duration) {
          const t = (performance.now()-start)/1000;
          const url = URL.createObjectURL(new Blob([kalmaPreview.overlaySvg(state,t)],{type:'image/svg+xml'}));
          const overlay = new Image(); overlay.src=url; await overlay.decode();
          ctx.drawImage(base,0,0,canvas.width,canvas.height);
          ctx.drawImage(overlay,0,0,canvas.width,canvas.height);
          URL.revokeObjectURL(url);
          await new Promise(resolve=>setTimeout(resolve,1000/24));
        }
      }
      recorder.stop(); await done; stream.getTracks().forEach(track=>track.stop());
      const blob = new Blob(chunks,{type:'video/webm'});
      return await new Promise(resolve=>{const reader=new FileReader(); reader.onload=()=>resolve(reader.result.split(',')[1]);reader.readAsDataURL(blob);});
    });
    fs.writeFileSync(path.join(root,'kalma-animation-reel.webm'),Buffer.from(video,'base64'));
    console.log('Saved animation reel.');
  } finally { await browser.close(); server.close(); }
})().catch(error=>{console.error(error);server.close();process.exitCode=1;});
