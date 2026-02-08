@echo off
setlocal enabledelayedexpansion

:: 1. Tạo file list.txt tự động từ các file mp4
echo Dang danh sach video...
(for %%i in (*.mp4) do @echo file '%%i') > list.txt

:: 2. Chạy lệnh FFmpeg để gộp video
echo Dang tien hanh gop video (Stream Copy)...
ffmpeg -f concat -safe 0 -i list.txt -c copy "Gop_Ket_Qua.mp4"

:: 3. Xóa file list.txt sau khi xong
del list.txt

echo.
echo === HOAN THANH! Video da duoc luu thanh Gop_Ket_Qua.mp4 ===
pause