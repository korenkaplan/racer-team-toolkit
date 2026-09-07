#!/bin/bash

set -e

DEVICE="R52Y901B9AP"

BACKUP_DIR="$HOME/Desktop/time-adjustment-test"
REFF_BACKUP="$BACKUP_DIR/reff"
VIDEO_BACKUP="$BACKUP_DIR/videos"

REMOTE_REFF="/sdcard/Records"
REMOTE_VIDEOS="/sdcard/Eyesatop-Records/Screen-Videos"

echo "Resetting Time Adjustment test..."
echo

echo "Deleting old REFF test files..."

adb -s "$DEVICE" shell rm -f \
    "$REMOTE_REFF/01_08_2024_08_27.reff" \
    "$REMOTE_REFF/01_08_2024_08_27_Number_1.reff" \
    "$REMOTE_REFF/01_08_2024_08_28.reff"

echo "Deleting old video test files..."

adb -s "$DEVICE" shell rm -f \
    "$REMOTE_VIDEOS/ScreenRec_2024-08-01_08-27.mp4" \
    "$REMOTE_VIDEOS/ScreenRec_2024-08-01_08-28.mp4"

echo
echo "Pushing original REFF test files..."

adb -s "$DEVICE" push -a \
    "$REFF_BACKUP/." \
    "$REMOTE_REFF/"

echo
echo "Pushing original video test files..."

adb -s "$DEVICE" push -a \
    "$VIDEO_BACKUP/." \
    "$REMOTE_VIDEOS/"

echo
echo "REFF timestamps:"
adb -s "$DEVICE" shell \
    'for f in /sdcard/Records/*; do [ -f "$f" ] && stat -c "%y %n" "$f"; done'

echo
echo "Video timestamps:"
adb -s "$DEVICE" shell \
    'for f in /sdcard/Eyesatop-Records/Screen-Videos/*; do [ -f "$f" ] && stat -c "%y %n" "$f"; done'

echo
echo "Time Adjustment test files restored."