# PDF 自动盖章工具

自动识别 PDF 每页空白区域并盖章，**不压文字、不压线段、不压图片**，支持表格内空白单元格识别。纯算法实现，无需 AI，无需联网。

## 功能特点

- 自动检测文字块、图片、矢量线段（表格线、签名线等）的占用区域
- 全页网格扫描，优先底部右侧，优先盖章在空白位置，能精确落进表格空白单元格
- 印章与内容保持安全间距，彻底避免压字
- 支持 PNG 透明背景印章

---

## 直接下载使用（无需安装）

### Windows 桌面工具（exe）

前往 [Releases](../../releases/latest) 下载 `PDF盖章工具.exe`，双击运行，自动打开浏览器，上传 PDF 和印章图片即可。

### Java SDK

前往 [Releases](../../releases/latest) 下载 `pdf-stamp-sdk-1.0.0.jar`，加入项目 classpath，三行代码完成盖章：

```java
PdfStamper stamper = new PdfStamper.Builder().stampSize(80).build();
byte[] result = stamper.stamp(pdfBytes, stampImageBytes);
// 或文件版本
stamper.stamp(new File("in.pdf"), new File("stamp.png"), new File("out.pdf"));
```

详细文档见 [pdf-stamp-sdk/README.md](pdf-stamp-sdk/README.md)

---

## 从源码运行（Python Web 版）

```bash
cd pdf-stamp/backend
pip install -r requirements.txt
python app.py
```

然后用浏览器打开 `pdf-stamp/frontend/index.html`，或直接运行 `main.py` 自动打开浏览器：

```bash
cd pdf-stamp
python main.py
```

---

## 项目结构

```
├── pdf-stamp/
│   ├── backend/
│   │   ├── app.py              # Flask 后端（独立运行版）
│   │   └── requirements.txt
│   ├── frontend/
│   │   └── index.html          # 前端页面
│   ├── main.py                 # 单文件启动（前后端合一）
│   ├── build.bat               # Windows 打包脚本
│   └── dist/
│       └── PDF盖章工具.exe      # 打包好的 Windows 可执行文件
│
└── pdf-stamp-sdk/
    ├── pom.xml
    ├── README.md               # Java SDK 使用说明
    ├── src/main/java/com/pdfstamp/
    │   ├── PdfStamper.java     # 核心 SDK
    │   ├── StampPosition.java
    │   └── OccupiedRegion.java
    └── target/
        └── pdf-stamp-sdk-1.0.0.jar  # 打包好的 fat jar
```

---

## 技术栈

- Python：Flask、PyMuPDF、Pillow
- Java：Apache PDFBox 2.x（兼容 Java 8+）

## License

MIT
