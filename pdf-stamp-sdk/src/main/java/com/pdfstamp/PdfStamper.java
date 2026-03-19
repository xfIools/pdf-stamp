package com.pdfstamp;

import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.image.PDImageXObject;
import org.apache.pdfbox.text.PDFTextStripper;
import org.apache.pdfbox.text.TextPosition;
import org.apache.pdfbox.contentstream.PDFStreamEngine;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.contentstream.operator.state.*;
import org.apache.pdfbox.contentstream.operator.DrawObject;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.util.Matrix;

import java.awt.geom.Rectangle2D;
import java.io.*;
import java.util.ArrayList;
import java.util.List;

/**
 * PDF 自动盖章 SDK
 *
 * <p>核心能力：
 * <ul>
 *   <li>自动检测每页文字块、图片、矢量线段的占用区域</li>
 *   <li>按优先级（底部→顶部，右→左→中）扫描空白位置</li>
 *   <li>印章不压文字、不压线段、不压图片</li>
 * </ul>
 *
 * <p>快速使用：
 * <pre>{@code
 * PdfStamper stamper = new PdfStamper.Builder()
 *     .stampSize(80)
 *     .padding(8)
 *     .build();
 * byte[] result = stamper.stamp(pdfBytes, stampImageBytes);
 * }</pre>
 */
public class PdfStamper {

    private final float stampSize;
    private final float padding;

    private PdfStamper(Builder builder) {
        this.stampSize = builder.stampSize;
        this.padding   = builder.padding;
    }

    // -------------------------------------------------------------------------
    // 公开 API
    // -------------------------------------------------------------------------

    /**
     * 对 PDF 每页自动盖章
     *
     * @param pdfBytes        原始 PDF 字节
     * @param stampImageBytes 印章图片字节（PNG/JPG，推荐透明背景PNG）
     * @return 盖章后的 PDF 字节
     */
    public byte[] stamp(byte[] pdfBytes, byte[] stampImageBytes) throws IOException {
        try (PDDocument doc = PDDocument.load(pdfBytes)) {
            PDImageXObject stampImage = PDImageXObject.createFromByteArray(doc, stampImageBytes, "stamp");

            for (int i = 0; i < doc.getNumberOfPages(); i++) {
                PDPage page = doc.getPage(i);
                PDRectangle mediaBox = page.getMediaBox();

                List<OccupiedRegion> occupied = collectOccupied(doc, page, i);
                StampPosition pos = findPosition(occupied, mediaBox.getWidth(), mediaBox.getHeight());

                float half = stampSize / 2f;
                try (PDPageContentStream cs = new PDPageContentStream(
                        doc, page, PDPageContentStream.AppendMode.APPEND, true, true)) {
                    cs.drawImage(stampImage, pos.cx - half, pos.cy - half, stampSize, stampSize);
                }
            }

            ByteArrayOutputStream out = new ByteArrayOutputStream();
            doc.save(out);
            return out.toByteArray();
        }
    }

    /**
     * 文件路径版本（便捷方法）
     */
    public void stamp(File inputPdf, File stampImage, File outputPdf) throws IOException {
        byte[] result = stamp(readFile(inputPdf), readFile(stampImage));
        try (FileOutputStream fos = new FileOutputStream(outputPdf)) {
            fos.write(result);
        }
    }

    /**
     * 仅查询某页的印章建议位置，不修改PDF（用于预览/调试）
     *
     * @param pdfBytes  PDF 字节
     * @param pageIndex 页码（从0开始）
     */
    public StampPosition findStampPosition(byte[] pdfBytes, int pageIndex) throws IOException {
        try (PDDocument doc = PDDocument.load(pdfBytes)) {
            PDPage page = doc.getPage(pageIndex);
            PDRectangle mediaBox = page.getMediaBox();
            List<OccupiedRegion> occupied = collectOccupied(doc, page, pageIndex);
            return findPosition(occupied, mediaBox.getWidth(), mediaBox.getHeight());
        }
    }

    // -------------------------------------------------------------------------
    // 核心算法
    // -------------------------------------------------------------------------

