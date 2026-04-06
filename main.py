import os
import sys
import cv2
from pyzbar.pyzbar import decode
import optparse
import concurrent.futures
import shutil
from send2trash import send2trash
import numpy as np
from paddleocr import PaddleOCR
import re

ocr_model = PaddleOCR(use_angle_cls=True, lang="vi")

class Configuration:
    def __init__(self):
        self._verbose: bool = False
        self._permanent_delete: bool = False
        self._recursive: bool = False
        self._trash_dir: str = ""
    
    @property
    def verbose(self) -> bool:
        return self._verbose
    @verbose.setter
    def verbose(self, val: bool):
        self._verbose = val
    
    @property
    def permanent_delete(self) -> bool:
        return self._permanent_delete
    @permanent_delete.setter
    def permanent_delete(self, val: bool):
        self._permanent_delete = val

    @property
    def recursive(self) -> bool:
        return self._recursive
    @recursive.setter
    def recursive(self, val: bool):
        self._recursive = val

    @property
    def trash_dir(self) -> str:
        return self._trash_dir
    @trash_dir.setter
    def trash_dir(self, val: str):
        self._trash_dir = val


def is_money_transfer(text):
    # 1. Danh sách các mẫu nhận diện quan trọng
    patterns = {
        "status": r"(thành\s?công|xong|hoàn\s?thành|thành\s?cong)",
        "bank_keywords": r"(techcombank|tpbank|vpbank|abbank|mbbank|vcb|vietcombank|napas|tcb)",
        "amount": r"(\d{1,3}([,.]\d{3})*)\s?(VND|đ|d|VNĐ)",
        "transaction_id": r"(mã\s?giao\s?dịch|mã\s?tra\s?soát|mã\s?tham\s?chiếu|FT\d{10,})",
        "action": r"(chuyển\s?khoản|chuyển\s?tiền|giao\s?dịch|nội\s?dung|người\s?nhận)"
    }
    score = 0
    found_elements = []
    for key, pattern in patterns.items():
        if re.search(pattern, text, re.IGNORECASE):
            score += 1
            found_elements.append(key)
    # Nếu khớp từ 3 nhóm dấu hiệu trở lên thì tỷ lệ là bill chuyển tiền rất cao
    is_transfer = score >= 3
    return is_transfer, found_elements


def remove_qr_images(dir: str, config: Configuration = Configuration()):
    if config.verbose:
        print(f"Searching for photo in {dir}...")
    if not os.path.exists(dir):
        return
    IMAGE_EXTENSIONS: list = ['.png', '.jpg', '.jpeg', '.tif', '.gif', '.bmp', '.heic']
    trash_dir: str = config.trash_dir
    detected: bool = False
    extracted_texts: list = []
    for dir_path, dir_names, file_names in os.walk(dir):
        for file_name in file_names:
            _, file_ext = os.path.splitext(file_name)
            file_ext = file_ext.lower()
            if file_ext.lower() not in IMAGE_EXTENSIONS:
                continue
            file_fullname = os.path.join(dir_path, file_name)
            if config.verbose:
                print(f"Detecting {file_fullname}...")
            bank_keywords = ["000201", "STCB", "VCB", "ICB", "BIDV", "NAPAS", "PAYMENT", "QRIBFTTA"]
            try:
                img = cv2.imdecode(np.fromfile(file_fullname, np.uint8), cv2.IMREAD_UNCHANGED)
                if img is None:
                    continue
                detected = False
                extracted_texts = []
                # Detect QR code
                codes = decode(img)
                if codes:
                    for qr in codes:
                        content = qr.data.decode("utf-8").upper()
                        if config.verbose:
                            print(f"QR content:{content}")
                        extracted_texts.append(content)
                        if any(key in content for key in bank_keywords):
                            detected = True
                            break
                if not detected:
                    #Detect cash transaction
                    result = ocr_model.ocr(file_fullname)
                    if result:
                        result = result[0]
                        if "rec_texts" in result:
                            rec_texts = result["rec_texts"]
                            for line in rec_texts:
                                line = line.strip()
                                if len(line) > 0:
                                    extracted_texts.append(line)
                            if len(extracted_texts) > 0:
                                detected, detections = is_money_transfer(" ".join(extracted_texts))
                                if config.verbose:
                                    print(f"detected:{detected}, detections:{detections}")
                
                if detected:
                    if config.verbose:
                        print(f"QR code detected.")
                    if config.permanent_delete:
                        if config.verbose:
                            print(f"Deleting {file_fullname}...")
                        os.remove(file_fullname)
                    else:
                        if config.verbose:
                            print(f"Moving {file_fullname} to trash...")
                        if trash_dir is None or len(trash_dir) <= 0:
                            send2trash(file_fullname)
                        else:
                            shutil.move(file_fullname, os.path.join(trash_dir, file_name))
                            #log_file = f"{os.path.join(trash_dir, file_name)}.log"
                            #with open(log_file, 'w', encoding='utf-8') as log:
                                #log.write(' '.join(extracted_texts))
            except Exception as ex:
                if config.verbose:
                    print(f"Exception: {str(ex)}")
        if config.recursive:
            for dir_name in dir_names:
                remove_qr_images(os.path.join(dir_path, dir_name), config)

if __name__=="__main__":
    parser: optparse.OptionParser = optparse.OptionParser('%prog [options] photo_directory')
    parser.add_option('--delete', '-d', action='store_false', help='Permanent delete photos')
    parser.add_option('--verbose', '-v', action='store_false', help='Verbose mode')
    parser.add_option('--recursive', '-r', action='store_false', help='Recursively walk directories')
    parser.add_option('--jobs', '-j', default=1, help='Number of concurence jobs. Default is 1')
    parser.add_option('--trash', '-t', default="", help="Trash directory to move detected files")
    parser.add_option('--detector', '', default=1, help="Detector to be used. Default is 1. 1=pyzbar, 2=YOLO")

    opts, args = parser.parse_args()

    if len(args)<=0:
        print("Error: There is no photo directory specified.")
        sys.exit(1)
    dirs: list = []
    config: Configuration = Configuration()
    config.verbose = True if opts.verbose is not None else False
    config.permanent_delete = True if opts.delete is not None else False
    config.recursive = True if opts.recursive is not None else False
    config.trash_dir = opts.trash

    for dir in args:
        dir_fullname = os.path.abspath(dir)
        if not os.path.exists(dir_fullname):
            print(f"Warning: Directory {dir} is not exist.")
        else:
            dirs.append(dir_fullname)
    
    if len(dirs) <= 0:
        print("No any directory speicied.")
        sys.exit(1)

    jobs: int  = 1
    try:
        jobs = int(opts.jobs)
    except:
        jobs = 1
    with concurrent.futures.ProcessPoolExecutor(max_workers=max(32, jobs)) as executor:
        future_to_dirs = { executor.submit(remove_qr_images, dir, config) : dir for dir in dirs }