"""生成测试样本：GBK 小说、Big5 繁体、md 笔记、epub、cbz、图片文件夹。"""
from __future__ import annotations

import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).parent


def make_novel():
    paras = [
        "雾从江面漫上来的时候，码头上的灯一盏一盏亮了。老周把最后一只木箱摞好，直起身，捶了捶后腰。",
        "他在这座港口活了五十七年，见过三十种雾，每一种的味道都不一样。今天的雾里有铁锈气，还有一点说不清的甜。",
        "“周叔，三号仓的货还等着点数。”年轻的记账员探进头来，又缩了回去，像是怕被这雾咬了一口。",
        "老周应了一声，拎起马灯推门出去。江面上的雾浓得像化不开的豆浆，只有航标灯在雾墙后面一明一灭，像某种巨大生物的眼睛。",
        "他忽然想起父亲临终前的话：起雾的日子，别去看水。可是不去看水，又怎么看得清自己这一辈子呢。",
    ]
    lines = ["雾港往事", "作者：沈砚", ""]
    for i in range(1, 6):
        lines.append(f"第{i}章 雾中的航标")
        lines.append("")
        lines.extend(paras)
        lines.append("")
    text = "\n".join(lines)
    (HERE / "novel_gbk.txt").write_bytes(text.encode("gbk"))
    trad = "".join(
        ["霧港往事\n", "作者：沈硯\n\n"]
        + [f"第{i}章 霧中的航標\n\n" + "\n".join(
            ["霧從江面漫上來的時候，碼頭上的燈一盞一盞亮了。老周把最後一隻木箱摞好，直起身，捶了捶後腰。",
             "他在這座港口活了五十七年，見過三十種霧，每一種的味道都不一樣。今天的霧裡有鐵鏽氣，還有一點說不清的甜。"]) + "\n\n"
           for i in range(1, 4)]
    )
    (HERE / "traditional_big5.txt").write_bytes(trad.encode("big5"))


def make_long_novel():
    """长章节小说：用于验证多栏分页。"""
    filler = [
        "雾散得很慢，像有人在江面上抖开一匹湿布，抖一下，收一下，怎么也铺不平。",
        "码头东头的缆桩上蹲着一只白鹭，脖子缩在翅膀里，谁也不看。老周认得它，去年冬天就在了。",
        "他把马灯搁在木箱上，火光把雾照出一小块看得见的地方，再远就又是一片白。",
        "潮水在脚下轻轻响，一下，又一下，像谁在数着他剩下的日子。",
        "年轻记账员的名字叫小林，学的是会计，却一辈子想去看海。老周知道，因为小林喝醉时说过。",
        "三号仓的门轴该上油了，开的时候会叫，像被人踩了尾巴的猫。",
        "他想起父亲说过，港口的雾分三等：一等是水雾，二等是雾，三等是老天爷在洗眼睛。",
        "今天大概是二等偏三等。老周在心里记了一笔，然后笑自己到了这把年纪还记这种没用的事。",
        "雾里传来汽笛，很短，是内河船。远洋船的声音要长一些，也更沉，像从水底传上来。",
        "他把账本翻到最后一页，上面是昨天的数字，写得工工整整，一点也看不出写字的人手在抖。",
    ]
    lines = ["雾港往事（全本）", "作者：沈砚", ""]
    for ch in range(1, 13):
        lines.append(f"第{ch}章 雾里的第{ch}个夜晚")
        lines.append("")
        for i in range(24):
            lines.append(filler[(ch * 7 + i) % len(filler)])
        lines.append("")
    (HERE / "long_novel.txt").write_text("\n".join(lines), encoding="utf-8")


def make_md():
    md = """# 无线传感器网络复习笔记

## 一、IEEE 802.15.4 与 ZigBee

ZigBee 工作在 **2.4 GHz** ISM 频段，全球通用，划分为 16 个信道，信道带宽为 `5 MHz`，码元速率 62.5 ksymbol/s。

- 低速率：$250\\ \\mathrm{kb/s}$
- 低功耗：终端节点可电池供电数月
- 自组织：支持星形、树形、网状拓扑

## 二、路由协议对比

| 协议 | 类型 | 优点 | 缺点 |
| --- | --- | --- | --- |
| AODV | 按需 | 开销小 | 时延高 |
| DSDV | 表驱动 | 实时性好 | 收敛慢 |
| LEACH | 分层 | 均衡能耗 | 簇头选举复杂 |

## 三、能量模型

发射 $k$ bit 数据到距离 $d$ 处，能耗为：

$$
E_{tx}(k,d) = E_{elec} \\cdot k + \\varepsilon_{fs} \\cdot k \\cdot d^2, \\quad d < d_0
$$

自由空间模型与多径衰落模型的分界距离 $d_0 = \\sqrt{\\varepsilon_{fs} / \\varepsilon_{mp}}$。

## 四、C 语言位运算速查

```c
// 置位与清位
#define SET_BIT(x, n)  ((x) |= (1U << (n)))
#define CLR_BIT(x, n)  ((x) &= ~(1U << (n)))
```

> 复习建议：先背路由协议对比表，再推导能量模型，最后刷信道划分计算题。
"""
    (HERE / "notes.md").write_text(md, encoding="utf-8")


