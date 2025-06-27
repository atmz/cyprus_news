#!/bin/bash

#8news260323.mp4

today=`date -v -1d +%d%m%y`

url_video=http://v6.cloudskep.com/rikvod/idisisstisokto/8news"$today".mp4?attachment=true
downloaded_filename=./news/8news"$today"a.mp4?attachment=true
local_filename_video=./news/8news"$today".mp4
local_filename_audio=./news/8news"$today".mp3
local_filename_audio_short_prefix=./news/8news"$today"_
text_gr=./news/8news"$today"_gr.txt
text_en=./news/8news"$today"_en.txt
text_gr_short=./news/8news"$today"_gr_3min.txt
text_en_short=./news/8news"$today"_en_3min.txt

echo "$local_filename_video."
if [ -f $local_filename_video ]; then 
    echo "$local_filename_video exists."
else
	wget $url_video -P ./news
    mv $downloaded_filename $local_filename_video
fi

if [ -f $local_filename_audio ]; then
    echo "$local_filename_audio exists."
else
    ffmpeg -i $local_filename_video  -vn -codec:a libmp3lame -qscale:a 4 $local_filename_audio
    ffmpeg  -i $local_filename_video -vn -segment_time 00:03:00 -f segment -reset_timestamps 1  -codec:a libmp3lame -qscale:a 4 $local_filename_audio_short_prefix%03d.mp3
fi

if [ -f $text_gr ]; then
    echo "$text_gr exists."
else
    python3 transcribe.py
fi

