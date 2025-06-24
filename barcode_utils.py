import barcode
from barcode.writer import ImageWriter
from io import BytesIO
from PIL import Image
import re
import requests

def extract_barcode_value(data):
    match = re.search(r"CEN;([^;]+);", data)
    if match:
        return match.group(1)
    return data

def lookup_product_name(barcode_value):
    # Используем бесплатное API UPC-Search.org
    try:
        url = f"https://api.upcitemdb.com/prod/trial/lookup?upc={barcode_value}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('items') and len(data['items']) > 0:
                title = data['items'][0].get('title')
                if title:
                    return title
    except Exception:
        pass
    return barcode_value

def generate_barcode(data):
    value = extract_barcode_value(data)
    CODE128 = barcode.get_barcode_class('code128')
    fp = BytesIO()
    CODE128(value, writer=ImageWriter()).write(fp)
    fp.seek(0)
    return Image.open(fp) 