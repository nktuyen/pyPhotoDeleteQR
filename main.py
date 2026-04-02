import os
import sys
import cv2
from pyzbar.pyzbar import decode
import optparse
import concurrent.futures
import shutil
from send2trash import send2trash

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


def remove_qr_images(dir: str, config: Configuration = Configuration()):
    print(f"Searching for photo in {dir}...")
    if not os.path.exists(dir):
        return
    IMAGE_EXTENSIONS: list = ['.png', '.jpg', '.jpeg', '.tif', '.gif', '.bmp', '.heic']
    trash_dir: str = config.trash_dir
    for dir_path, dir_names, file_names in os.walk(dir):
        for file_name in file_names:
            _, file_ext = os.path.splitext(file_name)
            if file_ext.lower() not in IMAGE_EXTENSIONS:
                continue
            file_fullname = os.path.join(dir_path, file_name)
            print(f"Decoding {file_fullname}...")
            try:
                img = cv2.imread(file_fullname)
                if img is None:
                    continue
                codes = decode(img)
                if codes:
                    print(f"QR code detected.")
                    if config.permanent_delete:
                        print(f"Deleting {file_fullname}...")
                        os.remove(file_fullname)
                    else:
                        print(f"Moving {file_fullname} to trash...")
                        if trash_dir is None or len(trash_dir) <= 0:
                            send2trash(file_fullname)
                        else:
                            shutil.move(file_fullname, os.path.join(trash_dir, file_name))
            except Exception as ex:
                print(f"Exception: {str(ex)}")

if __name__=="__main__":
    parser: optparse.OptionParser = optparse.OptionParser('%prog [options] photo_directory')
    parser.add_option('--delete', '-d', action='store_false', help='Permanent delete photos')
    parser.add_option('--verbose', '-v', action='store_false', help='Verbose mode')
    parser.add_option('--recursive', '-r', action='store_false', help='Recursively walk directories')
    parser.add_option('--jobs', '-j', default=1, help='Number of concurence jobs. Default is 1')
    parser.add_option('--trash', '-t', default="", help="Trash directory to move detected files")

    opts, args = parser.parse_args()
    print(opts)
    print(args)

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

    jobs: int  = 1
    try:
        jobs = int(opts.jobs)
    except:
        jobs = 1
    with concurrent.futures.ProcessPoolExecutor(max_workers=max(32, jobs)) as executor:
        future_to_dirs = { executor.submit(remove_qr_images, dir, config) : dir for dir in dirs }