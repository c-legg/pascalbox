# Pascal Box

一个面向 Object Pascal 的轻量桌面 IDE。界面采用硬边、方角的深色设计，
内置 Free Pascal 编译与 Windows 外部终端运行流程，适合算法练习、课程作业和
小型控制台程序。

## 功能

- **文件与标签**：新建、打开多文件、保存、另存为、全部保存；关闭未保存标签时
  会询问是否保存；标签支持切换、左右拖动排序、关闭和溢出滚动。
- **Pascal 编辑**：行号、当前行高亮、语法高亮、括号高亮与成对补全、自动缩进、
  多行缩进、撤销/重做和字号调整。
- **查找与替换**：`Ctrl+F` 打开内联查找栏，`Ctrl+H` 展开替换；支持区分大小写、
  全字匹配、`F3` / `Shift+F3` 循环查找、全部替换和匹配高亮。
- **缩进设置**：可设置 1–8 个空格的缩进宽度，并切换空格或制表符插入方式。
- **FPC 构建**：`F6` 编译、`F7` 运行已有可执行文件、`F5` 编译并运行。
- **编译诊断**：编译日志按严重程度着色，错误和警告可解析计数；双击输出中的源码
  位置可跳转到对应文件、行和列。
- **Windows 运行**：通过独立终端启动程序，程序退出后窗口保留并等待按键关闭。
- **界面与设置**：方角深色/亮色界面，可在“查看”菜单或 `Ctrl+T` 间切换；主题、字号、
  缩进、输出面板状态等偏好保存到用户配置目录，重新启动后继续生效。
- **Windows 集成**：支持暗色标题栏和免圆角窗口；支持拖动分隔条调整输出面板高度。

## 环境要求

- Windows 10 / 11
- Python 3.10 或更高版本，并带有标准 `tkinter`
- Free Pascal Compiler（FPC）

`fpc.exe` 可以通过以下方式被程序发现：

1. 放入 `PATH`；
2. 设置环境变量 `PASCAL_BOX_FPC` 为完整可执行文件路径；
3. 检查常见的 FPC 安装目录。

例如，在 PowerShell 中临时指定编译器：

```powershell
$env:PASCAL_BOX_FPC="C:\FPC\3.2.2\bin\i386-Win32\fpc.exe"
python main.py
```

## 安装与启动

不需要额外安装第三方 Python 包。

```bat
cd /d "项目目录"
python main.py
```

最简单的 Windows 启动方式：双击 `run.bat`。启动时可直接传入一个或多个文件：

```bat
python main.py samples\hello.pas
python main.py samples\hello.pas samples\triangle.pas
```

传入不存在的路径时，Pascal Box 会尝试创建一个以该路径为目标的新标签。
查看版本：

```bat
python main.py --version
```

如果使用 `run.bat`，且 `pythonw` 可用，启动窗口不会附带命令行；需要查看异常时
请使用 `python main.py` 启动。

## 使用 Nuitka 打包

在 Windows 上安装 Nuitka 后运行：

```bat
python -m pip install nuitka
build_nuitka.bat
```

也可以直接执行：

```bat
python -m nuitka main.py --standalone --enable-plugin=tk-inter ^
  --windows-console-mode=disable --assume-yes-for-downloads --zig ^
  --output-dir=dist --output-filename=PascalBox.exe ^
  --include-data-dir=samples=samples --include-data-files=README.md=README.md
```

生成结果位于 `dist\main.dist\`，入口为 `PascalBox.exe`。将整个 `main.dist`
文件夹复制到目标电脑即可运行，无需安装 Python。首次使用 `--zig` 时 Nuitka 会自动
下载 Zig 编译器；后续构建会使用本地缓存。

- 设置文件会保存在 `PascalBox.exe` 同级目录。
- `samples\` 与 `README.md` 会被一并复制到发布目录。
- Nuitka 只打包 IDE；目标电脑仍需安装 Free Pascal Compiler 才能编译程序，或将
  `PASCAL_BOX_FPC` 指向 `fpc.exe`。
- 若目标目录不可写，设置无法保存；请把程序放在有写入权限的目录中。

## 快捷键

| 快捷键 | 作用 |
| --- | --- |
| `Ctrl+N` | 新建文件 |
| `Ctrl+O` | 打开文件（可多选） |
| `Ctrl+S` | 保存 |
| `Ctrl+Shift+S` | 另存为 |
| `Ctrl+W` | 关闭当前标签 |
| `Ctrl+Z` / `Ctrl+Y` | 撤销 / 重做 |
| `Ctrl+A` | 全选 |
| `Ctrl+F` | 查找 |
| `Ctrl+H` | 查找并替换 |
| `F3` / `Shift+F3` | 查找下一个 / 上一个 |
| `Esc` | 关闭查找栏 |
| `Tab` / `Shift+Tab` | 增加 / 减少缩进 |
| `Ctrl+Tab` / `Ctrl+Shift+Tab` | 切换标签 |
| `F6` | 编译当前文件 |
| `F7` | 运行已编译程序 |
| `F5` | 编译并运行 |
| `Ctrl+F2` | 停止程序 |
| `Ctrl+=` / `Ctrl+-` / `Ctrl+0` | 增大 / 减小 / 重置字号 |
| `Ctrl+T` | 切换亮色 / 暗色主题 |
| `Ctrl+`` | 显示 / 隐藏输出面板 |

