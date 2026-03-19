import io
import threading
import webbrowser
import time
import socket
import multiprocessing
from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
from PIL import Image
import fitz  # PyMuPDF
from waitress import serve

app = Flask(__name__)
CORS(app)

# 前端页面（内嵌HTML）
HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>PDF 智能盖章</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
      background: #f0f2f5;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
    }
    .card {
      background: #fff;
      border-radius: 12px;
      padding: 40px;
      width: 480px;
      box-shadow: 0 4px 24px rgba(0,0,0,0.08);
    }
    h1 { font-size: 22px; color: #1a1a1a; margin-bottom: 8px; }
    p.sub { color: #888; font-size: 14px; margin-bottom: 28px; }
    .upload-area {
      border: 2px dashed #d9d9d9;
      border-radius: 8px;
      padding: 20px;
      text-align: center;
      cursor: pointer;
      transition: border-color 0.2s;
      margin-bottom: 16px;
      position: relative;
    }
    .upload-area:hover { border-color: #4f6ef7; }
    .upload-area input[type="file"] {
      position: absolute; inset: 0; opacity: 0; cursor: pointer;
    }
    .upload-area .icon { font-size: 32px; margin-bottom: 8px; }
    .upload-area .label { color: #555; font-size: 14px; }
    .upload-area .filename { color: #4f6ef7; font-size: 13px; margin-top: 6px; }
    .preview-stamp { max-width: 80px; max-height: 80px; margin-top: 8px; border-radius: 4px; }
    button {
      width: 100%; padding: 14px; background: #4f6ef7; color: #fff;
      border: none; border-radius: 8px; font-size: 16px; cursor: pointer;
      margin-top: 8px; transition: background 0.2s;
    }
    button:hover:not(:disabled) { background: #3a57e8; }
    button:disabled { background: #b0b8f0; cursor: not-allowed; }
    .status { margin-top: 16px; font-size: 14px; color: #555; text-align: center; min-height: 20px; }
    .status.error { color: #e53e3e; }
    .status.success { color: #38a169; }
    .progress { width: 100%; height: 6px; background: #eee; border-radius: 3px; margin-top: 12px; overflow: hidden; display: none; }
    .progress-bar { height: 100%; background: #4f6ef7; width: 0%; transition: width 0.3s; border-radius: 3px; }
  </style>
</head>
<body>
  <div class="card">
    <h1>📄 PDF 智能盖章</h1>
    <p class="sub">自动识别每页空白区域，精准盖章，不压文字</p>
    <div class="upload-area">
      <input type="file" id="pdfInput" accept=".pdf" />
      <div class="icon">📑</div>
      <div class="label">点击上传 PDF 文件</div>
      <div class="filename" id="pdfName"></div>
    </div>
    <div class="upload-area">
      <input type="file" id="stampInput" accept="image/*" />
      <div class="icon">🔖</div>
      <div class="label">点击上传印章图片（支持PNG透明背景）</div>
      <div class="filename" id="stampName"></div>
      <img class="preview-stamp" id="stampPreview" style="display:none" />
    </div>
    <button id="submitBtn" disabled>开始盖章</button>
    <div class="progress" id="progressWrap">
      <div class="progress-bar" id="progressBar"></div>
    </div>
    <div class="status" id="status"></div>
  </div>
  <script>
    const pdfInput = document.getElementById("pdfInput");
    const stampInput = document.getElementById("stampInput");
    const submitBtn = document.getElementById("submitBtn");
    const status = document.getElementById("status");
    const progressWrap = document.getElementById("progressWrap");
    const progressBar = document.getElementById("progressBar");

    function checkReady() {
      submitBtn.disabled = !(pdfInput.files[0] && stampInput.files[0]);
    }
    pdfInput.addEventListener("change", () => {
      document.getElementById("pdfName").textContent = pdfInput.files[0]?.name || "";
      checkReady();
    });
    stampInput.addEventListener("change", () => {
      const file = stampInput.files[0];
      if (file) {
        document.getElementById("stampName").textContent = file.name;
        const preview = document.getElementById("stampPreview");
        preview.src = URL.createObjectURL(file);
        preview.style.display = "block";
      }
      checkReady();
    });
    submitBtn.addEventListener("click", async () => {
      const formData = new FormData();
      formData.append("pdf", pdfInput.files[0]);
      formData.append("stamp", stampInput.files[0]);
      submitBtn.disabled = true;
      status.className = "status";
      status.textContent = "正在处理中...";
      progressWrap.style.display = "block";
      let prog = 0;
      const timer = setInterval(() => {
        prog = Math.min(prog + 3, 90);
        progressBar.style.width = prog + "%";
      }, 200);
      try {
        const res = await fetch("/stamp", { method: "POST", body: formData });
        clearInterval(timer);
        progressBar.style.width = "100%";
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.error || "服务器错误");
        }
        const blob = await res.blob();
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "stamped.pdf";
        a.click();
        status.className = "status success";
        status.textContent = "✅ 盖章完成，已自动下载！";
      } catch (e) {
        clearInterval(timer);
        status.className = "status error";
        status.textContent = "❌ 出错：" + e.message;
      } finally {
        submitBtn.disabled = false;
        setTimeout(() => { progressBar.style.width = "0%"; progressWrap.style.display = "none"; }, 2000);
      }
    });
  </script>
</body>
</html>"""


@app.route("/")
def index():
    return Response(HTML, mimetype="text/html")


def find_stamp_position(page: fitz.Page, stamp_size: float, padding: float = 8.0) -> tuple:
    page_w = page.rect.width
    page_h = page.rect.height
    half = stamp_size / 2
    margin = half + padding

    occupied = []

    # 文字块 padding 用印章半径，确保印章整体不会压到文字
    text_pad = half + padding

    # 文字块
    for block in page.get_text("blocks"):
        x0, y0, x1, y1 = block[0], block[1], block[2], block[3]
        occupied.append(fitz.Rect(x0 - text_pad, y0 - text_pad, x1 + text_pad, y1 + text_pad))

    # 图片块
    for img in page.get_images(full=True):
        for item in page.get_image_rects(img[0]):
            occupied.append(fitz.Rect(
                item.x0 - text_pad, item.y0 - text_pad,
                item.x1 + text_pad, item.y1 + text_pad
            ))

    # 矢量图形（线段、矩形框、表格线等）
    for drawing in page.get_drawings():
        r = drawing.get("rect")
        if r is None:
            continue
        line_pad = max(padding, 4.0)
        w = r.x1 - r.x0
        h = r.y1 - r.y0
        if w < 2 or h < 2:
            # 纯线段：只在垂直于线段方向扩展，不横向撑开整个表格区域
            if w < 2:
                occupied.append(fitz.Rect(r.x0 - line_pad, r.y0, r.x1 + line_pad, r.y1))
            else:
                occupied.append(fitz.Rect(r.x0, r.y0 - line_pad, r.x1, r.y1 + line_pad))
        else:
            occupied.append(fitz.Rect(r.x0 - padding, r.y0 - padding, r.x1 + padding, r.y1 + padding))

    def is_free(cx, cy):
        r = fitz.Rect(cx - half, cy - half, cx + half, cy + half)
        return not any(r.intersects(occ) for occ in occupied)

    step = stamp_size * 0.4
    y = page_h - margin
    while y >= margin:
        x = page_w - margin
        while x >= margin:
            if is_free(x, y):
                return x, y
            x -= step
        y -= step

    return page_w - margin, page_h - margin


@app.route("/stamp", methods=["POST"])
def stamp_pdf():
    if "pdf" not in request.files or "stamp" not in request.files:
        return jsonify({"error": "请上传 pdf 和 stamp 文件"}), 400

    stamp_img = Image.open(request.files["stamp"]).convert("RGBA")
    stamp_size = 100

    pdf_bytes = request.files["pdf"].read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    stamp_buf = io.BytesIO()
    stamp_img.save(stamp_buf, format="PNG")
    stamp_bytes = stamp_buf.getvalue()

    for page_index in range(len(doc)):
        page = doc[page_index]
        cx, cy = find_stamp_position(page, stamp_size)
        half = stamp_size / 2
        page.insert_image(
            fitz.Rect(cx - half, cy - half, cx + half, cy + half),
            stream=stamp_bytes, overlay=True
        )

    out_buf = io.BytesIO()
    doc.save(out_buf)
    doc.close()
    out_buf.seek(0)
    return send_file(out_buf, mimetype="application/pdf",
                     as_attachment=True, download_name="stamped.pdf")


def find_free_port(preferred=5678):
    """从preferred端口开始找一个可用端口"""
    for port in range(preferred, preferred + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return preferred


def open_browser(port):
    time.sleep(2.0)
    webbrowser.open(f"http://localhost:{port}")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    port = find_free_port(5678)
    threading.Thread(target=open_browser, args=(port,), daemon=True).start()
    print(f"PDF 盖章工具已启动：http://localhost:{port}")
    serve(app, host="127.0.0.1", port=port)