    private List<OccupiedRegion> collectOccupied(PDDocument doc, PDPage page, int pageIndex) throws IOException {
        List<OccupiedRegion> occupied = new ArrayList<>();
        float pad = padding;
        float linePad = Math.max(padding, 4f);

        // 1. 文字块 —— padding 用印章半径，确保印章整体不会压到文字
        float textPad = padding + (stampSize / 2f);
        TextBoundsCollector textCollector = new TextBoundsCollector();
        textCollector.setStartPage(pageIndex + 1);
        textCollector.setEndPage(pageIndex + 1);
        textCollector.getText(doc);
        for (Rectangle2D r : textCollector.getTextBounds()) {
            occupied.add(expand(r, textPad));
        }

        // 2. 图片 + 3. 矢量路径（统一用内容流引擎解析）
        GraphicsCollector gc = new GraphicsCollector(page);
        gc.processPage(page);
        for (Rectangle2D r : gc.getImageBounds()) {
            occupied.add(expand(r, textPad));  // 图片同样用 textPad
        }
        // 线段按方向智能扩展：水平线只扩展上下，竖线只扩展左右，避免撑开整个表格区域
        for (Rectangle2D r : gc.getVectorBounds()) {
            double w = r.getWidth();
            double h = r.getHeight();
            if (w < 2 || h < 2) {
                if (w < 2) {
                    // 竖线：只扩展左右
                    occupied.add(new OccupiedRegion(
                        (float) r.getX() - linePad, (float) r.getY(),
                        (float) (r.getX() + w) + linePad, (float) (r.getY() + h)));
                } else {
                    // 横线：只扩展上下
                    occupied.add(new OccupiedRegion(
                        (float) r.getX(), (float) r.getY() - linePad,
                        (float) (r.getX() + w), (float) (r.getY() + h) + linePad));
                }
            } else {
                occupied.add(expand(r, pad));
            }
        }

        return occupied;
    }

    private OccupiedRegion expand(Rectangle2D r, float pad) {
        return new OccupiedRegion(
            (float) r.getX() - pad,
            (float) r.getY() - pad,
            (float) (r.getX() + r.getWidth()) + pad,
            (float) (r.getY() + r.getHeight()) + pad
        );
    }

    private StampPosition findPosition(List<OccupiedRegion> occupied, float pageW, float pageH) {
        float half   = stampSize / 2f;
        float margin = half + padding;

        // 全页网格扫描：步长40%印章尺寸，从底部往上、从右往左
        // 足够细密，能落进表格单元格，也能找到页面空白区域
        float step = stampSize * 0.4f;
        for (float y = pageH - margin; y >= margin; y -= step) {
            for (float x = pageW - margin; x >= margin; x -= step) {
                if (isFree(occupied, x, y, half)) {
                    return new StampPosition(x, y);
                }
            }
        }

        return new StampPosition(pageW - margin, margin);
    }

    private boolean isFree(List<OccupiedRegion> occupied, float cx, float cy, float half) {
        float rx0 = cx - half, ry0 = cy - half, rx1 = cx + half, ry1 = cy + half;
        for (OccupiedRegion occ : occupied) {
            if (occ.intersects(rx0, ry0, rx1, ry1)) return false;
        }
        return true;
    }

    private float clamp(float val, float min, float max) {
        return Math.max(min, Math.min(max, val));
    }

    private byte[] readFile(File f) throws IOException {
        try (FileInputStream fis = new FileInputStream(f);
             ByteArrayOutputStream bos = new ByteArrayOutputStream()) {
            byte[] buf = new byte[8192];
            int n;
            while ((n = fis.read(buf)) != -1) bos.write(buf, 0, n);
            return bos.toByteArray();
        }
    }

    // -------------------------------------------------------------------------
    // 内部辅助类
    // -------------------------------------------------------------------------

    /** 收集文字边界框 */
    private static class TextBoundsCollector extends PDFTextStripper {
        private final List<Rectangle2D> bounds = new ArrayList<>();

        TextBoundsCollector() throws IOException {
            setSortByPosition(true);
        }

        @Override
        protected void processTextPosition(TextPosition text) {
            float x = text.getXDirAdj();
            float y = text.getPageHeight() - text.getYDirAdj() - text.getHeightDir();
            float w = text.getWidthDirAdj();
            float h = text.getHeightDir();
            if (w > 0 && h > 0) {
                bounds.add(new Rectangle2D.Float(x, y, w, h));
            }
        }

