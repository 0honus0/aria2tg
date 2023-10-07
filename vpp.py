from genericpath import isfile
import ffmpeg

import os
import time
from typing import List

M = 1024000

def preprocess_video( file_name : str , size : int) -> List[str]:
    """
    对视频进行预处理，分隔为多个4G以下的视频
    """
    video_list = []
    
    if get_video_suffix(file_name) != "mp4" or not judge_video_mp4(file_name) :
        if judge_codec(file_name):
            file_name = convert_h264_to_mp4(file_name)
        else:
            file_name = convert_all_to_mp4(file_name)

    file_size = os.path.getsize(file_name)
    #提供一部分冗余，防止TG发送失败
    if file_size < (3.90)*1024*1024*1024:
        return [file_name]
    video_total_duration = get_video_duration(file_name)
    video_current_duration = 0.00
    ss = timestamp_to_time(0)
    index = 1
    while abs(video_total_duration - video_current_duration) > 20:
        output_name = ".".join(file_name.split("/")[-1].split(".")[:-1]) + "_" + str(index) + ".mp4"
        video_list.append(output_name)
        ( 
            ffmpeg.input(file_name , ss = ss)
            .output(output_name , codec="copy" , fs = size * M)
            .overwrite_output()
            .run(quiet = True)
        )
        video_current_duration += get_video_duration(output_name)
        ss = timestamp_to_time(video_current_duration)
        index += 1
    return video_list

def get_video_thumb(file_name : str , width : int = 1920 , height : int = 1080) -> str:
    """
    获取视频的缩略图
    """
    video_file = ffmpeg.probe(file_name)
    video_total_duration = float(video_file["format"]["duration"])
    ss = timestamp_to_time(video_total_duration / 3)
    output_name = ".".join(file_name.split("/")[-1].split(".")[:-1]) + "_thumb.jpeg"
    (
        ffmpeg.input( file_name , ss= ss)
        .filter('scale', width , height)
        .output(output_name, vframes=1)
        .overwrite_output()
        .run(quiet = True)
    )
    return output_name

def get_video_duration(file_name : str) -> float:
    """
    获取视频时长
    """
    video_file = ffmpeg.probe(file_name)
    return float(video_file["format"]["duration"])

def get_video_suffix(file_name : str) -> str:
    """
    获取视频后缀
    """
    return file_name.split(".")[-1]

#时间戳转为时间
def timestamp_to_time( timestamp : float) -> str:
    """
    时间戳转为时间
    """
    return time.strftime("%H:%M:%S", time.gmtime(timestamp))

def judge_video_mp4(file_name : str) -> bool:
    """
    判断视频是否为mp4格式
    """
    video_file = ffmpeg.probe(file_name)
    if video_file["format"]["format_name"] == "mov,mp4,m4a,3gp,3g2,mj2":
        return True
    return False

def judge_codec(file_name : str) -> bool:
    """
    判断是否为mp4格式
    """
    video_file = ffmpeg.probe(file_name)
    if video_file["streams"][0]["codec_name"] == "h264":
        return True
    return False

def remove_file(file_name : str) -> None:
    """
    删除封面
    """
    thumb_name = ".".join(file_name.split("/")[-1].split(".")[:-1]) + "_thumb.jpeg"
    if os.path.isfile(thumb_name):
        os.remove(thumb_name)
    if os.path.isfile(file_name):
        os.remove(file_name)

def remove_thumb(file_name : str) -> None:
    """
    删除封面
    """
    thumb_name = ".".join(file_name.split("/")[-1].split(".")[:-1]) + "_thumb.jpeg"
    if os.path.isfile(thumb_name):
        os.remove(thumb_name)

def convert_h264_to_mp4(file_name : str) -> str:
    """
    转换编码格式为h264的文件为mp4
    """
    output_name = ".".join(file_name.split("/")[-1].split(".")[:-1]) + ".mp4"
    (
        ffmpeg.input(file_name)
        .output(output_name , codec = "copy")
        .overwrite_output()
        .run(quiet = True)
    )
    return output_name

def convert_all_to_mp4(file_name : str) -> str:
    """
    转换文件为mp4格式   
    ToDo: 后继优化转码参数
    """
    output_name = ".".join(file_name.split("/")[-1].split(".")[:-1]) + ".mp4"
    (
        ffmpeg.input(file_name)
        .output(output_name , format='h264' , scale= '1920:1080')
        .overwrite_output()
        .run(quiet = True)
    )
    return output_name

def get_video_width(file_name : str) -> int:
    """
    获取视频宽度
    """
    video_file = ffmpeg.probe(file_name)
    try:
        return int(video_file["streams"][0]["width"])
    except:
        return int(video_file["streams"][1]["width"])

def get_video_height(file_name : str) -> int:
    """
    获取视频高度
    """
    video_file = ffmpeg.probe(file_name)
    try:
        return int(video_file["streams"][0]["height"])
    except:
        return int(video_file["streams"][1]["height"])