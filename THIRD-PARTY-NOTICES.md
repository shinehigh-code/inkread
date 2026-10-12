# 第三方组件与许可

本项目**自己编写的代码**与下列第三方组件分别授权。分发时请保留本文件与各组件的许可证文本。

## 一、打包进 exe 或前端内置的组件

| 组件 | 版本 | 用途 | 许可证 | 上游 |
| --- | --- | --- | --- | --- |
| pywebview | 6.2.1 | 窗口与 WebView2 集成 | BSD-3-Clause | https://github.com/r0x0r/pywebview |
| pythonnet | 3.2.0 | .NET 互操作（pywebview 在 Windows 上的依赖） | MIT | https://github.com/pythonnet/pythonnet |
| clr_loader | 0.3.1 | 加载 .NET 运行时 | MIT | https://github.com/pythonnet/clr-loader |
| Pillow | 12.2.0 | 封面缩放、图标生成 | MIT-CMU (HPND) | https://github.com/python-pillow/Pillow |
| python-markdown | 3.10.2 | Markdown 渲染 | BSD-3-Clause | https://github.com/Python-Markdown/markdown |
| bleach | 6.4.0 | HTML 白名单净化 | Apache-2.0 | https://github.com/mozilla/bleach |
| OpenCC（Python 重实现） | 0.1.7 | 繁简转换 | Apache-2.0 | https://github.com/yichen0831/opencc-python |
| BeautifulSoup4 | 4.15.0 | EPUB / XHTML 解析 | MIT | https://www.crummy.com/software/BeautifulSoup/ |
| py7zr | 1.1.3 | 7z 支持 | LGPL-2.1-or-later | https://github.com/miurahr/py7zr |
| rarfile | 4.5 | rar 支持（实际解压需系统 UnRAR） | ISC | https://github.com/markokr/rarfile |
| KaTeX | 0.16 | 数学公式渲染（前端内置，离线） | MIT | https://github.com/KaTeX/KaTeX |
| PyInstaller | 6.22.3 | 打包（仅构建期使用） | GPL-2.0-or-later **附例外条款** | https://github.com/pyinstaller/pyinstaller |

说明：

- **PyInstaller 的例外条款**明确允许其打包产物（本项目的 exe）不受 GPL 约束。
- **py7zr 是 LGPL-2.1**：以未修改形式随包分发，许可证文本见其上游仓库；若要替换该库，
  可 `pip install py7zr==1.1.3`（或自己改过的版本）后执行 `python build.py` 重新打包，
  本项目源码完全公开，重建不受限制。
- KaTeX 的 MIT 许可证文本随代码放在 `web/assets/vendor/katex/LICENSE`。
- `.cbr` / `.rar` 的实际解压交给系统 UnRAR 完成，本项目不附带其二进制文件。

## 二、参考过的同类项目（未复用任何代码）

下列项目在**产品形态、功能取舍与交互形式**上提供了参考。本项目是独立实现，
没有复制、改写或翻译其源代码，也没有使用其图标、样式或其它资源文件，
因此不受其许可证约束：

| 项目 | 许可证 | 参考的是 |
| --- | --- | --- |
| [Koodo Reader](https://github.com/koodo-reader/koodo-reader) | AGPL-3.0 | 书库与阅读设置面板的组织方式、阅读模式的划分 |
| [YACReader](https://github.com/YACReader/yacreader) | GPL-3.0 | 漫画的适应模式、单双页、右到左、连续滚动等模式划分 |

**注意**：AGPL-3.0 与 GPL-3.0 都是强著佐权许可。如果将来要从这些项目里引入哪怕一小段代码、
样式或资源，本项目整体就必须改为相同许可（AGPL 还要求通过网络提供服务时公开源码）。

## 三、样例书籍

`samples/` 下的书籍由 `python samples/make_samples.py` 现场生成，内容为虚构文本
（小说《雾港往事》、传感器课程笔记、漫画页码图等），不含任何真实出版物内容。
