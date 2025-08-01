import tkinter as tk
from tkinter import messagebox
from picamera2 import Picamera2
from PIL import Image, ImageTk
import cv2
import numpy as np
import time
import os
import requests # requests 라이브러리 추가
import datetime # 날짜/시간 처리
import hashlib # 해시 함수
import hmac # HMAC 암호화
import base64 # Base64 인코딩

# --- NCP Object Storage 설정 정보 (반드시 본인의 정보로 변경하세요!) ---
NCP_ACCESS_KEY = "ncp_iam_BPAMKR5KytWH6Q8SQ6Fx"  
NCP_SECRET_KEY = "ncp_iam_BPKMKRIoECxfq2HTTJiXVpeKumrwmFjing" 
NCP_ENDPOINT_URL = "https://kr.object.ncloudstorage.com" # Object Storage Endpoint URL
NCP_BUCKET_NAME = "korean-jo" # NCP Object Storage에 미리 생성해두어야 하는 버킷 이름
NCP_REGION_NAME = "kr-standard" # Object Storage는 일반적으로 kr-central-2 리전을 사용합니다.
NCP_SERVICE = "s3" # S3 호환 서비스임을 명시
# -----------------------------------------------------------------

# --- AWS Signature Version 4 생성을 위한 헬퍼 함수 ---
# 이 함수들은 AWS 공식 문서나 기존 구현체를 참고하여 만들어진 표준적인 Signature V4 생성 로직입니다.
# 직접 구현 시 복잡하고 오류 가능성이 높으므로, 이해를 돕기 위한 예시로 제공됩니다.

def sign(key, msg):
    return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

def get_signature_key(key, date_stamp, region_name, service_name):
    k_date = sign(('AWS4' + key).encode('utf-8'), date_stamp)
    k_region = sign(k_date, region_name)
    k_service = sign(k_region, service_name)
    k_signing = sign(k_service, 'aws4_request')
    return k_signing

