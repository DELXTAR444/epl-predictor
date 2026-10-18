# EPL ทายสกอร์
- `update.py` ดึงข้อมูล ฟิตโมเดล ทายผล เขียน `docs/data.json`
- `docs/index.html` หน้าเว็บ (GitHub Pages)
- `update.yml` ย้ายไปเป็น `.github/workflows/update.yml` เพื่อให้รันเองอัตโนมัติ
- `data/predictions.json` บันทึกผลที่ทายไว้ เทียบกับผลจริงทีหลัง
ปรับค่าความแรงตัวเจ็บที่ `COEF` ใน update.py
