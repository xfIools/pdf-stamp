# PDF Stamp SDK — 使用说明书

自动识别 PDF 每页空白区域并盖章，避开所有文字、图片、线段。纯 Java 实现，无需 AI，基于 Apache PDFBox。

---

## 环境要求

- Java 8+
- Maven 3.3+

---

## 快速集成

### 方式一：Maven 引入（推荐）

将 SDK 安装到本地仓库：

```bash
cd pdf-stamp-sdk
mvn install -DskipTests
```

在你的项目 `pom.xml` 中添加：

```xml
<dependency>
    <groupId>com.pdfstamp</groupId>
    <artifactId>pdf-stamp-sdk</artifactId>
    <version>1.0.0</version>
</dependency>
```

### 方式二：直接引入 Fat Jar

```bash
mvn package -DskipTests
```

生成的 `target/pdf-stamp-sdk-1.0.0.jar` 已包含所有依赖，直接加入项目 classpath 即可。

> 注意：target 目录下还会生成 `original-pdf-stamp-sdk-1.0.0.jar`（仅含SDK代码，不含依赖）和 `pdf-stamp-sdk-1.0.0-shaded.jar`（中间产物），这两个忽略即可，只用 `pdf-stamp-sdk-1.0.0.jar`。

---

## 使用示例

### 基础用法（字节数组）

```java
import com.pdfstamp.PdfStamper;
import java.nio.file.Files;
import java.nio.file.Paths;

// 构建 Stamper（使用默认参数）
PdfStamper stamper = new PdfStamper.Builder().build();

// 读取文件
byte[] pdfBytes   = Files.readAllBytes(Paths.get("input.pdf"));
byte[] stampBytes = Files.readAllBytes(Paths.get("stamp.png"));

// 盖章，返回新 PDF 字节
byte[] result = stamper.stamp(pdfBytes, stampBytes);

// 保存
Files.write(Paths.get("output.pdf"), result);
```

### 文件路径版本

```java
PdfStamper stamper = new PdfStamper.Builder().build();

stamper.stamp(
    new File("input.pdf"),
    new File("stamp.png"),
    new File("output.pdf")
);
```

### 自定义印章大小和间距

```java
PdfStamper stamper = new PdfStamper.Builder()
    .stampSize(100)   // 印章尺寸100pt（约35mm），默认80
    .padding(10)      // 与周围内容保持10pt间距，默认8
    .build();
```

### 仅查询印章位置（不修改PDF，用于预览）

```java
PdfStamper stamper = new PdfStamper.Builder().build();
byte[] pdfBytes = Files.readAllBytes(Paths.get("input.pdf"));

// 查询第0页（第一页）的建议印章位置
StampPosition pos = stamper.findStampPosition(pdfBytes, 0);
System.out.println("建议位置: cx=" + pos.cx + ", cy=" + pos.cy);
// 注意：坐标系原点在页面左下角（PDF标准坐标系）
```

### Spring Boot 集成示例

```java
@RestController
public class StampController {

    private final PdfStamper stamper = new PdfStamper.Builder()
            .stampSize(80)
            .build();

    @PostMapping("/stamp")
    public ResponseEntity<byte[]> stamp(
            @RequestParam MultipartFile pdf,
            @RequestParam MultipartFile stamp) throws IOException {

        byte[] result = stamper.stamp(pdf.getBytes(), stamp.getBytes());

        return ResponseEntity.ok()
                .header("Content-Disposition", "attachment; filename=stamped.pdf")
                .contentType(MediaType.APPLICATION_PDF)
                .body(result);
    }
}
```

---

## 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `stampSize` | float | 80 | 印章尺寸（PDF点单位）。A4页宽约595pt，80pt ≈ 28mm |
| `padding` | float | 8 | 印章与周围内容的最小间距（PDF点）|

**PDF点与毫米换算：** 1pt = 0.3528mm，1mm ≈ 2.835pt

常用印章尺寸参考：
- 圆形公章（直径40mm）≈ 113pt
- 椭圆财务章（长轴40mm）≈ 113pt  
- 个人名章（20mm）≈ 57pt

---

## 算法说明

盖章位置查找分三步：

1. **收集占用区域** — 扫描页面所有文字块、图片、矢量路径（线段/矩形框/表格线），每个区域加 `padding` 缓冲
2. **候选位置扫描** — 按优先级遍历预设候选点：
   - Y 方向：从底部（93%）往上（10%）
   - X 方向：右侧（85%）→ 左侧（15%）→ 右1/4 → 左1/4 → 中间
   - 找到第一个与所有占用区域不重叠的位置即返回
3. **密集扫描兜底** — 若候选点全部被占用，以 `stampSize * 0.6` 为步长密集扫描整页

坐标系：PDFBox 使用左下角为原点的标准 PDF 坐标系。

---

## 印章图片建议

- 格式：PNG（支持透明背景，盖章效果更自然）
- 背景：透明或白色
- 分辨率：建议 300×300px 以上，保证清晰度
- 颜色：红色公章效果最佳

---

## 常见问题

**Q: 印章尺寸单位是什么？**  
A: PDF 点（pt），1pt ≈ 0.353mm。A4 纸宽 210mm ≈ 595pt，高 297mm ≈ 842pt。

**Q: 支持哪些 PDF 类型？**  
A: 支持标准 PDF 1.x ~ 2.0，加密 PDF 需先解密。扫描件（纯图片PDF）文字识别为空，印章会落在默认优先位置（右下角区域）。

**Q: 多页 PDF 每页都会盖章吗？**  
A: 是的，每页独立计算空白位置，各页印章位置可能不同。

**Q: 线程安全吗？**  
A: `PdfStamper` 实例无状态，线程安全，可在多线程环境中共享同一实例。

---

## 构建

```bash
# 编译
mvn compile

# 打包（含依赖的 fat jar）
mvn package -DskipTests

# 安装到本地 Maven 仓库
mvn install -DskipTests
```
