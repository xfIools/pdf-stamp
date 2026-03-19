import io
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from PIL import Image
import fitz  # PyMuPDF

app = Flask(__name__)
CORS(app)


def find_stamp_position(page: fitz.Page, stamp_size: float, padding: float = 8.0) -> tuple:
    """
    纯算法找印章位置：
    1. 收集页面所有内容块（文字 + 图片 + 矢量线段/路径）的bbox
    2. 按优先级扫描候选位置（底部→顶部，右→左→中）
    3. 找第一个与所有内容块都不重叠的位置
    """
    page_w = page.rect.width
    page_h = page.rect.height
    half = stamp_size / 2
    margin = half + padding

    occupied = []

    # 文字块 padding 用印章半径，确保印章整体不会压到文字
    text_pad = half + padding

    # 1. 文字块
    for block in page.get_text("blocks"):
        x0, y0, x1, y1 = block[0], block[1], block[2], block[3]
        occupied.append(fitz.Rect(x0 - text_pad, y0 - text_pad, x1 + text_pad, y1 + text_pad))

    # 2. 图片块
    for img in page.get_images(full=True):
        for item in page.get_image_rects(img[0]):
            occupied.append(fitz.Rect(
                item.x0 - text_pad, item.y0 - text_pad,
                item.x1 + text_pad, item.y1 + text_pad
            ))

    # 3. 矢量图形（线段、矩形框、表格线、签名线等）
    # 关键：对每条线段按方向单独扩展，避免把整个表格区域当成一整块占用
    line_pad = max(padding, 4.0)
    for drawing in page.get_drawings():
        items = drawing.get("items", [])
        r = drawing.get("rect")
        if r is None:
            continue
        w = r.x1 - r.x0
        h = r.y1 - r.y0
        if w < 2 or h < 2:
            # 纯线段（水平或垂直）：只在垂直于线段的方向扩展
            if w < 2:
                # 竖线：只扩展左右
                occupied.append(fitz.Rect(r.x0 - line_pad, r.y0, r.x1 + line_pad, r.y1))
            else:
                # 横线：只扩展上下
                occupied.append(fitz.Rect(r.x0, r.y0 - line_pad, r.x1, r.y1 + line_pad))
        else:
            # 有面积的图形（矩形、填充区域等）：四周都扩展
            occupied.append(fitz.Rect(r.x0 - padding, r.y0 - padding, r.x1 + padding, r.y1 + padding))

    def is_free(cx, cy):
        stamp_rect = fitz.Rect(cx - half, cy - half, cx + half, cy + half)
        for occ in occupied:
            if stamp_rect.intersects(occ):
                return False
        return True

    # 全页网格扫描：从底部往上、从右往左，步长40%印章尺寸
    # 足够细密，能落进表格单元格，也能找到页面空白区域
    step = stamp_size * 0.4
    y = page_h - margin
    while y >= margin:
        x = page_w - margin
        while x >= margin:
            if is_free(x, y):
                print(f"  找到空白位置: PDF坐标({x:.1f}, {y:.1f})")
                return x, y
            x -= step
        y -= step

    # 最终兜底
    print("  页面过满，使用右下角兜底")
    return page_w - margin, page_h - margin


@app.route("/stamp", methods=["POST"])
def stamp_pdf():
    if "pdf" not in request.files or "stamp" not in request.files:
        return jsonify({"error": "请上传 pdf 和 stamp 文件"}), 400

    pdf_file = request.files["pdf"]
    stamp_file = request.files["stamp"]

    stamp_img = Image.open(stamp_file).convert("RGBA")
    stamp_size = 100  # 印章尺寸（PDF点单位）

    pdf_bytes = pdf_file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    # 预先把印章转为PNG字节（只做一次）
    stamp_buf = io.BytesIO()
    stamp_img.save(stamp_buf, format="PNG")
    stamp_bytes = stamp_buf.getvalue()

    for page_index in range(len(doc)):
        page = doc[page_index]
        print(f"处理第 {page_index + 1} 页...")

        cx, cy = find_stamp_position(page, stamp_size)
        half = stamp_size / 2
        rect = fitz.Rect(cx - half, cy - half, cx + half, cy + half)
        page.insert_image(rect, stream=stamp_bytes, overlay=True)

    out_buf = io.BytesIO()
    doc.save(out_buf)
    doc.close()
    out_buf.seek(0)

    return send_file(
        out_buf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="stamped.pdf"
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
