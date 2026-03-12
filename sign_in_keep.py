import requests
import random
import time
import datetime
import logging
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sign_in.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# 从环境变量读取敏感配置（对应GitHub Secrets）
BASE_URL = os.getenv("ZEPP_BASE_URL", "http://yd.zeeplife.cn/sign/zepplife.php")
USERNAME = os.getenv("ZEPP_USERNAME")
PASSWORD = os.getenv("ZEPP_PASSWORD")
REMOTE = os.getenv("ZEPP_REMOTE", "0")
STEP_MIN = int(os.getenv("ZEPP_STEP_MIN", 19000))
STEP_MAX = int(os.getenv("ZEPP_STEP_MAX", 19999))

# 请求头（Cookie也移到环境变量）
HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "zh-CN,zh-Hans;q=0.9",
    "Connection": "keep-alive",
    "Cookie": os.getenv("ZEPP_COOKIE", ""),
    "Priority": "u=0, i",
    "Referer": "http://yd.zeeplife.cn/index.php?mod=list-sign",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.2 Safari/605.1.15"
}


def get_random_step():
    """生成随机的step值"""
    return random.randint(STEP_MIN, STEP_MAX)


def sign_in():
    """执行签到操作"""
    # 校验必要参数
    if not all([USERNAME, PASSWORD, HEADERS["Cookie"]]):
        logging.error("必要配置未填写！请检查GitHub Secrets")
        return

    try:
        # 生成随机step值
        step = get_random_step()

        # 构造请求参数
        params = {
            "username": USERNAME,
            "password": PASSWORD,
            "step": step,
            "remote": REMOTE
        }

        logging.info(f"开始执行签到，step值：{step}")

        # 发送请求
        response = requests.get(
            BASE_URL,
            params=params,
            headers=HEADERS,
            timeout=30
        )

        # 记录结果
        if response.status_code == 200:
            logging.info(f"签到成功！状态码：{response.status_code}")
            logging.info(f"响应内容：{response.text[:500]}")  # 只记录前500个字符
        else:
            logging.error(f"签到失败！状态码：{response.status_code}")

    except Exception as e:
        logging.error(f"签到过程中出现异常：{str(e)}")


def main():
    """主函数"""
    logging.info("=== 启动签到程序 ===")
    logging.info(f"Step值范围：{STEP_MIN} - {STEP_MAX}")

    # 移除原有的定时等待逻辑，执行时立即签到
    sign_in()


if __name__ == "__main__":
    # 确保脚本输出不缓冲
    if not os.environ.get('PYTHONUNBUFFERED'):
        os.environ['PYTHONUNBUFFERED'] = '1'

    main()