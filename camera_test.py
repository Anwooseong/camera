import tkinter as tk
from tkinter import messagebox
from picamera2 import Picamera2
from PIL import Image, ImageTk # ImageTk는 Tkinter와 Pillow 연동에 필수입니다.
import cv2 # OpenCV는 이미지 처리(색상 공간 변환 등)에 편리하게 사용됩니다.
import numpy as np # OpenCV와 Pillow가 내부적으로 사용하며, camera2의 출력도 numpy 배열입니다.
import time
import os
import boto3 # NCP Object Storage 연동을 위한 boto3 라이브러리

# --- NCP Object Storage 설정 정보 (반드시 본인의 정보로 변경하세요!) ---
# NCP '마이페이지' > '계정 관리' > '인증키 관리'에서 확인 가능합니다.
NCP_ACCESS_KEY = "YOUR_NCP_ACCESS_KEY"  
NCP_SECRET_KEY = "YOUR_NCP_SECRET_KEY" 
NCP_ENDPOINT_URL = "https://kr.object.ncloudstorage.com" # NCP Object Storage Endpoint URL
NCP_REGION_NAME = "kr-central-2" # Object Storage는 일반적으로 kr-central-2 리전을 사용합니다.
NCP_BUCKET_NAME = "your-unique-bucket-name" # NCP Object Storage에 미리 생성해두어야 하는 버킷 이름
# -----------------------------------------------------------------

class CameraApp:
    def __init__(self, master):
        self.master = master
        self.master.title("PiCamera2 GUI & NCP Object Storage Upload")

        self.picam2 = Picamera2()
        
        # 미리보기 설정: GUI에 표시될 해상도를 정합니다.
        preview_width = 800
        preview_height = 600
        preview_config = self.picam2.create_preview_configuration(main={"size": (preview_width, preview_height)})
        self.picam2.configure(preview_config)

        self.picam2.start()
        
        # 이미지 임시 저장 디렉토리 설정
        # 캡처 후 Object Storage에 업로드하기 전에 잠시 저장됩니다.
        self.save_dir = "/home/user/Desktop/temp_images"
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
            print(f"이미지 임시 저장 디렉토리 생성: {self.save_dir}")

        self.cap_idx = 0 # 캡처된 이미지 순서 번호

        # Tkinter UI 설정
        self.label = tk.Label(master)
        self.label.pack(padx=10, pady=10) # 패딩 추가

        # 키 바인딩
        master.bind('<space>', self.capture_image) # <space> 키로 이미지 캡처 및 업로드
        master.bind('<Control-z>', self.on_closing) # Ctrl+Z로 GUI 종료
        master.bind('<Control-c>', self.on_closing) # Ctrl+C로 GUI 종료
        master.protocol("WM_DELETE_WINDOW", self.on_closing) # 창 닫기 버튼 (X) 처리

        self.update_frame() # 카메라 프레임을 주기적으로 업데이트 시작

        # --- NCP Object Storage 클라이언트 초기화 ---
        try:
            self.s3_client = boto3.client(
                's3',
                endpoint_url=NCP_ENDPOINT_URL,
                aws_access_key_id=NCP_ACCESS_KEY,
                aws_secret_access_key=NCP_SECRET_KEY,
                region_name=NCP_REGION_NAME
            )
            # 버킷이 존재하는지 확인 (선택 사항이지만 초기 오류 확인에 유용)
            self.s3_client.head_bucket(Bucket=NCP_BUCKET_NAME)
            print(f"NCP Object Storage '{NCP_BUCKET_NAME}' 버킷에 성공적으로 연결되었습니다.")
        except Exception as e:
            # 연결 실패 시 사용자에게 알리고, 클라이언트를 None으로 설정하여 이후 작업 방지
            messagebox.showerror(
                "NCP 연결 오류", 
                f"NCP Object Storage 연결에 실패했습니다: {e}\n"
                "액세스 키, 시크릿 키, 엔드포인트 또는 버킷 이름을 확인해주세요."
            )
            print(f"NCP Object Storage 연결 오류: {e}")
            self.s3_client = None 

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
        messagebox.showinfo("캡쳐", "이미지를 캡쳐하여 NCP Object Storage에 업로드합니다. 잠시 기다려주세요!")
        
        # 캡쳐될 이미지의 임시 저장 경로 및 파일명 생성
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        img_filename = f"capture_{timestamp}_{self.cap_idx:03d}.jpg" 
        img_path = os.path.join(self.save_dir, img_filename)
        
        try:
            # 이미지를 로컬에 캡쳐 및 저장
            self.picam2.capture_file(img_path) 
            print(f"이미지 임시 저장 완료: {img_path}")
            self.cap_idx += 1 # 캡처 인덱스 증가

            # --- NCP Object Storage에 이미지 업로드 및 URL 가져오기 ---
            self.upload_image_to_ncp_object_storage(img_path)

        except Exception as e:
            messagebox.showerror("캡쳐/저장 오류", f"이미지 캡쳐 또는 임시 저장 중 오류가 발생했습니다: {e}")
            print(f"이미지 캡쳐/임시 저장 중 오류: {e}")

    def upload_image_to_ncp_object_storage(self, image_path):
        # S3 클라이언트가 정상적으로 초기화되었는지 확인
        if not self.s3_client:
            messagebox.showerror("NCP 오류", "NCP Object Storage 클라이언트가 초기화되지 않았습니다. 설정을 확인해주세요.")
            return

        object_key = os.path.basename(image_path) # 버킷에 저장될 파일 이름은 로컬 파일명과 동일하게 설정
        
        try:
            # 로컬 파일을 NCP Object Storage에 업로드합니다.
            # `upload_file`은 내부적으로 multipart 업로드를 지원하여 큰 파일도 효율적으로 처리합니다.
            self.s3_client.upload_file(image_path, NCP_BUCKET_NAME, object_key)
            print(f"'{object_key}' 파일을 NCP Object Storage '{NCP_BUCKET_NAME}' 버킷에 성공적으로 업로드했습니다.")

            # 업로드된 객체의 URL 생성
            # NCP Object Storage의 공개 접근 URL 형식은 일반적으로 다음과 같습니다:
            # https://{Endpoint URL}/{Bucket Name}/{Object Key}
            uploaded_file_url = f"{NCP_ENDPOINT_URL}/{NCP_BUCKET_NAME}/{object_key}"
            
            messagebox.showinfo("업로드 완료", f"이미지가 NCP Object Storage에 업로드되었습니다:\nURL: {uploaded_file_url}")
            print(f"업로드된 이미지 URL: {uploaded_file_url}")

            # 로컬에 임시 저장된 파일 삭제 (업로드 성공 시)
            try:
                os.remove(image_path)
                print(f"로컬 임시 파일 삭제 완료: {image_path}")
            except OSError as e:
                print(f"로컬 임시 파일 삭제 중 오류 발생: {e}")

            # --- 다음 단계: 이 URL을 이용하여 네이버 CLOVA OCR 등 외부 OCR API를 호출할 수 있습니다. ---
            # 예시:
            # self.call_clova_ocr_api(uploaded_file_url)

        except Exception as e:
            messagebox.showerror("NCP 업로드 오류", f"NCP Object Storage에 파일 업로드 중 오류가 발생했습니다: {e}")
            print(f"NCP Object Storage 업로드 중 오류: {e}")

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