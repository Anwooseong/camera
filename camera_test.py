import tkinter as tk
from tkinter import messagebox
from picamera2 import Picamera2
from PIL import Image, ImageTk
import cv2 # picamera2 이미지를 PIL 이미지로 변환하기 위해 사용 (선택 사항)
import numpy as np # OpenCV와 함께 사용
import pytesseract # OCR 라이브러리
import time
import os

# Tesseract 실행 파일 경로 설정 (윈도우나 특정 환경에서 필요할 수 있습니다. 라즈베리파이에선 보통 필요 없음)
# pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract' # 라즈베리파이 기본 경로

class CameraApp:
    def __init__(self, master):
        self.master = master
        self.master.title("PiCamera2 GUI")

        self.picam2 = Picamera2()
        
        # 미리보기 설정 (풀 해상도 사용 시 메모리 문제가 있을 수 있으니 적절히 조절)
        # Tkinter 창 크기에 맞게 미리보기 해상도를 설정하는 것이 좋습니다.
        # 예시: (640, 480) 또는 (1280, 720)
        preview_width = 1280
        preview_height = 720
        # NOTE: 'main' stream은 기본 카메라 출력 해상도를 따르며, 'lores' stream은 작은 미리보기 등에 사용됩니다.
        # GUI에 표시할 때는 'lores' 스트림을 사용하고, 캡처할 때는 'main' 스트림을 사용하는 것이 효율적입니다.
        preview_config = self.picam2.create_preview_configuration(main={"size": (preview_width, preview_height)})
        self.picam2.configure(preview_config)

        self.picam2.start()
        
        # 이미지 저장을 위한 디렉토리 설정
        self.save_dir = "/home/pi/Desktop/images"
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
            print(f"이미지 저장 디렉토리 생성: {self.save_dir}")

        self.cap_idx = 0 # 캡처된 이미지 인덱스

        # Tkinter UI 설정
        self.label = tk.Label(master)
        self.label.pack()

        # 키 바인딩
        # <space>: 캡쳐
        # <Control-z>, <Control-c>: GUI 종료
        master.bind('<space>', self.capture_image)
        master.bind('<Control-z>', self.on_closing)
        master.bind('<Control-c>', self.on_closing)
        master.protocol("WM_DELETE_WINDOW", self.on_closing) # 창 닫기 버튼 (X)

        self.update_frame() # 주기적으로 카메라 프레임을 업데이트

    def update_frame(self):
        # 최신 카메라 프레임 가져오기 (NumPy 배열 형식)
        # 'main' 또는 'lores' 스트림 중 원하는 것을 선택하여 가져올 수 있습니다.
        # GUI 표시용이므로 가벼운 'lores'가 좋습니다.
        frame = self.picam2.capture_array() 
        
        # BGR (OpenCV 기본) -> RGB (PIL/Tkinter) 변환
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # NumPy 배열을 PIL Image 객체로 변환
        img = Image.fromarray(frame_rgb)
        
        # Tkinter PhotoImage 객체로 변환
        imgtk = ImageTk.PhotoImage(image=img)
        
        self.label.imgtk = imgtk
        self.label.configure(image=imgtk)
        
        # 다음 프레임 업데이트 스케줄링 (20ms마다)
        self.master.after(20, self.update_frame)

    def capture_image(self, event=None):
        messagebox.showinfo("캡쳐", "이미지를 캡쳐합니다!")
        
        # 캡쳐될 이미지의 전체 경로 생성
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        img_filename = f"capture_{timestamp}_{self.cap_idx}.jpg"
        img_path = os.path.join(self.save_dir, img_filename)
        
        # 이미지 캡쳐 (main 스트림 사용)
        request = self.picam2.capture_request()
        request.save("main", img_path)
        request.release()
        
        print(f"이미지 저장 완료: {img_path}")
        self.cap_idx += 1

        # OCR 처리
        self.process_ocr(img_path)

    def process_ocr(self, image_path):
        try:
            # 이미지 로드
            img_for_ocr = Image.open(image_path)
            
            # OCR 실행
            # lang='eng'는 영어를, lang='kor'는 한글을 인식합니다. 둘 다 사용하려면 'eng+kor'
            text = pytesseract.image_to_string(img_for_ocr, lang='kor+eng')
            
            # 텍스트 파일 저장 경로 설정
            txt_filename = os.path.splitext(os.path.basename(image_path))[0] + ".txt"
            txt_path = os.path.join(self.save_dir, txt_filename)
            
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(text)
            
            print(f"OCR 텍스트 저장 완료: {txt_path}")
            messagebox.showinfo("OCR 완료", f"텍스트 파일이 저장되었습니다:\n{txt_path}")

        except pytesseract.TesseractNotFoundError:
            messagebox.showerror("OCR 오류", "Tesseract OCR 엔진을 찾을 수 없습니다. 설치를 확인해주세요.")
            print("Tesseract OCR 엔진을 찾을 수 없습니다. 'sudo apt install tesseract-ocr'로 설치했는지 확인해주세요.")
        except Exception as e:
            messagebox.showerror("OCR 오류", f"OCR 처리 중 오류가 발생했습니다: {e}")
            print(f"OCR 처리 중 오류: {e}")

    def on_closing(self, event=None):
        if messagebox.askokcancel("종료", "정말로 프로그램을 종료하시겠습니까?"):
            self.picam2.stop() # 카메라 스트림 중지
            self.master.destroy() # Tkinter 창 닫기
            print("프로그램이 종료되었습니다.")

# 메인 실행 블록
if __name__ == "__main__":
    root = tk.Tk()
    app = CameraApp(root)
    root.mainloop()