def make_epub():
    out = HERE / "demo.epub"
    cover = Image.new("RGB", (600, 850), (46, 74, 110))
    d = ImageDraw.Draw(cover)
    d.rectangle([28, 28, 572, 822], outline=(235, 230, 218), width=3)
    d.text((90, 340), "雾港往事", fill=(240, 236, 226))
    d.text((90, 400), "沈砚 著", fill=(190, 195, 205))
    cover_path = HERE / "_cover.png"
    cover.save(cover_path)

    opf = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="pub-id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>雾港往事</dc:title>
    <dc:creator>沈砚</dc:creator>
    <dc:language>zh-CN</dc:language>
    <meta property="dcterms:modified">2026-01-01T00:00:00Z</meta>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="css" href="style.css" media-type="text/css"/>
    <item id="cover" href="cover.png" media-type="image/png" properties="cover-image"/>
    <item id="c1" href="chap1.xhtml" media-type="application/xhtml+xml"/>
    <item id="c2" href="chap2.xhtml" media-type="application/xhtml+xml"/>
    <item id="c3" href="chap3.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="c1"/><itemref idref="c2"/><itemref idref="c3"/>
  </spine>
</package>"""

    container = """<?xml version="1.0" encoding="utf-8"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""

    nav = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>目录</title></head>
<body>
<nav epub:type="toc">
  <ol>
    <li><a href="chap1.xhtml">第一章 铁锈味的雾</a></li>
    <li><a href="chap2.xhtml">第二章 航标灯</a></li>
    <li><a href="chap3.xhtml">第三章 父亲的遗嘱</a></li>
  </ol>
</nav>
</body>
</html>"""

    css = "body{font-family:serif;line-height:1.8;} h1{font-size:1.3em;} img{max-width:100%;}"

    def chapter(title, body_paras, with_media=True):
        media = (
            '<p><img src="cover.png" alt="封面"/></p>'
            '<p><img src="http://example.com/tracker.png" alt="外链图"/></p>'
            "<p><script>alert('xss')</script></p>"
            '<p><a href="chap2.xhtml">跳到第二章</a> <a href="https://example.com">外链</a></p>'
            if with_media
            else ""
        )
        paras = "".join(f"<p>{p}</p>" for p in body_paras)
        return (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>'
            + title
            + '</title><link rel="stylesheet" href="style.css"/></head><body><h1>'
            + title
            + "</h1>"
            + media
            + paras
            + "</body></html>"
        )

    ch1 = chapter(
        "第一章 铁锈味的雾",
        [
            "雾从江面漫上来的时候，码头上的灯一盏一盏亮了。老周把最后一只木箱摞好，直起身，捶了捶后腰。",
            "今天的雾里有铁锈气，还有一点说不清的甜。他深吸一口，觉得肺叶里灌满了旧港口的往事。",
            "“周叔，三号仓的货还等着点数。”年轻的记账员探进头来，又缩了回去。",
        ],
    )
    ch2 = chapter(
        "第二章 航标灯",
        [
            "江面上的雾浓得像化不开的豆浆，只有航标灯在雾墙后面一明一灭。",
            "老周忽然想起父亲临终前的话：起雾的日子，别去看水。",
            "他攥紧马灯的提手，指节发白。三十年了，那句话一直卡在他的骨头缝里。",
        ],
    )
    ch3 = chapter(
        "第三章 父亲的遗嘱",
        [
            "遗嘱封在一个铁盒里，钥匙挂在他的脖子上，贴着他的心跳了三十年。",
            "盒子里只有一张海图，和一行褪色的字：雾散之前，把灯点亮。",
            "老周望向江心。雾，正在慢慢变薄。",
        ],
        with_media=False,
    )

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", container)
        zf.writestr("OEBPS/content.opf", opf)
        zf.writestr("OEBPS/nav.xhtml", nav)
        zf.writestr("OEBPS/style.css", css)
        zf.write(cover_path, "OEBPS/cover.png")
        zf.writestr("OEBPS/chap1.xhtml", ch1)
        zf.writestr("OEBPS/chap2.xhtml", ch2)
        zf.writestr("OEBPS/chap3.xhtml", ch3)
    cover_path.unlink()


def make_comic():
    pages = HERE / "comic_folder"
    pages.mkdir(exist_ok=True)
    palette = [(38, 50, 66), (66, 44, 38), (38, 66, 52), (56, 40, 66)]
    for i in range(1, 9):
        img = Image.new("RGB", (760, 1120), palette[i % len(palette)])
        d = ImageDraw.Draw(img)
        d.rectangle([24, 24, 736, 1096], outline=(225, 220, 208), width=3)
        d.ellipse([220, 260, 540, 580], outline=(225, 220, 208), width=4)
        d.line([120, 700, 640, 700], fill=(225, 220, 208), width=3)
        d.text((300, 500), f"{i:02d}", fill=(230, 226, 214))
        d.text((120, 730), "墨读 · 示例漫画页", fill=(200, 196, 184))
        img.save(pages / f"page_{i:02d}.png")

    cbz = HERE / "comic.cbz"
    with zipfile.ZipFile(cbz, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(pages.glob("*.png")):
            zf.write(f, f"chapter/{f.name}")
        zf.writestr("__MACOSX/._page_01.png", b"junk")


def make_7z():
    import py7zr

    pages = sorted((HERE / "comic_folder").glob("*.png"))
    with py7zr.SevenZipFile(HERE / "comic.7z", "w") as z:
        for f in pages:
            z.write(f, f"pages/{f.name}")


if __name__ == "__main__":
    make_novel()
    make_long_novel()
    make_md()
    make_epub()
    make_comic()
    try:
        make_7z()
    except Exception as e:
        print("7z 样本生成失败（可忽略）：", e)
    print("样本已生成于", HERE)
