#python库
import threading
import time
from queue import Queue
from urllib.parse  import unquote
import psutil
import tempfile
import os
#typing
from typing import Dict , List , BinaryIO
from aria2p.downloads import Download
from pyrogram.types import Message
#自定义函数
from aria2 import Aria2
from utils import load_config , pybyte , md5
from vpp import *
from sync import Client
#pyrogram
from pyrogram import filters
from pyrogram import errors as pyro_errors
from pyrogram.types import InlineKeyboardButton , InlineKeyboardMarkup , InputMediaVideo

#logging.basicConfig(level=logging.INFO)

class Aria2Tg:
    #要回复消息的群组
    status_send_chats : Dict["Message.chat.id","Message.id"] = {}
    #已有的下载任务与下载名字对应
    tasks    : Dict["Download.gid","Download.name"] = {}
    #文件路径的md5值
    hashs : Dict["md5","Download.name"] = {}
    #上一次运行的时间
    last_run_time = 0
    #上传队列
    upload_queue : Queue = Queue()
    #上传的文件列表，防止重复上传
    upload_list : List["md5"] = []
    #缓存下载文件的所有文件内容  | ["md5(name)","[md5(path) : bool]"] 
    cache : Dict["md5", List] = {}

    def on_admin(self):
        '''
        Execute commands only for user in the list
        '''
        def deco(func):
            async def deco_deco(client : "Client.client" , message : "Message" ):
                if message.from_user.id in self.admins:
                    await func(client , message)
                else:
                    await self.bot.send_message(chat_id = message.chat.id , text = "非管理员无法使用指令")
            return deco_deco
        return deco

    #初始化
    def __init__(self):
        config = load_config()
        host = config['Aria2']['host']
        port = config['Aria2']['port']
        secret = config['Aria2']['secret']
        api_id = config['Telegram']['api_id']
        api_hash = config['Telegram']['api_hash']
        bot_token = config['Telegram']['bot_token']
        self.admins = config['Telegram']['admins']
        self.chat_id = int(config['Telegram']['chat_id'])
        self.aria2 = Aria2(host, port, secret)
        self.bot = Client("TG_Download_Bot" , api_id, api_hash , bot_token)
        self.app = Client("TG_Download_User", api_id, api_hash)
        self.sync_tasks()

        # on magnet link
        @self.bot.on_message(filters.regex("magnet:\?xt=urn:btih:[0-9a-fA-F]{40,}.*"))
        @self.on_admin()
        async def add_magnets(client : "Client.client" , message : "Message"):
            '''
            on magnet link ,add magnet to aria2 and send message to user
            '''
            MagnetList = [k.group(0) for k in message.matches]
            downloads = self.aria2.add_magnets(magnets = MagnetList)
            await message_handle(message, downloads , MagnetList)

        # on http(s) link
        @self.bot.on_message(filters.regex("http[s]:\/\/[\w.]+\/?\S*"))
        @self.on_admin()
        async def on_http_s(client : "Client.client" , message : "Message"):
            '''
            on http or https link ,add http or https link to aria2 and send message to user
            '''
            HttpList = [k.group(0) for k in message.matches]
            downloads = self.aria2.add_urls(urls = HttpList)
            await message_handle(message, downloads , HttpList)

        #torrent file
        @self.bot.on_message(filters.document)
        @self.on_admin()
        async def on_torrent(client : "Client.client" , message : "Message"):
            '''
            on torrent file ,add torrent file to aria2 and send message to user
            '''
            if message.document.mime_type != "application/x-bittorrent":
                await message.reply_text("Not a torrent file")
                return
            file_io = await self.bot.download_media(message , in_memory = True)
            file = tempfile.NamedTemporaryFile(delete = True)
            file_io.seek(0)
            file.write(file_io.read())
            file.flush()
            downloads = self.aria2.add_torrents([file.name])
            file.close()
            await message_handle(message, downloads , [file.name])

        async def message_handle(message : "Message" , downloads : List["Download"] , tasklist : List[str]):
            text = ""
            for index in range(len(downloads)):
                if downloads[index]:
                    self.tasks[downloads[index].gid] = downloads[index].name
                    text += f"`{downloads[index].name}` 添加成功 \n"
                else:
                    text += f"`{tasklist[index]}` 添加失败 \n"
            text += "\n发送 /status 查看进度"
            if text:
                text = unquote(text)
                await self.bot.send_message(chat_id = message.chat.id, text = text)
            else:
                await self.bot.send_message(chat_id = message.chat.id, text = "添加失败")

        @self.bot.on_message(filters.command("status"))
        @self.on_admin()
        async def status(client : "Client.client", message : "Message"):
            '''
            on /status command ,add chat.id and message.id into status_send_chats ,then send progress status to each user in status_send_chats
            '''
            send_message = await self.bot.send_message(chat_id = message.chat.id, text = "更新中...")
            self.status_send_chats[message.chat.id] = send_message.id

        @self.bot.on_message(filters.command("cancel"))
        @self.on_admin()
        async def cancel(client : "Client.client" , message : "Message"):
            '''
            on /cancel command ,cancel download by gid
            '''
            gids  = message.text.split(" ")[1:]
            text = ""
            result = self.aria2.remove_downloads(gids)
            for index in range(len(result)):
                if result[index] == True:
                    try:
                        text += f"`{self.tasks[gids[index]]}({gids[index]})` 已取消\n"
                    except:
                        text += f"`{gids[index]}` 已取消\n"
                    try:
                        self.tasks.pop(gids[index])
                    except:
                        pass
                else:
                    try:
                        text += f"`{self.tasks[gids[index]]}({gids[index]})` 取消失败\n"
                    except:
                        text += f"`{gids[index]}` 取消失败\n"
            if not gids:
                text = "GID为空"
            await self.bot.send_message(chat_id = message.chat.id, text = unquote(text))

        @self.bot.on_message(filters.command("trans"))
        @self.on_admin()
        async def trans(client : "Client.client" , message : "Message"):
            '''
            on /trans commmand, trans the file corresponding to the gid to preconfigured groups
            '''
            command = message.text.split(" ")[-1]
            if command == "cancel":
                self.upload_queue.queue.clear()
                await self.bot.send_message(chat_id = message.chat.id , text = "已清空上传队列")
                return

            download = None
            gid = ""
            text = ""
            try:
                gid  = message.text.split(" ")[1]
                download = self.aria2.get_downloads(gid)[0]
                try:
                    if download.status != "complete":
                        text = "任务未下载完成"
                except:
                    text = "GID错误"
            except:
                text = "GID为空"

            if text:
                await self.bot.send_message(chat_id = message.chat.id, text = text)
                return

            text = "请选择一个文件：\n"

            InlineKey = []
            # path = download.root_files_paths[0]
            download_name_md5 = md5(download.name)
            self.cache[download_name_md5] = []
            for file in download.files:
                file_name = str(file.path).split("/")[-1]
                file_md5 = md5(str(file.path))
                self.hashs[file_md5] = file.path
                self.cache[download_name_md5].append([file_md5, False])
                InlineKey.append([InlineKeyboardButton(text = file_name[0:44] , callback_data = f"md5:{download_name_md5}:{file_md5}")])

            InlineKey.append([InlineKeyboardButton(text = "确定" , callback_data = f"trans_ok: {download_name_md5}"),InlineKeyboardButton(text = "反选" , callback_data = f"trans_all md5: {download_name_md5}:FF"),InlineKeyboardButton(text = "取消" , callback_data = f"trans_cancel")])
            await self.bot.send_message(
                message.chat.id,  
                text,
                reply_markup = InlineKeyboardMarkup(InlineKey)
            )

        @self.bot.on_callback_query()
        async def answer(client, callback_query): 
            if "trans_ok" in callback_query.data:
                callback_download_name_md5 = callback_query.data.split(":")[-1].strip()
                for file in self.cache[callback_download_name_md5]:
                    if file[1] == True:
                        if file[0] in self.upload_list:
                            file_name = str(self.hashs[file[0]]).split("/")[-1]
                            await self.bot.send_message(chat_id = callback_query.message.chat.id, text = f"`{file_name}` 已上传或处理中")
                        else:
                            self.upload_list.append(file[0])
                            self.upload_queue.put((callback_query.message.chat.id , self.hashs[file[0]]))
                self.cache = {}
                self.hashs = {}

            if "trans_cancel" in callback_query.data:
                self.cache = {}
                self.hashs = {}

            if "md5" in callback_query.data:
                callback_download_name_md5 = callback_query.data.split(":")[-2].strip()
                callback_file_md5 = callback_query.data.split(":")[-1].strip()
                InlineKey = []
                for file in self.cache[callback_download_name_md5]:
                    file_path = self.hashs[file[0]]
                    file_name = str(file_path).split("/")[-1]
                    if file[0] == callback_file_md5 or "trans_all" in callback_query.data:
                        file[1] = True if file[1] == False else False
                    if file[1] == True:
                        InlineKey.append([InlineKeyboardButton(text = file_name[0:44] + "✅", callback_data = f"md5 : {callback_download_name_md5} : {file[0]}")])
                    else:
                        InlineKey.append([InlineKeyboardButton(text = file_name[0:44] , callback_data = f"md5 : {callback_download_name_md5} : {file[0]}")])
                InlineKey.append([InlineKeyboardButton(text = "确定" , callback_data = f"trans_ok : {callback_download_name_md5}"),InlineKeyboardButton(text = "反选" , callback_data = f"trans_all md5: {callback_download_name_md5}:FF"),InlineKeyboardButton(text = "取消" , callback_data = f"trans_cancel")])
                await self.bot.edit_message_reply_markup(
                    chat_id = callback_query.message.chat.id,  
                    message_id = callback_query.message.id,
                    reply_markup = InlineKeyboardMarkup(InlineKey)
                )

            if "md5" not in callback_query.data:
                await self.bot.delete_messages(chat_id = callback_query.message.chat.id, message_ids = callback_query.message.id)

    def sync_tasks(self) -> None:
        downloads = self.aria2.get_downloads()
        for download in downloads:
            self.tasks[download.gid] = download.name

    def update_progress(self) -> str:
        downloads = self.aria2.get_downloads()
        content = []
        completed = True
        for download in downloads:
            if download.is_metadata and download.status == "complete":
                self.aria2.remove_downloads(download.gid)
                continue
            text = ""
            name = download.name
            completed_length = download.completed_length
            total_length = download.total_length
            status = download.status
            speed = download.download_speed
            gid = download.gid
            progress = download.progress
            eta = download.eta
            if status == "active":
                completed = False

            text += f"Name : `{name}`\n"
            text += f"Size : `{pybyte(total_length)}`\n"
            text += f"Progress :  `{progress:.2f}%`\n"
            text += f"Status: `{status}`\n"
            if status == "active":
                text += f"Speed : `{pybyte(speed)}/s`\n"
                text += f"ETA : `{eta}`\n"
            text += f"GID : `{gid}`\n"
            content.append(text)
        return "\n".join(content) , completed

    def run(self):
        #更新下载状态信息
        def _progress_run(sleep_time = 3):
            while True:
                if self.status_send_chats:
                    send_chats = dict(self.status_send_chats)
                    text , completed = self.update_progress()
                    
                    cpu_info = psutil.cpu_percent()
                    memory = psutil.virtual_memory()
                    disk = psutil.disk_usage("/")
                    text += f"\n\nCPU : `{cpu_info}%`\n"
                    text += f"Memory : `{pybyte(memory.used)}/{pybyte(memory.total)}`\n"
                    text += f"Disk : `{pybyte(disk.used)}/{pybyte(disk.total)}`"

                    if completed == True or not text:
                        self.status_send_chats.clear()
                        if not text:
                            text = "暂无任务"

                    for chat_id , message_id in send_chats.items():
                        try:
                            self.bot.edit_message_text(chat_id = chat_id, message_id = message_id, text = text)
                        except pyro_errors.exceptions.bad_request_400.MessageNotModified:
                            pass
                time.sleep(sleep_time)

        #处理上传任务
        def _upload_run(sleep_time = 3):
            def send_file_thread(chat_id : str = None , file : str | BinaryIO = None, progress : callable  = None , progress_args: tuple = [] ):
                try:
                    self.app.start()
                except:
                    pass
                
                self.bot.edit_message_text(chat_id = progress_args[0] , message_id = progress_args[1] , text = "预处理视频中。。。")
                video_list = preprocess_video(file , 3950)
                self.bot.edit_message_text(chat_id = progress_args[0] , message_id = progress_args[1] , text = "预处理视频完成。。。")
                count = len(video_list)
                width = get_video_width(file)
                height = get_video_height(file)
                try:
                    if count == 1:
                        video = video_list[0]
                        self.app.send_video(chat_id = chat_id , video = video , thumb = get_video_thumb(file_name = video , width = width, height = height) , progress = progress , progress_args = progress_args , caption = progress_args[3] , width = width, height = height , duration = int(get_video_duration(file)))
                    elif count > 1:
                        media = []
                        index = 0
                        for video in video_list:
                            if index == 0:
                                media.append(InputMediaVideo(media =  video, caption = file.split("/")[-1] , thumb = get_video_thumb(file_name = video , width = width, height = height) , width = width, height = height , duration = int(get_video_duration(video))))
                            else:
                                media.append(InputMediaVideo(media =  video, thumb = get_video_thumb(file_name = video , width = width, height = height) , width = width, height = height , duration = int(get_video_duration(video))))
                            index += 1
                        self.app.send_media_group(chat_id = chat_id , media = media , progress = progress , progress_args = progress_args)

                    for video in video_list:
                        remove_file(video)
                    if get_video_suffix(file) != "mp4":
                        new_file = file.replace(get_video_suffix(file) , "mp4")
                        try:
                            os.remove(new_file)
                        except:
                            pass
                except Exception as e:
                    self.bot.edit_message_text(chat_id = progress_args[0] , message_id = progress_args[1] , text = f"{progress_args[3]} {e}")
                #self.app.stop()

            def trans_progress(current, total , *args):
                chat_id    = args[0]
                message_id = args[1]
                interval   = args[2]
                name       = args[3]
                current_time = time.time()
                text = ""
                text += "上传信息\n\n"
                text += f"name : `{name}`\n"
                text += f"size : `{pybyte(total)}`\n"
                text += f"progress : `{pybyte(current)}/{pybyte(total)}  {(current / total)*100:.2f}%`\n\n"
                text += f"队列剩余任务 : `{self.upload_queue.qsize()}`\n"
                if current == total:
                    self.bot.edit_message_text(chat_id = chat_id , message_id = message_id , text = text)
                elif (current_time - self.last_run_time) > interval:
                    self.last_run_time = current_time
                    self.bot.edit_message_text(chat_id = chat_id , message_id = message_id , text = text)

            while True:
                if not self.upload_queue.empty():
                    chat_id , path = self.upload_queue.get()
                    name = str(path).split("/")[-1]
                    interval = 3
                    message = self.bot.send_message( chat_id = chat_id ,  text = "开始上传。。。")
                    send_file_thread(self.chat_id , str(path) , trans_progress , [chat_id, message.id, interval, name])
                    self.upload_queue.task_done()
                time.sleep(sleep_time)

        p = threading.Thread(target = _progress_run , args=(3,))
        p.daemon = True
        p.start()

        t = threading.Thread(target = _upload_run , args=(3,) )
        t.daemon = True
        t.start()

        #机器人运行
        self.bot.run()

Aria2Tg().run()