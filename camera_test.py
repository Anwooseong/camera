import tkinter as tk
from tkinter import messagebox
from picamera2 import Picamera2
from PIL import Image, ImageTk
import cv2
import numpy as np
import pytesseract
from gtts import gTTS # 텍스트 음성 변환 (Google Text-to-Speech)
import os
import time
import glob # 파일 목록을 가져오기 위함
import subprocess # 외부 프로그램 실행을 위함

# Tesseract 실행 파일 경로 설정 (일반적으로 라즈베리파이에선 기본 경로로 자동 탐지되므로 필요 없을 수 있습니다.)
# pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract' 

class CameraApp:
    def __init__(self, master):
        self.master = master
        self.master.title("PiCamera2 GUI & OCR 통합/음성")

        self.picam2 = Picamera2()
        
        # 미리보기 해상도 설정
        preview_width = 800
        preview_height = 600
        preview_config = self.picam2.create_preview_configuration(main={"size": (preview_width, preview_height)})
        self.picam2.configure(preview_config)

        try:
            self.picam2.start()
        except Exception as e:
            messagebox.showerror("카메라 시작 오류", f"카메라를 시작할 수 없습니다. 연결 상태나 권한을 확인해주세요: {e}")
            self.master.destroy()
            return
        
        # 이미지 저장 디렉토리 설정 (OS 사용자 홈 디렉토리 기준으로 유연하게 설정)
        self.save_dir = os.path.join(os.path.expanduser("~"), "Desktop/images")
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
            print(f"이미지 저장 디렉토리 생성: {self.save_dir}")

        # 모든 OCR 결과가 저장될 통합 텍스트 파일 경로
        self.all_ocr_results_file = os.path.join(self.save_dir, "all_ocr_results.txt")
        self.cap_idx = 0 # 캡처된 이미지 순서 번호

        # Tkinter UI 설정
        self.label = tk.Label(master)
        self.label.pack(padx=10, pady=10) # 패딩 추가

        # 키 바인딩
        master.bind('<space>', self.capture_image)            # 스페이스바: 사진 캡쳐
        master.bind('<Control-p>', self.process_all_images_and_speak) # Ctrl+P: 모든 사진 OCR 통합 + 음성 재생
        master.bind('<Control-z>', self.on_closing)           # Ctrl+Z: 종료
        master.bind('<Control-c>', self.on_closing)           # Ctrl+C: 종료
        master.protocol("WM_DELETE_WINDOW", self.on_closing)  # 창 닫기 버튼 (X) 처리

        self.update_frame() # 카메라 프레임을 주기적으로 업데이트 시작

    def update_frame(self):
        # 최신 카메라 프레임 가져와서 GUI에 표시
        frame = self.picam2.capture_array()
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        imgtk = ImageTk.PhotoImage(image=img)
        
        self.label.imgtk = imgtk 
        self.label.configure(image=imgtk)
        
        self.master.after(33, self.update_frame) # 약 30fps

    def capture_image(self, event=None):
        messagebox.showinfo("캡쳐", "사진을 캡쳐합니다. Ctrl+P를 눌러 OCR 통합 및 음성 재생을 실행하세요!")
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        img_filename = f"capture_{timestamp}_{self.cap_idx:03d}.jpg" 
        img_path = os.path.join(self.save_dir, img_filename)
        
        try:
            self.picam2.capture_file(img_path) 
            print(f"이미지 저장 완료: {img_path}")
            self.cap_idx += 1 

        except Exception as e:
            messagebox.showerror("캡쳐 오류", f"이미지 캡쳐 중 오류가 발생했습니다: {e}")
            print(f"이미지 캡쳐 중 오류: {e}")

    def process_all_images_and_speak(self, event=None):
        messagebox.showinfo("OCR 통합 및 음성 재생", "모든 캡쳐 이미지를 OCR 분석하고 통합 텍스트를 읽어 드립니다. 잠시 기다려주세요!")
        
        all_captured_images = sorted(glob.glob(os.path.join(self.save_dir, "capture_*.jpg")))
        
        if not all_captured_images:
            messagebox.showwarning("이미지 없음", "OCR을 수행할 캡쳐 이미지가 없습니다.")
            return

        full_text_content = ""
        
        # 모든 캡쳐 이미지에서 OCR 수행
        for img_path in all_captured_images:
            try:
                img_for_ocr = Image.open(img_path)
                # OCR 실행: 한글과 영어를 모두 인식하도록 설정
                text = pytesseract.image_to_string(img_for_ocr, lang='kor+eng')
                
                # 각 이미지별 텍스트를 통합 내용에 추가
                full_text_content += f"\n--- {os.path.basename(img_path)} ---\n"
                full_text_content += text.strip()
                full_text_content += "\n---------------------------\n"
                print(f"OCR 분석 완료: {os.path.basename(img_path)}")

            except pytesseract.TesseractNotFoundError:
                messagebox.showerror("OCR 오류", "Tesseract OCR 엔진을 찾을 수 없습니다. 'sudo apt install tesseract-ocr' 명령으로 설치를 확인해주세요.")
                print("Tesseract OCR 엔진을 찾을 수 없습니다.")
                return # Tesseract 오류 발생 시 더 이상 진행하지 않음
            except Exception as e:
                print(f"이미지 {os.path.basename(img_path)} OCR 처리 중 오류: {e}")
                full_text_content += f"\n--- {os.path.basename(img_path)} (OCR 실패) ---\n"


        # 통합된 텍스트 파일 저장 (기존 내용 덮어쓰기)
        try:
            with open(self.all_ocr_results_file, 'w', encoding='utf-8') as f:
                f.write(full_text_content.strip())
            print(f"통합 OCR 텍스트 저장 완료: {self.all_ocr_results_file}")
            messagebox.showinfo("OCR 통합 완료", f"모든 캡쳐 이미지의 텍스트가 '{self.all_ocr_results_file}'에 저장되었습니다.")
        except Exception as e:
            messagebox.showerror("파일 저장 오류", f"통합 텍스트 파일 저장 중 오류가 발생했습니다: {e}")
            print(f"통합 텍스트 파일 저장 중 오류: {e}")
            return


        # 텍스트 음성 변환 (TTS) 및 재생
        if full_text_content.strip(): # 내용이 있을 경우에만 음성 재생
            try:
                print("음성 변환 중...")
                tts = gTTS(text=full_text_content, lang='ko') # 한국어 음성 생성
                audio_file = os.path.join(self.save_dir, "ocr_output.mp3")
                tts.save(audio_file)
                print(f"음성 파일 저장 완료: {audio_file}")
                
                # mpg123으로 음성 파일 재생
                subprocess.run(["mpg123", audio_file], check=True) # check=True: 오류 시 예외 발생
                print("음성 재생 완료.")

                # 음성 재생 후 임시 파일 삭제
                os.remove(audio_file)
                print("음성 파일 삭제 완료.")

            except Exception as e:
                messagebox.showerror("음성 재생 오류", f"텍스트를 음성으로 변환하거나 재생하는 중 오류가 발생했습니다: {e}")
                print(f"음성 변환/재생 중 오류: {e}")
        else:
            messagebox.showwarning("내용 없음", "OCR로 추출된 텍스트가 없어 음성 재생을 건너뜀.") 


    def on_closing(self, event=None):
        if messagebox.askokcancel("종료", "정말로 프로그램을 종료하시겠습니까?"):
            print("카메라 스트림을 중지합니다.")
            self.picam2.stop() 
            print("GUI 애플리케이션을 종료합니다.")
            self.master.destroy() 

# 메인 실행 블록
if __name__ == "__main__":
    root = tk.Tk()
    app = CameraApp(root)
    root.mainloop()