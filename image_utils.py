from PIL import Image, ImageDraw, ImageFont
from barcode_utils import generate_barcode, extract_barcode_value, lookup_product_name
import numpy as np
import os
import re
import qrcode
import time

def safe_filename(s):
    return re.sub(r'[^A-Za-z0-9_.-]', '_', s)

def cleanup_old_files(directory='.', age_seconds=300):
    now = time.time()
    for fname in os.listdir(directory):
        if fname.startswith('result_') and fname.endswith('.jpg'):
            fpath = os.path.join(directory, fname)
            try:
                if os.path.isfile(fpath) and now - os.path.getmtime(fpath) > age_seconds:
                    os.remove(fpath)
            except Exception:
                pass

def create_result_images(qrs):
    cleanup_old_files()
    images = []
    font = ImageFont.load_default()
    for idx, qr in enumerate(qrs):
        title = qr['data']
        barcode_value = extract_barcode_value(qr['data'])
        product_name = lookup_product_name(barcode_value)
        # Генерируем QR-код заново
        qr_img_pil = qrcode.make(title)
        qr_size = 200
        qr_img_pil = qr_img_pil.resize((qr_size, qr_size), Image.NEAREST)
        barcode_img = generate_barcode(qr['data'])
        barcode_width, barcode_height = barcode_img.size
        width = max(qr_size, barcode_width, 400)
        height = 40 + qr_size + 20 + barcode_height + 40
        result = Image.new('RGB', (width, height), 'white')
        draw = ImageDraw.Draw(result)
        # 1. Название товара или штрихкод
        draw.text((width//2 - draw.textlength(product_name, font=font)//2, 10), product_name, font=font, fill='black')
        # 2. Сам QR по центру
        result.paste(qr_img_pil, (width//2 - qr_size//2, 40))
        # 3. Штрих снизу по центру
        result.paste(barcode_img, (width//2 - barcode_width//2, 40 + qr_size + 20))
        safe_title = safe_filename(title)
        out_path = f"result_{idx}_{safe_title}.jpg"
        result.save(out_path)
        images.append(out_path)
    return images 