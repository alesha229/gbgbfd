import cv2
from pyzbar.pyzbar import decode, ZBarSymbol
import numpy as np
import os
from ultralytics import YOLO

YOLO_WEIGHTS = 'yolov8n.pt'

# Автоматическая загрузка весов, если их нет
import urllib.request
if not os.path.exists(YOLO_WEIGHTS):
    url = 'https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.pt'
    print('Скачиваю YOLOv8 стандартные веса...')
    urllib.request.urlretrieve(url, YOLO_WEIGHTS)

def four_point_transform(image, pts):
    # Получаем прямоугольник из 4 точек
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    (tl, tr, br, bl) = rect
    widthA = np.linalg.norm(br - bl)
    widthB = np.linalg.norm(tr - tl)
    maxWidth = max(int(widthA), int(widthB))
    heightA = np.linalg.norm(tr - br)
    heightB = np.linalg.norm(tl - bl)
    maxHeight = max(int(heightA), int(heightB))
    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]], dtype="float32")
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
    return warped

def preprocess_variants(image):
    variants = [image]
    # 1. Увеличение x2
    variants.append(cv2.resize(image, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC))
    # 2. Грейскейл + adaptive threshold
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    th1 = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY, 31, 10)
    variants.append(cv2.cvtColor(th1, cv2.COLOR_GRAY2BGR))
    # 3. Грейскейл + Otsu
    _, th2 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append(cv2.cvtColor(th2, cv2.COLOR_GRAY2BGR))
    # 4. CLAHE (контраст)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    cl = clahe.apply(gray)
    variants.append(cv2.cvtColor(cl, cv2.COLOR_GRAY2BGR))
    # 5. Морфология (расширение)
    kernel = np.ones((3,3), np.uint8)
    dil = cv2.dilate(gray, kernel, iterations=1)
    variants.append(cv2.cvtColor(dil, cv2.COLOR_GRAY2BGR))
    # 6. Морфология (сужение)
    ero = cv2.erode(gray, kernel, iterations=1)
    variants.append(cv2.cvtColor(ero, cv2.COLOR_GRAY2BGR))
    return variants

def extract_qrs_from_image(image_path):
    image_orig = cv2.imread(image_path)
    qrs = []
    seen = set()
    variants = preprocess_variants(image_orig)
    for img in variants:
        # pyzbar по варианту
        decoded = decode(img, symbols=[ZBarSymbol.QRCODE])
        for obj in decoded:
            data = obj.data.decode('utf-8') if obj.data else None
            if data and data not in seen:
                (x, y, w, h) = obj.rect
                qrs.append({'data': data, 'rect': (x, y, w, h), 'image': img[y:y+h, x:x+w]})
                seen.add(data)
        # OpenCV QRCodeDetector по варианту
        detector = cv2.QRCodeDetector()
        val, points = detector.detect(img)
        if val:
            qr_data, _, _ = detector.detectAndDecode(img)
            if qr_data and qr_data not in seen:
                if points is not None and len(points) == 4:
                    pts = points.astype(int).reshape(-1, 2)
                    x, y, w, h = pts[:,0].min(), pts[:,1].min(), pts[:,0].max()-pts[:,0].min(), pts[:,1].max()-pts[:,1].min()
                    qrs.append({'data': qr_data, 'rect': (x, y, w, h), 'image': img[y:y+h, x:x+w]})
                    seen.add(qr_data)
    # Возвращаем только уникальные QR по data
    unique = {}
    for qr in qrs:
        if qr['data'] not in unique:
            unique[qr['data']] = qr
    return list(unique.values()) 