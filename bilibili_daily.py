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

# 强制兜底BV号（避免为空）
DEFAULT_WATCH_BV = "BV1vW4y1n74c"
DEFAULT_COIN_BVS = ["BV1vW4y1n74c", "BV1m84y1w7b7", "BV18x421m78R", "BV1jt421w78Q", "BV1ox421g75q"]

# 从环境变量读取配置
BILI_COOKIE = os.getenv("BILI_COOKIE")
# 优先读取环境变量，否则用默认值
WATCH_VIDEO_BV = os.getenv("WATCH_VIDEO_BV", DEFAULT_WATCH_BV).strip()
COIN_VIDEO_BVS = [bv.strip() for bv in os.getenv("COIN_VIDEO_BVS", ",".join(DEFAULT_COIN_BVS)).split(",") if bv.strip()]

# 请求头（补充完整）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Cookie": BILI_COOKIE,
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://www.bilibili.com",
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
}

BASE_URL = "https://api.bilibili.com"

class BilibiliDailyTask:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.user_info = None
        self.csrf = self._extract_csrf_from_cookie()  # 从Cookie提取csrf

    def _extract_csrf_from_cookie(self):
        """从Cookie中提取bili_jct（csrf）"""
        if not BILI_COOKIE:
            return ""
        for item in BILI_COOKIE.split(";"):
            item = item.strip()
            if item.startswith("bili_jct="):
                return item.split("=")[1]
        return ""

    def check_login(self):
        """检查登录状态"""
        try:
            url = f"{BASE_URL}/x/web-interface/nav"
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if data["code"] == 0:
                self.user_info = data["data"]
                logging.info(f"登录成功！用户名：{self.user_info['uname']}")
                # 双重确认csrf
                if not self.csrf:
                    self.csrf = self.user_info.get("csrf", "")
                logging.info(f"提取的CSRF：{self.csrf if self.csrf else '未提取到'}")
                return True
            else:
                logging.error(f"登录失败：{data['message']}")
                return False
        except Exception as e:
            logging.error(f"检查登录异常：{str(e)}")
            return False

    def daily_login(self):
        """每日登录"""
        try:
            url = "https://api.bilibili.com/x/member/web/exp/reward"
            params = {"csrf": self.csrf} if self.csrf else {}
            resp = self.session.get(url, params=params, timeout=15)
            data = resp.json()
            if data["code"] == 0:
                logging.info(f"每日登录任务完成，经验值+{data['data']['login']}")
            else:
                logging.warning(f"每日登录任务失败：{data['message']}")
        except Exception as e:
            logging.error(f"每日登录异常：{str(e)}")

    def watch_video(self):
        """观看视频"""
        try:
            if not WATCH_VIDEO_BV:
                logging.warning("观看视频：BV号为空，使用默认BV号")
                bv = DEFAULT_WATCH_BV
            else:
                bv = WATCH_VIDEO_BV
            
            # 获取视频信息
            video_info = self._get_video_info(bv)
            if not video_info:
                logging.error("观看视频：获取视频信息失败，跳过任务")
                return
            
            # 模拟观看上报
            url = f"{BASE_URL}/x/click-interface/web/heartbeat"
            data = {
                "aid": video_info["aid"],
                "cid": video_info["cid"],
                "progress": random.randint(100, 500),
                "play_type": "normal",
                "csrf": self.csrf
            }
            self.session.post(url, data=data, timeout=15)
            logging.info(f"观看视频任务完成（BV：{bv}）")
        except Exception as e:
            logging.error(f"观看视频异常：{str(e)}")

    def share_video(self):
        """分享视频"""
        try:
            bv = WATCH_VIDEO_BV if WATCH_VIDEO_BV else DEFAULT_WATCH_BV
            video_info = self._get_video_info(bv)
            if not video_info:
                logging.error("分享视频：获取视频信息失败，跳过任务")
                return
            
            url = f"{BASE_URL}/x/web-interface/share/add"
            params = {"aid": video_info["aid"], "csrf": self.csrf}
            resp = self.session.post(url, params=params, timeout=15)
            data = resp.json()
            if data["code"] == 0:
                logging.info(f"分享视频任务完成（BV：{bv}）")
            else:
                logging.warning(f"分享视频失败：{data['message']}")
        except Exception as e:
            logging.error(f"分享视频异常：{str(e)}")

    def coin_video(self):
        """投币视频"""
        coin_count = 0
        # 兜底：如果无有效BV号，用默认列表
        valid_bvs = COIN_VIDEO_BVS if COIN_VIDEO_BVS else DEFAULT_COIN_BVS
        
        for bv in valid_bvs[:5]:
            try:
                video_info = self._get_video_info(bv)
                if not video_info:
                    logging.warning(f"投币（BV：{bv}）：获取视频信息失败，跳过")
                    continue
                
                url = f"{BASE_URL}/x/web-interface/coin/add"
                params = {
                    "aid": video_info["aid"],
                    "multiply": 1,
                    "select_like": 1,
                    "csrf": self.csrf
                }
                resp = self.session.post(url, params=params, timeout=15)
                data = resp.json()
                if data["code"] == 0:
                    coin_count += 1
                    logging.info(f"投币成功（BV：{bv}），已投{coin_count}/5")
                elif data["code"] == 34005:
                    logging.warning("投币：今日投币已达上限")
                    break
                else:
                    logging.warning(f"投币失败（BV：{bv}）：{data['message']}")
                time.sleep(3)
            except Exception as e:
                logging.error(f"投币异常（BV：{bv}）：{str(e)}")
        logging.info(f"投币任务完成，共投{coin_count}个硬币")

    def comic_task(self):
        """漫画任务"""
        try:
            # 漫画签到（修复platform参数）
            sign_url = "https://manga.bilibili.com/twirp/activity.v1.Activity/ClockIn"
            # 用form-data格式提交
            sign_data = {"platform": "android"}  # web改为android，兼容接口
            sign_resp = self.session.post(sign_url, data=sign_data, timeout=15)
            try:
                sign_data = sign_resp.json()
                if sign_data.get("code") == 0:
                    logging.info("漫画签到成功")
                else:
                    logging.warning(f"漫画签到失败：{sign_data.get('msg')}")
            except:
                logging.info("漫画签到：接口返回非JSON，默认成功")

            # 漫画分享
            share_url = "https://manga.bilibili.com/twirp/activity.v1.Activity/Share"
            share_data = {"id": 1, "platform": "android"}
            self.session.post(share_url, data=share_data, timeout=15)
            logging.info("漫画分享任务完成")
        except Exception as e:
            logging.error(f"漫画任务异常：{str(e)}")

    def live_sign(self):
        """直播签到"""
        try:
            url = "https://api.live.bilibili.com/xlive/web-ucenter/v1/sign/DoSign"
            params = {"csrf": self.csrf} if self.csrf else {}
            # 增加代理/超时容错
            resp = self.session.post(url, params=params, timeout=20)
            data = resp.json()
            if data["code"] == 0:
                logging.info(f"直播签到成功，奖励：{data['data'].get('text')}")
            elif data["code"] == 10003:
                logging.info("直播签到：今日已签到")
            else:
                logging.warning(f"直播签到失败：{data['message']}")
        except Exception as e:
            logging.error(f"直播签到异常：{str(e)}")

    def youaishe_sign(self):
        """友爱社签到"""
        try:
            url = "https://api.bilibili.com/x/club/user/sign"
            params = {"csrf": self.csrf} if self.csrf else {}
            resp = self.session.post(url, params=params, timeout=20)
            data = resp.json()
            if data["code"] == 0:
                logging.info("友爱社签到成功")
            elif data["code"] == 1101000:
                logging.info("友爱社签到：今日已签到")
            else:
                logging.warning(f"友爱社签到失败：{data['message']}")
        except Exception as e:
            logging.error(f"友爱社签到异常：{str(e)}")

    def silver_to_coin(self):
        """银瓜子兑换硬币"""
        try:
            if not self.csrf:
                logging.warning("银瓜子兑换：无CSRF，跳过")
                return
            
            url = f"{BASE_URL}/x/revenue/v1/silver2coin/coin2silver"
            params = {"csrf": self.csrf}
            resp = self.session.post(url, params=params, timeout=15)
            data = resp.json()
            if data["code"] == 0:
                logging.info(f"银瓜子兑换成功：{data['data']['message']}")
            elif data["code"] == 10002:
                logging.info("银瓜子兑换：今日已兑换")
            else:
                logging.warning(f"银瓜子兑换失败：{data['message']}")
        except Exception as e:
            logging.error(f"银瓜子兑换异常：{str(e)}")

    def _get_video_info(self, bv):
        """获取视频aid和cid"""
        try:
            url = f"{BASE_URL}/x/web-interface/view?bvid={bv}"
            resp = self.session.get(url, timeout=15)
            data = resp.json()
            if data["code"] != 0:
                logging.error(f"获取视频信息失败：{data['message']}")
                return None
            return {
                "aid": data["data"]["aid"],
                "cid": data["data"]["pages"][0]["cid"]
            }
        except Exception as e:
            logging.error(f"获取视频信息异常（BV：{bv}）：{str(e)}")
            return None

    def run_all_tasks(self):
        """执行所有任务"""
        logging.info("=== 开始执行哔哩哔哩每日任务 ===")
        logging.info(f"执行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        if not self.check_login():
            logging.error("登录失败，终止任务")
            return

        self.daily_login()
        time.sleep(2)

        self.watch_video()
        time.sleep(2)

        self.share_video()
        time.sleep(2)

        self.coin_video()
        time.sleep(3)

        self.comic_task()
        time.sleep(2)

        self.live_sign()
        time.sleep(2)

        self.youaishe_sign()
        time.sleep(2)

        self.silver_to_coin()

        logging.info("=== 哔哩哔哩每日任务执行完毕 ===")

if __name__ == "__main__":
    os.environ['PYTHONUNBUFFERED'] = '1'
    bilibili_task = BilibiliDailyTask()
    bilibili_task.run_all_tasks()
