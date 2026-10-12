// 分页与键盘翻页调试
const { chromium } = require('playwright');

(async () => {
  const port = process.argv[2];
  const base = `http://127.0.0.1:${port}`;
  const lib = await (await fetch(base + '/api/library')).json();
  const txt = lib.books.find((b) => b.fmt === 'txt' && b.title === '雾港往事（全本）');

  const browser = await chromium.launch({ channel: 'msedge', args: ['--no-proxy-server'] });
  const page = await browser.newPage({ viewport: { width: 1340, height: 880 } });
  page.on('pageerror', (e) => console.log('PAGEERROR', e.message));
  await page.goto(`${base}/#/read/${txt.id}`);
  await page.waitForSelector('.flow p');
  await page.waitForTimeout(400);

  const probe = async (tag) => {
    const info = await page.evaluate(() => {
      const flow = document.getElementById('flow');
      const cs = getComputedStyle(flow);
      const padX = parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight);
      return {
        readers: document.querySelectorAll('.reader').length,
        label: document.getElementById('pglabel').textContent,
        chapter: document.getElementById('chname').textContent,
        transform: flow.style.transform,
        colWidth: cs.columnWidth,
        scrollW: flow.scrollWidth,
        clientW: flow.clientWidth,
        padX,
        step: parseFloat(cs.columnWidth) + parseFloat(cs.columnGap),
        active: document.activeElement.tagName,
      };
    });
    console.log(tag, JSON.stringify(info));
  };

  await probe('初始');

  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(300);
  await probe('按→');

  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(300);
  await probe('再按→');

  await page.keyboard.press('ArrowLeft');
  await page.waitForTimeout(300);
  await probe('按←');

  // 切到长章节（第 5 章）验证多栏
  await page.click('[data-act="toc"]');
  await page.click('.toc-item[data-i="5"]');
  await page.waitForTimeout(700);
  await probe('第五章');

  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(300);
  await probe('第五章-下一页');

  await browser.close();
})();