        List<Rectangle2D> getTextBounds() { return bounds; }
    }

    /** 统一收集图片和矢量路径的边界框 */
    private static class GraphicsCollector extends PDFStreamEngine {
        private final List<Rectangle2D> imageBounds  = new ArrayList<>();
        private final List<Rectangle2D> vectorBounds = new ArrayList<>();
        private final PDPage page;
        // 当前路径点
        private final List<float[]> currentPath = new ArrayList<>();

        GraphicsCollector(PDPage page) throws IOException {
            this.page = page;
            addOperator(new Concatenate());
            addOperator(new Save());
            addOperator(new Restore());
            addOperator(new SetMatrix());
            addOperator(new DrawObject());
        }

        @Override
        protected void processOperator(Operator operator, List<COSBase> operands) throws IOException {
            String op = operator.getName();
            float pageH = page.getMediaBox().getHeight();

            switch (op) {
                case "Do": {
                    // 图片绘制
                    Matrix ctm = getGraphicsState().getCurrentTransformationMatrix();
                    float x = ctm.getTranslateX();
                    float y = ctm.getTranslateY();
                    float w = Math.abs(ctm.getScaleX());
                    float h = Math.abs(ctm.getScaleY());
                    if (w > 0 && h > 0) {
                        imageBounds.add(new Rectangle2D.Float(x, pageH - y, w, h));
                    }
                    break;
                }
                case "m": // moveto
                    if (operands.size() >= 2) {
                        currentPath.add(new float[]{
                            ((COSNumber) operands.get(0)).floatValue(),
                            ((COSNumber) operands.get(1)).floatValue()
                        });
                    }
                    break;
                case "l": // lineto
                    if (operands.size() >= 2) {
                        currentPath.add(new float[]{
                            ((COSNumber) operands.get(0)).floatValue(),
                            ((COSNumber) operands.get(1)).floatValue()
                        });
                    }
                    break;
                case "re": // rectangle
                    if (operands.size() >= 4) {
                        float x = ((COSNumber) operands.get(0)).floatValue();
                        float y = ((COSNumber) operands.get(1)).floatValue();
                        float w = Math.abs(((COSNumber) operands.get(2)).floatValue());
                        float h = Math.abs(((COSNumber) operands.get(3)).floatValue());
                        vectorBounds.add(new Rectangle2D.Float(x, pageH - y - h, w, h));
                    }
                    break;
                case "S":  // stroke
                case "s":  // closepath + stroke
                case "f":  // fill
                case "F":
                case "f*":
                case "B":  // fill + stroke
                case "B*":
                case "b":
                case "b*":
                    flushCurrentPath(pageH);
                    break;
                case "n":  // end path (no paint)
                    currentPath.clear();
                    break;
                default:
                    super.processOperator(operator, operands);
            }
        }

        private void flushCurrentPath(float pageH) {
            if (currentPath.isEmpty()) return;
            float minX = Float.MAX_VALUE, minY = Float.MAX_VALUE;
            float maxX = -Float.MAX_VALUE, maxY = -Float.MAX_VALUE;
            for (float[] pt : currentPath) {
                if (pt[0] < minX) minX = pt[0];
                if (pt[0] > maxX) maxX = pt[0];
                if (pt[1] < minY) minY = pt[1];
                if (pt[1] > maxY) maxY = pt[1];
            }
            vectorBounds.add(new Rectangle2D.Float(minX, pageH - maxY, maxX - minX, maxY - minY));
            currentPath.clear();
        }

        List<Rectangle2D> getImageBounds()  { return imageBounds; }
        List<Rectangle2D> getVectorBounds() { return vectorBounds; }
    }

    // -------------------------------------------------------------------------
    // Builder
    // -------------------------------------------------------------------------

    public static class Builder {
        private float stampSize = 80f;
        private float padding   = 8f;

        /** 印章尺寸，单位：PDF点（1pt≈0.353mm，A4页宽约595pt）。默认80 */
        public Builder stampSize(float stampSize) { this.stampSize = stampSize; return this; }

        /** 印章与周围内容的最小间距（PDF点）。默认8 */
        public Builder padding(float padding) { this.padding = padding; return this; }

        public PdfStamper build() { return new PdfStamper(this); }
    }
}
