import cv2
from pyzbar.pyzbar import decode, ZBarSymbol
import numpy as np
from ultralytics import YOLO
import os

YOLO_WEIGHTS = 'yolov8n.pt'

class AutoQRDetector:
    def __init__(self, yolo_conf=0.2, yolo_imgsz=640, min_qr_count=3):
        self.yolo_conf = yolo_conf
        self.yolo_imgsz = yolo_imgsz
        self.min_qr_count = min_qr_count
        if not os.path.exists(YOLO_WEIGHTS):
            import urllib.request
            url = 'https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.pt'
            print('Скачиваю YOLOv8 стандартные веса...')
            urllib.request.urlretrieve(url, YOLO_WEIGHTS)
        self.model = YOLO(YOLO_WEIGHTS)

    def detect(self, image_path):
        image_orig = cv2.imread(image_path)
        h, w = image_orig.shape[:2]
        qrs = []
        seen = set()
        # 1. YOLOv8 QR detection
        results = self.model(image_path, imgsz=self.yolo_imgsz, conf=self.yolo_conf)
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)
                crop = image_orig[y1:y2, x1:x2]
                decoded = decode(crop, symbols=[ZBarSymbol.QRCODE])
                for obj in decoded:
                    data = obj.data.decode('utf-8') if obj.data else None
                    if data and data not in seen:
                        qrs.append({'data': data, 'rect': (x1, y1, x2-x1, y2-y1), 'image': crop})
                        seen.add(data)
                detector = cv2.QRCodeDetector()
                val, points = detector.detect(crop)
                if val:
                    qr_data, _, _ = detector.detectAndDecode(crop)
                    if qr_data and qr_data not in seen:
                        qrs.append({'data': qr_data, 'rect': (x1, y1, x2-x1, y2-y1), 'image': crop})
                        seen.add(qr_data)
        # Если мало QR — пробуем pyzbar по всему изображению
        if len(qrs) < self.min_qr_count:
            decoded = decode(image_orig, symbols=[ZBarSymbol.QRCODE])
            for obj in decoded:
                data = obj.data.decode('utf-8') if obj.data else None
                if data and data not in seen:
                    (x, y, w, h) = obj.rect
                    qrs.append({'data': data, 'rect': (x, y, w, h), 'image': image_orig[y:y+h, x:x+w]})
                    seen.add(data)
            # OpenCV QRCodeDetector по всему изображению
            detector = cv2.QRCodeDetector()
            val, points = detector.detect(image_orig)
            if val:
                qr_data, _, _ = detector.detectAndDecode(image_orig)
                if qr_data and qr_data not in seen:
                    if points is not None and len(points) == 4:
                        pts = points.astype(int).reshape(-1, 2)
                        x, y, w, h = pts[:,0].min(), pts[:,1].min(), pts[:,0].max()-pts[:,0].min(), pts[:,1].max()-pts[:,1].min()
                        qrs.append({'data': qr_data, 'rect': (x, y, w, h), 'image': image_orig[y:y+h, x:x+w]})
                        seen.add(qr_data)
        return qrs 