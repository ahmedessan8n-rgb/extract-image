import fitz  # PyMuPDF
from fastapi import FastAPI, UploadFile, File
import base64
import os
from io import BytesIO
from PIL import Image

app = FastAPI()

def is_mostly_solid(img: Image.Image, dark_thresh=10, light_thresh=245, ratio=0.95) -> bool:
    small = img.convert("L").resize((50, 50))
    pixels = list(small.getdata())
    n = len(pixels)
    dark = sum(1 for p in pixels if p <= dark_thresh)
    light = sum(1 for p in pixels if p >= light_thresh)
    return (dark / n >= ratio) or (light / n >= ratio)

@app.post("/extract")
async def extract_data(file: UploadFile = File(...)):
    temp_path = f"raw_{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(await file.read())

    try:
        doc = fitz.open(temp_path)
        extracted_pages = []
        processed_xrefs = set()  # لتجنّب التكرار
        prompt_parts = []  # سنجمع هنا نص كل صفحة بالترتيب

        for page_index in range(len(doc)):
            page = doc[page_index]
            page_text = page.get_text().strip()
            # أضف فقرة النص للـ prompt العام مع عنوان الصفحة
            prompt_parts.append(f"--- Page {page_index + 1} ---\n{page_text}")

            page_images = []
            for img in page.get_images(full=True):
                xref = img[0]
                if xref in processed_xrefs:
                    continue

                try:
                    img_dict = doc.extract_image(xref)
                    if not img_dict or "image" not in img_dict:
                        processed_xrefs.add(xref)
                        continue

                    img_bytes = img_dict["image"]
                    ext = img_dict.get("ext", "png").lower()

                    pil_img = Image.open(BytesIO(img_bytes))
                    pil_img.load()

                    # تجاهل الصور صغيرة الحجم
                    if pil_img.width < 120 or pil_img.height < 120:
                        processed_xrefs.add(xref)
                        continue

                    # تجاهل الصور Solids (أسود/أبيض) النافعة فقط كلوح فارغ
                    if is_mostly_solid(pil_img):
                        processed_xrefs.add(xref)
                        continue

                    # تحويل للصيغة RGB إن لزم ثم حفظ JPEG في الذاكرة
                    if pil_img.mode not in ("RGB", "L"):
                        pil_img = pil_img.convert("RGB")
                    elif pil_img.mode == "L":
                        pil_img = pil_img.convert("RGB")

                    out_buf = BytesIO()
                    pil_img.save(out_buf, format="JPEG", quality=85)
                    out_buf.seek(0)
                    final_bytes = out_buf.read()

                    img_base64 = base64.b64encode(final_bytes).decode("utf-8")

                    # أضف الصورة مع بيانات وصفية لتسهيل المعالجة لاحقًا
                    page_images.append({
                        "id": f"img_{xref}",
                        "data": img_base64,
                        "ext": "jpg",
                        "width": pil_img.width,
                        "height": pil_img.height,
                        "orig_ext": ext,
                        "page": page_index + 1
                    })

                    processed_xrefs.add(xref)

                except Exception:
                    # تجاهل أي صورة سببت استثناء واستمر
                    processed_xrefs.add(xref)
                    continue

            extracted_pages.append({
                "page": page_index + 1,
                "text": page_text,
                "images": page_images
            })

        # اجمع كل نصوص الصفحات في promptText واحد (ترتيب تصاعدي)
        prompt_text = "\n\n".join(prompt_parts).strip()

        return {
            "content": extracted_pages,
            "promptText": prompt_text
        }

    except Exception as e:
        return {"error": str(e)}
    finally:
        if 'doc' in locals():
            try:
                doc.close()
            except:
                pass
        if os.path.exists(temp_path):
            os.remove(temp_path)
