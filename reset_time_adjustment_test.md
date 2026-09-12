adb -s R52Y901B9AP shell touch -m -d "@1785567610" "/sdcard/Records/09_09_2026_16_52.reff"

adb -s R52Y901B9AP shell touch -m -d "@1785567915" "/sdcard/Records/10_09_2026_11_58.reff"

adb -s R52Y901B9AP shell touch -m -d "@1785568500" "/sdcard/Records/10_09_2026_12_37.reff"

adb -s R52Y901B9AP shell touch -m -d "@1785567630" "/sdcard/Eyesatop-Records/Screen-Videos/30-45-150-90.mp4"

adb -s R52Y901B9AP shell touch -m -d "@1785567641" "/sdcard/Eyesatop-Records/Screen-Videos/45-45-150-90.mp4"


adb -s R52Y901B9AP shell 'for f in /sdcard/Records/* /sdcard/Eyesatop-Records/Screen-Videos/*; do [ -f "$f" ] && stat -c "%y %n" "$f"; done'


2026-08-01 10:00:10.000000000 +0300 /sdcard/Records/09_09_2026_16_52.reff
2026-08-01 10:05:15.000000000 +0300 /sdcard/Records/10_09_2026_11_58.reff
2026-08-01 10:15:00.000000000 +0300 /sdcard/Records/10_09_2026_12_37.reff
2026-08-01 10:00:05.000000000 +0300 /sdcard/Eyesatop-Records/Screen-Videos/30-45-150-90.mp4
2026-08-01 10:00:08.000000000 +0300 /sdcard/Eyesatop-Records/Screen-Videos/45-45-150-90.mp4
2026-09-10 12:00:00.000000000 +0300 /sdcard/Eyesatop-Records/Screen-Videos/65-45-150-90.mp4