// 截一张带朗读条与语音列表的界面图
const { chromium } = require('playwright');
const path = require('path');

const OUT = path.join(__dirname, '..', 'shots');

(async () => {
  const base = `http://127.0.0.1:${process.argv[2]}`;
  const lib = await (await fetch(base + '/api/library')).json();
  const novel = lib.books.find((b) => b.title.includes('全本'));
  const browser = await chromium.launch({ channel: 'msedge', headless: false, args: ['--no-proxy-server'] });
  const page = await browser.newPage({ viewport: { width: 1240, height: 800 }, deviceScaleFactor: 1.25 });
  await page.goto(`${base}/#/read/${novel.id}`);
  await page.waitForSelector('.flow p');
  await page.click('[data-act="toc"]');
  await page.click('.toc-item[data-i="1"]');
  await page.waitForTimeout(800);
  await page.click('[data-act="tts"]');
  await page.waitForTimeout(2500);
  await page.screenshot({ path: path.join(OUT, 'tts-reading.png') });
  await page.click('[data-act="font"]');
  await page.waitForTimeout(600);
  await page.screenshot({ path: path.join(OUT, 'tts-panel.png') });
  await page.click('[data-act="tts-stop"]');
  console.log('截图完成');
  await browser.close();
})();
