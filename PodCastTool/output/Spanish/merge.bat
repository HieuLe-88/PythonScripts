@echo off
setlocal enabledelayedexpansion

:: 1. Tạo file list.txt
echo Dang danh sach video...
(for %%i in (*.mp4) do @echo file '%%i') > list.txt

:: 2. Chạy lệnh FFmpeg (Sử dụng Re-encoding thay vì Copy)
echo Dang tien hanh gop video và dong bo lai am thanh...
:: -c:v libx264: Encode lại hình ảnh chuẩn H.264
:: -c:a aac: Encode lại âm thanh chuẩn AAC
:: -strict experimental: Đảm bảo tính tương thích
ffmpeg -f concat -safe 0 -i list.txt -c:v libx264 -preset fast -crf 22 -c:a aac -b:a 192k "Gop_Ket_Qua_Fixed.mp4"

:: 3. Xóa file list.txt
del list.txt

echo.
echo === HOAN THANH! Video da duoc dong bo tai Gop_Ket_Qua_Fixed.mp4 ===
pause