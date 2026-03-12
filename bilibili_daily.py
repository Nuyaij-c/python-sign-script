import requests
import random
import time
import logging
import os
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bilibili_daily.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# 从环境变量读取敏感配置（对应GitHub Secrets）
BILI_SID = os.getenv("BILI_SID")
# 可选配置：投币视频列表（填写视频BV号，至少5个）
COIN_VIDEO_BVS = os.getenv("COIN_VIDEO_BVS", "BV1xx411c7m8,BV1xt411o7Xu,BV17x411w7KC,BV1ex411x7Em,BV1qx411E79o").split(",")
# 可选配置：观看/分享视频BV号
WATCH_VIDEO_BV = os.getenv("WATCH_VIDEO_BV", "BV1xx411c7m8")

# 请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Cookie": f"sid={BILI_SID}"  # 核心鉴权sid
}

# 基础URL
BASE_URL = "https://api.bilibili.com"

class BilibiliDailyTask:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.user_info = None

    def check_login(self):
        """检查是否登录成功"""
        try:
            url = f"{BASE_URL}/x/web-interface/nav"
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data["code"] == 0:
                self.user_info = data["data"]
                logging.info(f"登录成功！用户名：{self.user_info['uname']}")
                return True
            else:
                logging.error(f"登录失败：{data['message']}")
                return False
        except Exception as e:
            logging.error(f"检查登录异常：{str(e)}")
            return False

    def daily_login(self):
        """每日登录任务"""
        try:
            url = f"{BASE_URL}/x/report/click/v2/sdk/single"
            params = {
                "entry_id": 2907,
                "platform": "web",
                "csrf": self.user_info.get("csrf", "") if self.user_info else ""
            }
            resp = self.session.post(url, params=params, timeout=10)
            data = resp.json()
            if data["code"] == 0:
                logging.info("每日登录任务完成")
            else:
                logging.warning(f"每日登录任务失败：{data['message']}")
        except Exception as e:
            logging.error(f"每日登录异常：{str(e)}")

    def watch_video(self):
        """观看视频任务"""
        try:
            # 模拟观看视频（上报播放进度）
            url = f"{BASE_URL}/x/click-interface/web/heartbeat"
            params = {
                "aid": self._get_aid_by_bv(WATCH_VIDEO_BV),
                "cid": self._get_cid_by_aid(self._get_aid_by_bv(WATCH_VIDEO_BV)),
                "progress": random.randint(60, 300),  # 随机播放进度（秒）
                "play_type": "normal",
                "csrf": self.user_info.get("csrf", "") if self.user_info else ""
            }
            resp = self.session.post(url, data=params, timeout=10)
            data = resp.json()
            if data["code"] == 0:
                logging.info(f"观看视频任务完成（BV：{WATCH_VIDEO_BV}）")
            else:
                logging.warning(f"观看视频任务失败：{data['message']}")
        except Exception as e:
            logging.error(f"观看视频异常：{str(e)}")

    def share_video(self):
        """分享视频任务"""
        try:
            url = f"{BASE_URL}/x/web-interface/share/add"
            params = {
                "aid": self._get_aid_by_bv(WATCH_VIDEO_BV),
                "csrf": self.user_info.get("csrf", "") if self.user_info else ""
            }
            resp = self.session.post(url, params=params, timeout=10)
            data = resp.json()
            if data["code"] == 0:
                logging.info(f"分享视频任务完成（BV：{WATCH_VIDEO_BV}）")
            else:
                logging.warning(f"分享视频任务失败：{data['message']}")
        except Exception as e:
            logging.error(f"分享视频异常：{str(e)}")

    def coin_video(self):
        """视频投币任务（最多5个）"""
        coin_count = 0
        for bv in COIN_VIDEO_BVS[:5]:  # 最多投5个
            try:
                url = f"{BASE_URL}/x/web-interface/coin/add"
                params = {
                    "aid": self._get_aid_by_bv(bv),
                    "multiply": 1,  # 每次投1个
                    "select_like": 1,  # 投币并点赞
                    "csrf": self.user_info.get("csrf", "") if self.user_info else ""
                }
                resp = self.session.post(url, params=params, timeout=10)
                data = resp.json()
                if data["code"] == 0:
                    coin_count += 1
                    logging.info(f"投币成功（BV：{bv}），已投{coin_count}/5")
                    time.sleep(2)  # 避免请求过快
                else:
                    logging.warning(f"投币失败（BV：{bv}）：{data['message']}")
            except Exception as e:
                logging.error(f"投币异常（BV：{bv}）：{str(e)}")
        logging.info(f"投币任务完成，共投{coin_count}个硬币")

    def comic_task(self):
        """漫画任务（签到+分享）"""
        try:
            # 漫画签到
            sign_url = "https://manga.bilibili.com/twirp/activity.v1.Activity/ClockIn"
            sign_resp = self.session.post(sign_url, timeout=10)
            sign_data = sign_resp.json()
            if sign_data.get("code") == 0:
                logging.info("漫画签到成功")
            else:
                logging.warning(f"漫画签到失败：{sign_data.get('msg', '未知错误')}")

            # 漫画分享（随机选一个漫画）
            share_url = "https://manga.bilibili.com/twirp/activity.v1.Activity/Share"
            share_resp = self.session.post(share_url, json={"id": 1}, timeout=10)
            share_data = share_resp.json()
            if share_data.get("code") == 0:
                logging.info("漫画分享任务完成")
            else:
                logging.warning(f"漫画分享失败：{share_data.get('msg', '未知错误')}")
        except Exception as e:
            logging.error(f"漫画任务异常：{str(e)}")

    def live_sign(self):
        """直播签到"""
        try:
            url = "https://api.live.bilibili.com/xlive/web-ucenter/v1/sign/DoSign"
            resp = self.session.post(url, timeout=10)
            data = resp.json()
            if data["code"] == 0:
                logging.info(f"直播签到成功，获得{data['data'].get('text', '')}")
            else:
                logging.warning(f"直播签到失败：{data['message']}")
        except Exception as e:
            logging.error(f"直播签到异常：{str(e)}")

    def youaishe_sign(self):
        """友爱社签到"""
        try:
            url = "https://api.bilibili.com/x/club/user/sign"
            resp = self.session.post(url, timeout=10)
            data = resp.json()
            if data["code"] == 0:
                logging.info("友爱社签到成功")
            else:
                logging.warning(f"友爱社签到失败：{data['message']}")
        except Exception as e:
            logging.error(f"友爱社签到异常：{str(e)}")

    def silver_to_coin(self):
        """银瓜子兑换硬币（每日限1次，700银瓜子=1硬币）"""
        try:
            url = f"{BASE_URL}/x/revenue/v1/silver2coin/coin2silver"
            params = {
                "csrf": self.user_info.get("csrf", "") if self.user_info else ""
            }
            resp = self.session.post(url, params=params, timeout=10)
            data = resp.json()
            if data["code"] == 0:
                logging.info(f"银瓜子兑换硬币成功：{data['data']['message']}")
            else:
                logging.warning(f"银瓜子兑换硬币失败：{data['message']}")
        except Exception as e:
            logging.error(f"银瓜子兑换异常：{str(e)}")

    def _get_aid_by_bv(self, bv):
        """通过BV号获取aid"""
        try:
            url = f"{BASE_URL}/x/web-interface/view?bvid={bv}"
            resp = self.session.get(url, timeout=10)
            return resp.json()["data"]["aid"]
        except Exception as e:
            logging.error(f"获取aid失败（BV：{bv}）：{str(e)}")
            return 0

    def _get_cid_by_aid(self, aid):
        """通过aid获取cid"""
        try:
            url = f"{BASE_URL}/x/player/pagelist?aid={aid}"
            resp = self.session.get(url, timeout=10)
            return resp.json()["data"][0]["cid"]
        except Exception as e:
            logging.error(f"获取cid失败（aid：{aid}）：{str(e)}")
            return 0

    def run_all_tasks(self):
        """执行所有任务"""
        logging.info("=== 开始执行哔哩哔哩每日任务 ===")
        logging.info(f"执行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 1. 检查登录
        if not self.check_login():
            logging.error("登录失败，终止任务执行")
            return

        # 2. 执行各项任务
        self.daily_login()
        time.sleep(1)  # 间隔1秒，避免请求过快

        self.watch_video()
        time.sleep(1)

        self.share_video()
        time.sleep(1)

        self.coin_video()
        time.sleep(2)

        self.comic_task()
        time.sleep(1)

        self.live_sign()
        time.sleep(1)

        self.youaishe_sign()
        time.sleep(1)

        self.silver_to_coin()

        logging.info("=== 哔哩哔哩每日任务执行完毕 ===")

if __name__ == "__main__":
    # 确保输出不缓冲
    os.environ['PYTHONUNBUFFERED'] = '1'
    
    # 初始化并执行任务
    bilibili_task = BilibiliDailyTask()
    bilibili_task.run_all_tasks()
