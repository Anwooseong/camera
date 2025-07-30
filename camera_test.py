import tkinter as tk
from tkinter import messagebox
from picamera2 import Picamera2
from PIL import Image, ImageTk
import cv2
import numpy as np
import requests # API 호출을 위한 requests 라이브러리 추가
import base64   # 이미지 base64 인코딩을 위한 base64 모듈 추가
import json     # JSON 데이터 처리를 위한 json 모듈 추가
import time
import os

# --- 네이버 Clova OCR API 설정 ---
# 발급받으신 Client ID와 Client Secret을 여기에 입력해 주세요!
# **절대 GitHub 등 외부에 노출되지 않도록 주의해 주세요!**
CLOVA_OCR_API_URL = "YOUR_CLOVA_OCR_API_URL_HERE" # 예: https://ocr.apigw.ntruss.com/ocr/v2/image
CLOVA_OCR_CLIENT_ID = "YOUR_CLIENT_ID_HERE"
CLOVA_OCR_CLIENT_SECRET = "YOUR_CLIENT_SECRET_HERE"

# OCR 결과가 누적 저장될 하나의 텍스트 파일 경로
OCR_OUTPUT_TEXT_FILE = os.path.join(os.path.expanduser("~/Desktop/images"), "all_ocr_results.txt")


class CameraApp:
    def __init__(self, master):
        self.master = master
        self.master.title("PiCamera2 GUI & Clova OCR")

        # Clova OCR API 설정 정보가 입력되었는지 확인
        if CLOVA_OCR_API_URL == "YOUR_CLOVA_OCR_API_URL_HERE" or \
           CLOVA_OCR_CLIENT_ID == "YOUR_CLIENT_ID_HERE" or \
           CLOVA_OCR_CLIENT_SECRET == "YOUR_CLIENT_SECRET_HERE":
            messagebox.showerror("설정 오류", "Clova OCR API URL, Client ID, Client Secret을 코드에 입력해 주세요!")
            self.master.destroy()
            return

        self.picam2 = Picamera2()
        
        # 미리보기 설정: GUI에 표시될 해상도를 정합니다.
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
        
        # 이미지 저장 디렉토리 설정 (기존과 동일)
        self.save_dir = os.path.join(os.path.expanduser("~"), "Desktop/images")
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
            print(f"이미지 저장 디렉토리 생성: {self.save_dir}")

        self.cap_idx = 0 # 캡처된 이미지 순서 번호

        # Tkinter UI 설정
        self.label = tk.Label(master)
        self.label.pack(padx=10, pady=10) # 패딩 추가

        # 키 바인딩
        master.bind('<space>', self.capture_image)
        master.bind('<Control-z>', self.on_closing)
        master.bind('<Control-c>', self.on_closing)
        master.protocol("WM_DELETE_WINDOW", self.on_closing) # 창 닫기 버튼 (X) 처리

        self.update_frame() # 카메라 프레임을 주기적으로 업데이트 시작

    def update_frame(self):
        # 최신 카메라 프레임 가져오기 (NumPy 배열 형식)
        frame = self.picam2.capture_array()
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # NumPy 배열을 PIL Image 객체로 변환
        img = Image.fromarray(frame_rgb)
        
        # Tkinter PhotoImage 객체로 변환
        imgtk = ImageTk.PhotoImage(image=img)
        
        self.label.imgtk = imgtk 
        self.label.configure(image=imgtk)
        
        # 다음 프레임 업데이트 스케줄링 (약 30fps = 33ms마다)
        self.master.after(33, self.update_frame)

    def capture_image(self, event=None):
        messagebox.showinfo("캡쳐 및 OCR", "이미지를 캡쳐하여 Clova OCR로 분석합니다. 잠시 기다려주세요!")
        
        # 캡쳐될 이미지의 전체 경로 생성
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        img_filename = f"capture_{timestamp}_{self.cap_idx:03d}.jpg" 
        img_path = os.path.join(self.save_dir, img_filename)
        
        try:
            # 이미지 캡쳐 및 저장
            self.picam2.capture_file(img_path) 
            print(f"이미지 저장 완료: {img_path}")
            self.cap_idx += 1 

            # Clova OCR 처리
            self.process_clova_ocr(img_path)

        except Exception as e:
            messagebox.showerror("캡쳐/저장 오류", f"이미지 캡쳐 또는 저장 중 오류가 발생했습니다: {e}")
            print(f"이미지 캡쳐/저장 중 오류: {e}")

    def process_clova_ocr(self, image_path):
        try:
            # 1. 이미지 파일을 바이너리 형태로 읽어서 Base64로 인코딩
            with open(image_path, 'rb') as f:
                image_bytes = f.read()
            encoded_image = base64.b64encode(image_bytes).decode('utf-8')

            # 2. Clova OCR API 요청 페이로드 구성
            headers = {
                'Content-Type': 'application/json',
                'X-OCR-SECRET': CLOVA_OCR_CLIENT_SECRET
            }
            body = {
                'version': 'V2',
                'requestId': f'clova_{int(time.time() * 1000)}',
                'timestamp': int(time.time() * 1000),
                'lang': 'ko', # 한국어 인식을 기본으로 설정합니다. ('en' for English)
                'images': [
                    {
                        'format': 'jpg',
                        'name': os.path.basename(image_path),
                        'data': encoded_image
                    }
                ]
            }

            # 3. API 호출
            print(f"Clova OCR API 호출 중: {os.path.basename(image_path)}")
            response = requests.post(CLOVA_OCR_API_URL, headers=headers, data=json.dumps(body))
            response.raise_for_status() # HTTP 오류가 발생하면 예외 발생

            result = response.json()
            
            # 4. OCR 결과 파싱 및 텍스트 추출
            extracted_text = ""
            for image_info in result.get('images', []):
                for field in image_info.get('fields', []):
                    # 모든 필드의 텍스트를 줄바꿈하여 추출합니다.
                    extracted_text += field.get('inferText', '') + '\n'

            if not extracted_text.strip():
                extracted_text = "[OCR 인식 결과 없음]"
            
            # 5. 하나의 텍스트 파일에 결과 누적 저장
            with open(OCR_OUTPUT_TEXT_FILE, 'a', encoding='utf-8') as f: # 'a'는 append 모드
                f.write(f"\n--- {os.path.basename(image_path)} ({time.ctime()}) ---\n")
                f.write(extracted_text.strip())
                f.write("\n----------------------------------------\n")
            
            print(f"Clova OCR 텍스트 결과가 '{OCR_OUTPUT_TEXT_FILE}'에 저장 완료되었습니다.")
            messagebox.showinfo("Clova OCR 완료", f"텍스트 결과가 '{OCR_OUTPUT_TEXT_FILE}'에 저장되었습니다.")

        except requests.exceptions.RequestException as e:
            messagebox.showerror("Clova OCR API 통신 오류", f"API 통신 중 오류가 발생했습니다: {e}")
            print(f"Clova OCR API 통신 중 오류: {e}")
        except json.JSONDecodeError as e:
            messagebox.showerror("Clova OCR API 응답 오류", f"API 응답 형식이 올바르지 않습니다: {e}\n응답 내용: {response.text[:200]}...")
            print(f"Clova OCR API 응답 파싱 오류: {e}\n응답 내용: {response.text}")
        except Exception as e:
            messagebox.showerror("Clova OCR 처리 오류", f"Clova OCR 처리 중 예기치 않은 오류 발생: {e}")
            print(f"Clova OCR 처리 중 예외: {e}")

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
