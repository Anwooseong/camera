import tkinter as tk
from tkinter import messagebox
from picamera2 import Picamera2
from PIL import Image, ImageTk # ImageTk는 Tkinter와 Pillow 연동에 필수입니다.
import cv2 # OpenCV는 이미지 처리(색상 공간 변환 등)에 편리하게 사용됩니다.
import numpy as np # OpenCV와 Pillow가 내부적으로 사용하며, camera2의 출력도 numpy 배열입니다.
import pytesseract # OCR 라이브러리
import time
import os

# Tesseract 실행 파일 경로 설정 (일반적으로 라즈베리파이에선 기본 경로로 자동 탐지되므로 필요 없을 수 있습니다.)
# 만약 TesseractNotFoundError가 계속 발생한다면, 아래 주석을 풀고 tesseract 설치 경로를 확인하여 설정해 보세요.
# pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract' 

class CameraApp:
    def __init__(self, master):
        self.master = master
        self.master.title("PiCamera2 GUI & OCR")

        self.picam2 = Picamera2()
        
        # 미리보기 설정: GUI에 표시될 해상도를 정합니다.
        # Too large resolution can slow down the GUI or consume too much memory.
        preview_width = 800
        preview_height = 600
        preview_config = self.picam2.create_preview_configuration(main={"size": (preview_width, preview_height)})
        self.picam2.configure(preview_config)

        self.picam2.start()
        
        # 이미지 저장 디렉토리 설정
        self.save_dir = "/home/user/Desktop/images"
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
            print(f"이미지 저장 디렉토리 생성: {self.save_dir}")

        self.cap_idx = 0 # 캡처된 이미지 순서 번호

        # Tkinter UI 설정
        self.label = tk.Label(master)
        self.label.pack(padx=10, pady=10) # 패딩 추가

        # 키 바인딩
        # <space>: 캡쳐
        # <Control-z>, <Control-c>: GUI 종료
        master.bind('<space>', self.capture_image)
        master.bind('<Control-z>', self.on_closing)
        master.bind('<Control-c>', self.on_closing)
        master.protocol("WM_DELETE_WINDOW", self.on_closing) # 창 닫기 버튼 (X) 처리

        self.update_frame() # 카메라 프레임을 주기적으로 업데이트 시작

    def update_frame(self):
        # 최신 카메라 프레임 가져오기 (NumPy 배열 형식)
        # BGR (OpenCV 기본) -> RGB (PIL/Tkinter) 변환
        frame = self.picam2.capture_array()
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # NumPy 배열을 PIL Image 객체로 변환
        img = Image.fromarray(frame_rgb)
        
        # Tkinter PhotoImage 객체로 변환
        imgtk = ImageTk.PhotoImage(image=img)
        
        self.label.imgtk = imgtk # Tkinter가 이미지 가비지 컬렉션 되는 것을 방지
        self.label.configure(image=imgtk)
        
        # 다음 프레임 업데이트 스케줄링 (약 30fps = 33ms마다)
        self.master.after(33, self.update_frame)

    def capture_image(self, event=None):
        messagebox.showinfo("캡쳐", "이미지를 캡쳐하고 OCR을 진행합니다. 잠시 기다려주세요!")
        
        # 캡쳐될 이미지의 전체 경로 생성
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        # 이미지 파일명에 순서 인덱스를 추가하여 중복 방지
        img_filename = f"capture_{timestamp}_{self.cap_idx:03d}.jpg" 
        img_path = os.path.join(self.save_dir, img_filename)
        
        try:
            # 이미지 캡쳐 (main 스트림 사용)
            # capture_file()은 내부적으로 request를 사용하며 파일로 바로 저장합니다.
            self.picam2.capture_file(img_path) 
            print(f"이미지 저장 완료: {img_path}")
            self.cap_idx += 1 # 캡처 인덱스 증가

            # OCR 처리
            self.process_ocr(img_path)

        except Exception as e:
            messagebox.showerror("캡쳐/저장 오류", f"이미지 캡쳐 또는 저장 중 오류가 발생했습니다: {e}")
            print(f"이미지 캡쳐/저장 중 오류: {e}")

    def process_ocr(self, image_path):
        try:
            # 이미지 로드 (Pillow 객체)
            img_for_ocr = Image.open(image_path)
            
            # OCR 실행: 한글과 영어를 모두 인식하도록 설정
            # pytesseract는 Pillow Image 객체를 입력으로 받습니다.
            text = pytesseract.image_to_string(img_for_ocr, lang='kor+eng')
            
            # 텍스트 파일 저장 경로 설정
            # 이미지 파일명과 동일한 이름의 .txt 파일로 저장
            txt_filename = os.path.splitext(os.path.basename(image_path))[0] + ".txt"
            txt_path = os.path.join(self.save_dir, txt_filename)
            
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(text)
            
            print(f"OCR 텍스트 저장 완료: {txt_path}")
            messagebox.showinfo("OCR 완료", f"텍스트 파일이 저장되었습니다:\n{txt_path}")

        except pytesseract.TesseractNotFoundError:
            messagebox.showerror("OCR 오류", "Tesseract OCR 엔진을 찾을 수 없습니다. 'sudo apt install tesseract-ocr' 명령으로 설치를 확인해주세요.")
            print("Tesseract OCR 엔진을 찾을 수 없습니다. 'sudo apt install tesseract-ocr'로 설치했는지 확인해주세요.")
        except Exception as e:
            messagebox.showerror("OCR 오류", f"OCR 처리 중 오류가 발생했습니다: {e}")
            print(f"OCR 처리 중 오류: {e}")

    def on_closing(self, event=None):
        if messagebox.askokcancel("종료", "정말로 프로그램을 종료하시겠습니까?"):
            print("카메라 스트림을 중지합니다.")
            self.picam2.stop() # 카메라 스트림 중지 및 리소스 해제
            print("GUI 애플리케이션을 종료합니다.")
            self.master.destroy() # Tkinter 창 닫기

# 메인 실행 블록
if __name__ == "__main__":
    root = tk.Tk()
    app = CameraApp(root)
    root.mainloop()