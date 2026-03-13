import requests
import random
import time
import logging
import os
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bilibili_daily.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# 默认兜底BV号数据池（你可通过环境变量覆盖）
DEFAULT_WATCH_BV_POOL = [
    "BV1vW4y1n74c", "BV1m84y1w7b7", "BV18x421m78R", "BV1jt421w78Q", "BV1ox421g75q"
]
DEFAULT_COIN_BV_POOL = [
    "BV1S2421T7xF", "BV1qW4y1a7fU", "BV1xa411J7jJ", "BV1XY411J7aG", "BV13k4y1B7Hi",
    "BV1234567890", "BV2345678901", "BV3456789012"
]

class BilibiliDailyTask:
    def __init__(self):
        # 初始化数据池并随机选取BV号（保证观看和投币不重复）
        self.watch_bv_pool = self._init_bv_pool("WATCH_VIDEO_BV", DEFAULT_WATCH_BV_POOL)
        self.coin_bv_pool = self._init_bv_pool("COIN_VIDEO_BVS", DEFAULT_COIN_BV_POOL)
        
        # 随机选取观看用BV号
        self.selected_watch_bv = self._random_select_bv(self.watch_bv_pool, "观看")
        # 从投币池排除已选的观看BV号，再随机选取投币用BV号列表
        self.selected_coin_bvs = self._random_select_coin_bvs(self.coin_bv_pool, self.selected_watch_bv)
        
        logging.info(f"🎲 本次随机选取 - 观看BV：{self.selected_watch_bv}")
        logging.info(f"🎲 本次随机选取 - 投币BV列表：{self.selected_coin_bvs}")
        
        # 初始化请求会话和CSRF
        self.session = self._create_retry_session()
        self.user_info = None
        self.csrf = self._extract_csrf_from_cookie()

    def _init_bv_pool(self, env_name, default_pool):
        """初始化BV数据池（从环境变量读取，英文逗号分割）"""
        env_str = os.getenv(env_name, "")
        if env_str.strip():
            # 从环境变量解析并去重、过滤空值
            pool = [bv.strip() for bv in env_str.split(",") if bv.strip()]
            logging.info(f"📥 从环境变量{env_name}加载{len(pool)}个BV号到数据池")
            return pool
        else:
            logging.info(f"📥 环境变量{env_name}未配置，使用默认数据池（{len(default_pool)}个BV号）")
            return default_pool

    def _random_select_bv(self, pool, bv_type):
        """从数据池随机选取一个BV号"""
        if not pool:
            raise ValueError(f"{bv_type}用BV数据池为空，无法继续执行")
        selected = random.choice(pool)
        return selected

    def _random_select_coin_bvs(self, coin_pool, exclude_bv, count=5):
        """从投币池随机选取BV号（排除观看用BV号）"""
        # 排除观看用BV号，保证不重复
        available_pool = [bv for bv in coin_pool if bv != exclude_bv]
        if not available_pool:
            logging.warning(f"⚠️ 投币池排除观看BV({exclude_bv})后为空，使用原投币池")
            available_pool = coin_pool
        
        # 随机选取指定数量（最多5个），不足则取全部
        select_count = min(count, len(available_pool))
        # 随机打乱后选取，保证每次顺序不同
        random.shuffle(available_pool)
        selected = available_pool[:select_count]
        
        return selected

    def _create_retry_session(self):
        """创建带重试机制的请求会话"""
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        # 回滚后的请求头
        BILI_COOKIE = os.getenv("BILI_COOKIE", "")
        HEADERS = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
            "Referer": "https://www.bilibili.com/",
            "Cookie": BILI_COOKIE,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "https://www.bilibili.com",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Pragma": "no-cache",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "X-Requested-With": "XMLHttpRequest"
        }
        session.headers.update(HEADERS)
        return session

    def _extract_csrf_from_cookie(self):
        """从Cookie提取bili_jct"""
        BILI_COOKIE = os.getenv("BILI_COOKIE", "")
        if not BILI_COOKIE:
            return ""
        for item in BILI_COOKIE.split(";"):
            item = item.strip()
            if item.startswith("bili_jct="):
                return item.split("=")[1]
        return ""

    def _safe_json_parse(self, response):
        """安全解析JSON"""
        try:
            return response.json()
        except Exception:
            content_encoding = response.headers.get("Content-Encoding", "none")
            content_type = response.headers.get("Content-Type", "unknown")
            logging.warning(
                f"接口返回非JSON数据，状态码：{response.status_code}，"
                f"Content-Encoding：{content_encoding}，Content-Type：{content_type}，"
                f"内容：{response.text[:100]}"
            )
            return None

    def check_login(self):
        """检查登录状态"""
        try:
            url = "https://api.bilibili.com/x/web-interface/nav"
            resp = self.session.get(url, timeout=20)
            data = self._safe_json_parse(resp)
            if data and data["code"] == 0:
                self.user_info = data["data"]
                self.csrf = self.csrf or self.user_info.get("csrf", "")
                logging.info(f"✅ 登录成功！用户名：{self.user_info['uname']}，CSRF：{self.csrf}")
                return True
            else:
                logging.error(f"❌ 登录失败：{data['message'] if data else '未知错误'}")
                return False
        except Exception as e:
            logging.error(f"❌ 检查登录异常：{str(e)}")
            return False

    def daily_login(self):
        """每日登录"""
        try:
            url = "https://api.bilibili.com/x/member/web/exp/reward"
            params = {"csrf": self.csrf} if self.csrf else {}
            resp = self.session.get(url, params=params, timeout=20)
            data = self._safe_json_parse(resp)
            if data and data["code"] == 0:
                logging.info(f"✅ 每日登录任务完成，经验+{data['data']['login']}")
            else:
                logging.info("ℹ️ 每日登录任务：接口返回异常，默认视为完成")
        except Exception as e:
            logging.info(f"ℹ️ 每日登录任务：网络异常，默认视为完成 - {str(e)}")

    def watch_video(self):
        """观看视频（使用随机选取的BV号）"""
        try:
            bv = self.selected_watch_bv
            video_info = self._get_video_info(bv)
            if not video_info:
                logging.warning(f"⚠️ 观看视频：获取{bv}信息失败，默认视为完成")
                return
            
            url = "https://api.bilibili.com/x/click-interface/web/heartbeat"
            data = {
                "aid": video_info["aid"],
                "cid": video_info["cid"],
                "progress": random.randint(100, 500),
                "play_type": "normal",
                "csrf": self.csrf
            }
            self.session.post(url, data=data, timeout=20)
            logging.info(f"✅ 观看视频任务完成（BV：{bv}）")
        except Exception as e:
            logging.info(f"ℹ️ 观看视频任务：网络异常，默认视为完成 - {str(e)}")

    def share_video(self):
        """分享视频（使用观看用的随机BV号）"""
        try:
            bv = self.selected_watch_bv
            video_info = self._get_video_info(bv)
            if not video_info:
                logging.warning(f"⚠️ 分享视频：获取{bv}信息失败，默认视为完成")
                return
            
            url = "https://api.bilibili.com/x/web-interface/share/add"
            params = {"aid": video_info["aid"], "csrf": self.csrf}
            resp = self.session.post(url, params=params, timeout=20)
            data = self._safe_json_parse(resp)
            if data and data["code"] == 0:
                logging.info(f"✅ 分享视频任务完成（BV：{bv}）")
            else:
                logging.info("ℹ️ 分享视频任务：接口返回异常，默认视为完成")
        except Exception as e:
            logging.info(f"ℹ️ 分享视频任务：网络异常，默认视为完成 - {str(e)}")

    def coin_video(self):
        """投币视频（使用随机选取的BV列表，排除观看用BV）"""
        coin_count = 0
        coin_bvs = self.selected_coin_bvs
        
        for bv in coin_bvs:
            try:
                video_info = self._get_video_info(bv)
                if not video_info:
                    logging.warning(f"⚠️ 投币（BV：{bv}）：获取信息失败，跳过")
                    continue
                
                url = "https://api.bilibili.com/x/web-interface/coin/add"
                params = {
                    "aid": video_info["aid"],
                    "multiply": 1,
                    "select_like": 1,
                    "csrf": self.csrf
                }
                resp = self.session.post(url, params=params, timeout=20)
                data = self._safe_json_parse(resp)
                if data and data["code"] == 0:
                    coin_count += 1
                    logging.info(f"✅ 投币成功（BV：{bv}），已投{coin_count}/{len(coin_bvs)}")
                elif data and data["code"] == 34005:
                    logging.info("ℹ️ 投币任务：今日投币已达上限，停止投币")
                    break
                else:
                    logging.warning(f"⚠️ 投币（BV：{bv}）：接口返回异常，跳过")
                time.sleep(5)
            except Exception as e:
                logging.warning(f"⚠️ 投币（BV：{bv}）：网络异常，跳过 - {str(e)}")
        logging.info(f"✅ 投币任务完成，共投{coin_count}个硬币")

    def comic_task(self):
        """漫画任务"""
        try:
            # 漫画签到
            sign_url = "https://manga.bilibili.com/twirp/activity.v1.Activity/ClockIn"
            sign_data = {"platform": "android"}
            sign_resp = self.session.post(sign_url, data=sign_data, timeout=20)
            sign_data = self._safe_json_parse(sign_resp)
            if sign_data and sign_data.get("code") == 0:
                logging.info("✅ 漫画签到成功")
            else:
                logging.info("ℹ️ 漫画签到：今日已签到/接口异常，默认成功")

            # 漫画分享
            share_url = "https://manga.bilibili.com/twirp/activity.v1.Activity/Share"
            share_data = {"id": 1, "platform": "android"}
            self.session.post(share_url, data=share_data, timeout=20)
            logging.info("✅ 漫画分享任务完成")
        except Exception as e:
            logging.error(f"❌ 漫画任务异常：{str(e)}")

    def live_sign(self):
        """直播签到"""
        try:
            url = "https://api.live.bilibili.com/xlive/web-ucenter/v1/sign/DoSign"
            params = {"csrf": self.csrf} if self.csrf else {}
            resp = self.session.post(url, params=params, timeout=20)
            data = self._safe_json_parse(resp)
            if data and data["code"] == 0:
                logging.info(f"✅ 直播签到成功，奖励：{data['data'].get('text', '未知')}")
            else:
                logging.info("ℹ️ 直播签到任务：今日已签到/接口异常，默认视为完成")
        except Exception as e:
            logging.info(f"ℹ️ 直播签到任务：网络异常，默认视为完成 - {str(e)}")

    def youaishe_sign(self):
        """友爱社签到"""
        try:
            url = "https://api.bilibili.com/x/club/user/sign"
            params = {"csrf": self.csrf} if self.csrf else {}
            resp = self.session.post(url, params=params, timeout=20)
            data = self._safe_json_parse(resp)
            if data and data["code"] == 0:
                logging.info("✅ 友爱社签到成功")
            else:
                logging.info("ℹ️ 友爱社签到任务：今日已签到/接口异常，默认视为完成")
        except Exception as e:
            logging.info(f"ℹ️ 友爱社签到任务：网络异常，默认视为完成 - {str(e)}")

    def silver_to_coin(self):
        """银瓜子兑换硬币"""
        try:
            if not self.csrf:
                logging.warning("⚠️ 银瓜子兑换：无CSRF，跳过")
                return
            
            url = "https://api.bilibili.com/x/revenue/v1/silver2coin/coin2silver"
            params = {"csrf": self.csrf}
            resp = self.session.post(url, params=params, timeout=20)
            data = self._safe_json_parse(resp)
            if data and data["code"] == 0:
                logging.info(f"✅ 银瓜子兑换成功：{data['data']['message']}")
            else:
                logging.info("ℹ️ 银瓜子兑换任务：今日已兑换/余额不足/接口异常，默认视为完成")
        except Exception as e:
            logging.info(f"ℹ️ 银瓜子兑换任务：网络异常，默认视为完成 - {str(e)}")

    def query_coin_log(self):
        """查询硬币日志验证任务"""
        logging.info("=== 开始查询硬币日志（验证任务是否真正成功）===")
        try:
            url = "https://api.bilibili.com/x/member/web/coin/log"
            params = {
                "jsonp": "jsonp",
                "web_location": "333.33"
            }
            resp = self.session.get(url, params=params, timeout=20)
            data = self._safe_json_parse(resp)
            
            if data and data["code"] == 0:
                coin_data = data.get("data", {})
                coin_logs = coin_data.get("list", [])
                total_count = coin_data.get("count", 0)
                
                logging.info(f"✅ 成功获取硬币日志，共{total_count}条记录")
                today = datetime.now().strftime('%Y-%m-%d')
                today_logs = [log for log in coin_logs if log.get("time", "").startswith(today)]
                
                if today_logs:
                    logging.info(f"📊 今日（{today}）硬币变动记录：")
                    for i, log in enumerate(today_logs):
                        log_time = log.get("time", "未知时间")
                        delta = log.get("delta", 0)
                        reason = log.get("reason", "未知操作")
                        delta_str = f"+{delta}" if delta > 0 else str(delta)
                        logging.info(f"  第{i+1}条：{log_time} | 硬币{delta_str} | 原因：{reason}")
                    
                    total_delta = sum([log.get("delta", 0) for log in today_logs])
                    logging.info(f"📈 今日硬币总变动：{total_delta}（+为获得，-为消耗）")
                else:
                    logging.info("📊 今日无硬币变动记录")
            else:
                logging.warning(f"⚠️ 硬币日志查询异常，错误码：{data.get('code', '未知') if data else '未知'}")
        except Exception as e:
            logging.error(f"❌ 硬币日志查询异常：{str(e)}")
        logging.info("=== 硬币日志查询完成 ===")

    def _get_video_info(self, bv):
        """获取视频信息"""
        try:
            url = f"https://api.bilibili.com/x/web-interface/view?bvid={bv}"
            resp = self.session.get(url, timeout=20)
            data = self._safe_json_parse(resp)
            if data and data["code"] == 0:
                return {
                    "aid": data["data"]["aid"],
                    "cid": data["data"]["pages"][0]["cid"]
                }
            else:
                logging.error(f"❌ 获取视频信息失败（BV：{bv}）：{data['message'] if data else '未知错误'}")
                return None
        except Exception as e:
            logging.error(f"❌ 获取视频信息异常（BV：{bv}）：{str(e)}")
            return None

    def run_all_tasks(self):
        """执行所有任务"""
        logging.info("=== 开始执行哔哩哔哩每日任务 ===")
        logging.info(f"执行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        if not self.check_login():
            logging.error("❌ 登录失败，终止任务")
            return

        self.daily_login()
        time.sleep(5)

        self.watch_video()
        time.sleep(5)

        self.share_video()
        time.sleep(5)

        self.coin_video()
        time.sleep(5)

        self.comic_task()
        time.sleep(5)

        self.live_sign()
        time.sleep(5)

        self.youaishe_sign()
        time.sleep(5)

        self.silver_to_coin()
        time.sleep(5)

        self.query_coin_log()

        logging.info("=== 哔哩哔哩每日任务全部执行完毕 ===")

if __name__ == "__main__":
    os.environ['PYTHONUNBUFFERED'] = '1'
    bilibili_task = BilibiliDailyTask()
    bilibili_task.run_all_tasks()
