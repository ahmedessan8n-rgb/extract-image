# 1. استخدام صورة بايثون رسمية وخفيفة
FROM python:3.9-slim

# 2. تحديث النظام وتثبيت المكتبات اللازمة لـ PyMuPDF (إذا لزم الأمر)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 3. تحديد مسار العمل داخل الحاوية
WORKDIR /code

# 4. نسخ ملف المتطلبات وتثبيته
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# 5. نسخ باقي ملفات المشروع (main.py)
COPY . .

# 6. تشغيل السيرفر باستخدام uvicorn على منفذ 7860
# ملاحظة: Hugging Face يتوقع دائماً أن يعمل السيرفر على هذا المنفذ
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
