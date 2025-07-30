from picamera2 import Picamera2
import time
import os

# Picamera2 객체 초기화
picam2 = Picamera2()

# 미리보기 설정을 구성합니다.
# 카메라를 초기화하는 동안 시간이 필요하므로 필요합니다.
# 별도의 창에 미리보기가 뜨는 것은 이 코드에는 포함되어 있지 않습니다.
preview_config = picam2.create_preview_configuration()
picam2.configure(preview_config)

# 카메라 시작
picam2.start()

# 카메라가 안정화될 시간을 잠시 기다립니다 (필요에 따라 조절)
time.sleep(2)

# 저장할 파일 경로 설정
# 현재 시간을 이용해 파일명을 동적으로 생성하여 겹치지 않도록 합니다.
current_time = time.strftime("%Y%m%d_%H%M%S")
save_path = f"/home/user/Desktop/images/image_{current_time}.jpg"

# 폴더가 존재하지 않으면 생성
# 이전에 `mkdir` 명령어로 직접 만드셨다면 이 부분은 불필요하지만,
# 코드 내에서 한 번 더 확인하는 것은 좋은 습관입니다.
output_directory = os.path.dirname(save_path)
if not os.path.exists(output_directory):
    os.makedirs(output_directory)
    print(f"디렉토리 생성: {output_directory}")

try:
    # 이미지 캡쳐 및 저장
    picam2.capture_file(save_path)
    print(f"사진이 성공적으로 저장되었습니다: {save_path}")

except Exception as e:
    print(f"사진 저장 중 오류가 발생했습니다: {e}")

finally:
    # 카메라 정지
    picam2.stop()
    print("카메라가 정지되었습니다.")