## 查找与替换

按 `Ctrl+F` 在编辑器右上角打开查找栏；再按 `Ctrl+H` 展开替换行。查找栏会高亮当前
文档中的全部匹配，并在右上角显示匹配计数。`Aa` 与“全字”按钮分别切换区分大小写和
全字匹配；查找和替换都遵循这两个选项。

- `Enter`：查找下一个；`Shift+Enter`：查找上一个。
- `F3` / `Shift+F3`：在查找栏关闭后继续循环查找。
- “替换”只替换当前匹配并自动跳到下一处；“全部替换”会一次替换所有匹配。
- `Esc` 或右上角 `×` 关闭查找栏；替换操作可以用 `Ctrl+Z` 撤销。
- 打开查找栏时，如果编辑器中已有单行选中文本，会自动填入查找框。

## 编译与运行

编译前会自动保存当前文件。编译命令采用以下等价参数：

```text
fpc -Mobjfpc -Sh -O2 -vw -o"源文件同名.exe" "源文件名"
```

编译工作目录是源文件所在目录，因此同目录单元和相对路径文件访问可以正常工作。
编译产物（`.exe`、`.o`、`.ppu` 等）位于源文件旁边。

- `F6`：只编译，不运行。
- `F7`：运行已有可执行文件；找不到时会提示先编译。
- `F5`：先编译，成功后打开独立 Windows 终端运行。
- 程序运行期间不可再次编译；使用 `Ctrl+F2` 或菜单中的“停止程序”关闭它。

示例：

```bat
python main.py samples\triangle.pas
```

打开后按 `F5` 编译并运行，在弹出的终端窗口中输入数据；程序退出后终端不会立即
消失，便于查看输出。

## 文件编码与换行

读取文件时依次识别：

- UTF-8（含 UTF-8 BOM）
- UTF-16（含 BOM）
- GB18030
- 最终回退为 CP1252

保存时保留当前文档的编码和换行符；未保存的同名文档将保留自动检测到的格式。
新建文档默认使用 UTF-8 编码和 CRLF 换行。

## 配置与日志

用户偏好保存到程序目录下的 `settings.json`，与 `main.py`、`run.bat` 同级：

- 源码运行：`pascal-box/settings.json`
- 打包运行：`PascalBox.exe` 所在目录下的 `settings.json`

该文件在首次修改设置时自动创建，并已加入 `.gitignore`。若程序目录不可写，设置将
无法保存；可将整个程序放到有写入权限的目录中运行。

配置项包括主题模式、缩进宽度、空格/制表符模式、字号、最后打开目录、输出面板状态和高度。

## 项目结构

```text
pascal-box/
├─ main.py                 # 命令行入口与 DPI 初始化
├─ run.bat                 # Windows 启动脚本
├─ build_nuitka.bat        # Nuitka Windows 打包脚本
├─ pascalbox/
│  ├─ app.py               # 主窗口、标签、菜单、文件与构建流程
│  ├─ editor.py            # 编辑器、行号、括号、缩进与文件读写
│  ├─ searchbar.py         # 内联查找、替换与匹配高亮
│  ├─ highlighter.py       # Pascal 词法扫描与语法高亮
│  ├─ runner.py            # FPC 探测、异步编译和终端运行
│  ├─ widgets.py           # 方角按钮、标签栏、滚动条和面板标签
│  ├─ sharp_menu.py        # 自绘深色弹出菜单
│  ├─ dialogs.py           # 缩进、快捷键和关于对话框
│  ├─ settings.py          # JSON 偏好设置
│  └─ theme.py             # 色板与字体
├─ samples/
│  ├─ hello.pas
│  └─ triangle.pas         # ReadLn 交互示例
└─ docs/
   └─ screenshot.png
```

## 常见问题

**提示“未找到 Free Pascal 编译器 fpc”**

确认 `fpc -iV` 能在命令行运行，或设置 `PASCAL_BOX_FPC` 指向完整的 `fpc.exe` 路径。

**双击运行后窗口无法显示或立即退出**

使用 `python main.py` 启动以查看 Python 异常；确认系统已安装完整的 Tkinter 支持。

**编译成功但无法运行**

F7 只运行上一次生成的可执行文件。先按 F6/F5；使用 F5 可自动编译并运行。

**中文或旧编码源文件显示异常**

保存前可在状态栏确认检测到的编码。程序会尝试 UTF-8、BOM 编码和 GB18030，无法识别的
二进制或私有编码可能无法完整恢复。

## 当前边界

这是刻意保持轻量的编辑器。当前不包含调试器、断点、代码补全引擎、LSP、查找替换、
代码重构、工程文件管理或内置终端输入。目标是把“编写 Pascal、编译、运行、查看
编译诊断”做得直接可靠。
