import subprocess
import time

batch_file_path = "restart.bat"

time.sleep(10)
print("restarting......")
subprocess.Popen(batch_file_path, shell=True, stdin=None, stdout=None, stderr=None, close_fds=True)