class CameraApp:
    def __init__(self, master):
        self.master = master
        self.master.title("PiCamera2 GUI & NCP Object Storage Direct Upload")

        self.picam2 = Picamera2()
        
        preview_width = 800
        preview_height = 600
        preview_config = self.picam2.create_preview_configuration(main={"size": (preview_width, preview_height)})
        self.picam2.configure(preview_config)

        self.picam2.start()
        
        self.save_dir = "/home/user/Desktop/temp_images"
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
            print(f"이미지 임시 저장 디렉토리 생성: {self.save_dir}")

        self.cap_idx = 0

        self.label = tk.Label(master)
        self.label.pack(padx=10, pady=10)

        master.bind('<space>', self.capture_image)
        master.bind('<Control-z>', self.on_closing)
        master.bind('<Control-c>', self.on_closing)
        master.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.update_frame()

    def update_frame(self):
        frame = self.picam2.capture_array()
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        imgtk = ImageTk.PhotoImage(image=img)
        
        self.label.imgtk = imgtk
        self.label.configure(image=imgtk)
        
        self.master.after(33, self.update_frame)

    def capture_image(self, event=None):
        messagebox.showinfo("캡쳐", "이미지를 캡쳐하여 NCP Object Storage에 직접 업로드합니다. 잠시 기다려주세요!")
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        img_filename = f"capture_{timestamp}_{self.cap_idx:03d}.jpg" 
        img_path = os.path.join(self.save_dir, img_filename)
        
        try:
            self.picam2.capture_file(img_path) 
            print(f"이미지 임시 저장 완료: {img_path}")
            self.cap_idx += 1 

            self.upload_image_to_ncp_object_storage_direct(img_path)

        except Exception as e:
            messagebox.showerror("캡쳐/저장 오류", f"이미지 캡쳐 또는 임시 저장 중 오류가 발생했습니다: {e}")
            print(f"이미지 캡쳐/임시 저장 중 오류: {e}")

    def upload_image_to_ncp_object_storage_direct(self, image_path):
        method = 'PUT'
        object_key = os.path.basename(image_path) # 버킷에 저장될 파일 이름
        host = NCP_BUCKET_NAME + '.' + NCP_ENDPOINT_URL.split('://')[1] # 호스트는 '버킷이름.엔드포인트주소' 형식
        request_url = f"{NCP_ENDPOINT_URL}/{NCP_BUCKET_NAME}/{object_key}"

        t = datetime.datetime.utcnow()
        amz_date = t.strftime('%Y%m%dT%H%M%SZ')
        date_stamp = t.strftime('%Y%m%d') # Date w/o time, used in credential scope

        # Step 1: Create a canonical request
        canonical_uri = f"/{NCP_BUCKET_NAME}/{object_key}" # Object Storage API는 버킷과 객체 키를 함께 URI로 사용
        canonical_querystring = ''
        canonical_headers = 'host:' + host + '\nx-amz-date:' + amz_date + '\n'
        signed_headers = 'host;x-amz-date'

        # 파일을 열어서 sha256 해시값 계산
        with open(image_path, 'rb') as f:
            file_content = f.read()
            payload_hash = hashlib.sha256(file_content).hexdigest()
        
        canonical_request = method + '\n' + canonical_uri + '\n' + canonical_querystring + '\n' + canonical_headers + '\n' + signed_headers + '\n' + payload_hash

        # Step 2: Create the string to sign
        algorithm = 'AWS4-HMAC-SHA256'
        credential_scope = date_stamp + '/' + NCP_REGION_NAME + '/' + NCP_SERVICE + '/' + 'aws4_request'
        string_to_sign = algorithm + '\n' + amz_date + '\n' + credential_scope + '\n' + hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()

        # Step 3: Calculate the signature
        signing_key = get_signature_key(NCP_SECRET_KEY, date_stamp, NCP_REGION_NAME, NCP_SERVICE)
        signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

        # Step 4: Add signing information to the request
        authorization_header = algorithm + ' ' + 'Credential=' + NCP_ACCESS_KEY + '/' + credential_scope + ', ' + 'SignedHeaders=' + signed_headers + ', ' + 'Signature=' + signature

        headers = {
            'x-amz-date': amz_date,
            'Authorization': authorization_header,
            'Content-Type': 'image/jpeg' # 업로드할 이미지 타입에 따라 변경 (예: image/png)
        }

        try:
            # PUT 요청 전송
            response = requests.put(request_url, data=file_content, headers=headers)
            
            if response.status_code == 200:
                uploaded_file_url = f"{NCP_ENDPOINT_URL}/{NCP_BUCKET_NAME}/{object_key}"
                messagebox.showinfo("업로드 완료", f"이미지가 NCP Object Storage에 직접 업로드되었습니다:\nURL: {uploaded_file_url}")
                print(f"업로드된 이미지 URL: {uploaded_file_url}")

                # 로컬에 임시 저장된 파일 삭제
                try:
                    os.remove(image_path)
                    print(f"로컬 임시 파일 삭제 완료: {image_path}")
                except OSError as e:
                    print(f"로컬 임시 파일 삭제 중 오류 발생: {e}")
            else:
                messagebox.showerror("업로드 실패", f"NCP Object Storage 직접 업로드 실패: Status Code {response.status_code}\n"
                                                      f"Response: {response.text}")
                print(f"NCP Object Storage 직접 업로드 실패: Status Code {response.status_code}")
                print(f"Response: {response.text}")

        except requests.exceptions.RequestException as e:
            messagebox.showerror("네트워크 오류", f"NCP Object Storage 직접 업로드 중 네트워크 오류 발생: {e}")
            print(f"NCP Object Storage 직접 업로드 중 네트워크 오류 발생: {e}")
        except Exception as e:
            messagebox.showerror("업로드 오류", f"예상치 못한 업로드 오류 발생: {e}")
            print(f"예상치 못한 업로드 오류 발생: {e}")

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
