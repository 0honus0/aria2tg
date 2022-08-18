import aria2p
from typing import List , Callable
from aria2p.downloads import Download
from aria2p import Options
# from loguru import logger
# logger.enable("aria2p")

class Aria2:

    def __init__(self, host = "localhost", port = 6800, secret = "" ):
        self.aria2 = aria2p.API(aria2p.Client(host=host,port=port,secret=secret))
        self.options = Options(api = self.aria2 , struct = {})
    #     self.set_options()

    # def set_options(self):
    #     #不保存下载的种子文件
    #     self.options.bt_save_metadata = False

    def add_magnets(self, magnets : List[str]) -> List[Download]:
        downloads = []
        for magnet in magnets:
            try:
                download = self.aria2.add_magnet(magnet_uri = magnet, options = self.options)
            except:
                download = False
            downloads.append(download)
        return downloads

    def add_urls(self, urls : List[str]) -> List[Download]:
        downloads = []
        for url in urls:
            try:
                download = self.aria2.add_uris(uris = urls, options = self.options)
            except:
                download = False
            downloads.append(download)
        return downloads

    def add_torrents(self, torrents_path : List[str]) -> List[Download]:
        downloads = []
        for path in torrents_path:
            download = self.aria2.add_torrent(torrent_file_path = path, options = self.options)
            downloads.append(download)
        return downloads

    def add_metalinks(self, metalinks : List[str]):
        for metalink in metalinks:
            self.aria2.add_metalink(metalink_file_path = metalink, options = self.options)
 
    def get_downloads(self, gids : List[str] = []) -> List[Download | bool]:
        downloads = []
        if isinstance(gids, str):
            gids = [gids.strip()]
        if gids == []:
            downloads = self.aria2.get_downloads()
        else:
            for gid in gids:
                try:
                    download = self.aria2.get_download(gid)
                    downloads.append(download)
                except:
                    downloads.append(False)
        return downloads
    
    def remove_downloads(self, gids : List[str] = []):
        result = []
        if isinstance(gids, str) and gids:
            gids = [gids]
        downloads = self.get_downloads(gids)  
        for download in downloads:
            if download:
                res = self.aria2.remove(downloads = [download], force = True, files = True, clean = True)[0]
            else:
                res = False
            result.append(res) 
        return result

