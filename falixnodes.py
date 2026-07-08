import time
import os
import json
import re
import random
import requests

# 智能环境配置：仅在未设置时才应用默认值
# 这样兼容 GitHub Actions 的 xvfb-run (会自动设置 DISPLAY) 和 Docker 环境
if "DISPLAY" not in os.environ:
    os.environ["DISPLAY"] = ":1"
    
if "XAUTHORITY" not in os.environ:
    # 仅当路径存在时才设置，避免在 GitHub Runner (home/runner) 中报错
    if os.path.exists("/home/headless/.Xauthority"):
        os.environ["XAUTHORITY"] = "/home/headless/.Xauthority"

print(f"[DEBUG] Env DISPLAY: {os.environ.get('DISPLAY')}")
print(f"[DEBUG] Env XAUTHORITY: {os.environ.get('XAUTHORITY')}")

from seleniumbase import SB

# ================= 配置区域 =================
PROXY_URL = os.getenv("PROXY", "")  # 代理
EMAIL = os.getenv("EMAIL")  # 邮箱
PASSWORD = os.getenv("PASSWORD")  # 密码
SERVERNUM = os.getenv("SERVERNUM")  # 服务器编号
TG_TOKEN = os.getenv("TG_TOKEN")  # tg通知token
TG_CHAT_ID = os.getenv("TG_CHAT_ID")  # tg通知chat_id

# 目标 URL
LOGIN = "https://client.falixnodes.net/auth/login"
TAGET = f"https://client.falixnodes.net/timer?id={SERVERNUM}"
# ===========================================

class FalixNodesRenewal:
    def __init__(self):
        self.BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        self.screenshot_dir = os.path.join(self.BASE_DIR, "artifacts")
        if not os.path.exists(self.screenshot_dir):
            os.makedirs(self.screenshot_dir)

    def log(self, msg):
        timestamp = time.strftime('%H:%M:%S')
        print(f"[{timestamp}] [INFO] {msg}", flush=True)

    def human_wait(self, min_s=6, max_s=10):
        """随机模拟人类等待时间"""
        time.sleep(random.uniform(min_s, max_s))

    def move_mouse_human(self, sb):
        """模拟人类鼠标晃动预热"""
        try:
            # 在页面不同位置“晃悠”一下鼠标，打破机器人直线模式
            for _ in range(3):
                x = random.randint(100, 800)
                y = random.randint(100, 600)
                sb.slow_click(f"body", force=True) # 借用 slow_click 的移动特性，或者直接用 move_to
                time.sleep(random.uniform(0.5, 1.2))
        except: pass

    def send_telegram_notify(self, message, photo_path=None):
        """发送 Telegram 通知 (带图片)"""
        if not TG_TOKEN or not TG_CHAT_ID:
            self.log("⚠️ 未配置 TG_TOKEN 或 TG_CHAT_ID，跳过推送。")
            return
        
        try:
            if photo_path and os.path.exists(photo_path):
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"
                with open(photo_path, 'rb') as f:
                    # caption 参数用于发送带文字的图片
                    requests.post(url, data={'chat_id': TG_CHAT_ID, 'caption': message}, files={'photo': f})
            else:
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
                requests.post(url, data={'chat_id': TG_CHAT_ID, 'text': message})
            
            self.log("✅ TG 推送已发送")
        except Exception as e:
            self.log(f"❌ TG 推送失败: {e}")

    def run(self):
        self.log("=" * 40)
        self.log("🚀 FalixNodes - 保活流程")
        self.log("=" * 40)
        self.log("🎯 正在启动 Chrome 浏览器...")
        
        # 使用 headed=True 强制有头模式渲染到 VNC
        with SB(
            uc=True,            # 启用反检测模式
            test=True, 
            headed=True,        # 关键：强制有头模式
            headless=False,     # 明确禁用 headless
            xvfb=False,         # 禁用内部虚拟显示器，使用系统 DISPLAY
            chromium_arg="--no-sandbox,--disable-dev-shm-usage,--disable-gpu,--window-position=0,0,--start-maximized",
            proxy=PROXY_URL if PROXY_URL else None
        ) as sb:
            try:
                self.log("✅ 浏览器已启动！")
                
                # ... (省略中间步骤，保持原有逻辑不变) ...
                
                # 1. IP 检测
                self.log("🌍 正在检测出口 IP...")
                try:
                    sb.open("https://api.ipify.org?format=json")
                    ip_val = json.loads(re.search(r'\{.*\}', sb.get_text("body")).group(0)).get('ip', 'Unknown')
                    parts = ip_val.split('.')
                    self.log(f"✅ 当前出口 IP: {parts[0]}.{parts[1]}.***.{parts[-1]}")
                except:
                    self.log("⚠️ IP 检测跳过...")

                # 2. 登录
                self.log("🔗 访问登录页面并尝试登录...")
                sb.uc_open_with_reconnect(LOGIN, reconnect_time=25)
                time.sleep(5)
                self.log("⏳ 开始登录验证Cloudflare")
                cf_indicators = [
                    "verify you are human",
                    "确认您是真人",
                    "troubleshoot",
                    "just a moment"
                ]
                for i in range(10): # 尝试10次
                    sb.uc_gui_click_captcha()
                    time.sleep(3)
                    page_lower = sb.get_page_source().lower()
                    if any(x in page_lower for x in cf_indicators):
                        sb.uc_gui_handle_captcha()
                        time.sleep(3)
                        page_lower = sb.get_page_source().lower()
                    if not any(x in page_lower for x in cf_indicators):
                        self.log("✅Cloudflare验证已通过")
                        break
                sb.type("#email-address", "your_email@example.com")
                sb.type("#password", "your_password")
                sb.click("button.auth-submit-btn")
                time.sleep(5)

               login_screenshot = f"{self.screenshot_dir}/login.png"
                sb.save_screenshot(login_screenshot)
                self.send_telegram_notify("✅邮箱密码登录完毕", login_screenshot)

                # 3. 访问目标页面
                self.log("🔗 访问目标页面...")
                sb.uc_open_with_reconnect(TAGET, reconnect_time=25)
                time.sleep(5)

                before = sb.get_text("#timer-page-countdown") # Renew前剩余时间

                # 4. 验证Cloudflare
                self.log("⏳ 开始验证Cloudflare")
                cf_indicators = [
                    "verify you are human",
                    "确认您是真人",
                    "troubleshoot",
                    "just a moment"
                ]
                for i in range(10): # 尝试10次
                    sb.uc_gui_click_captcha()
                    time.sleep(3)
                    page_lower = sb.get_page_source().lower()
                    if any(x in page_lower for x in cf_indicators):
                        sb.uc_gui_handle_captcha()
                        time.sleep(3)
                        page_lower = sb.get_page_source().lower()
                    if not any(x in page_lower for x in cf_indicators):
                        self.log("✅Cloudflare验证已通过")
                        break

                taget_screenshot = f"{self.screenshot_dir}/taget.png"
                sb.save_screenshot(taget_screenshot)
                self.send_telegram_notify("✅访问保活页面并通过Cloudflare认证", taget_screenshot)
                
                # 5. 点击各种按钮
                self.log("🖱️ 开始处理点击各种按钮")

                self.log("🖱️ 点击添加时间/Addtime")
                sb.wait_for_element_visible("#timer-page-btn", timeout=10)
                sb.click("#timer-page-btn")
                time.sleep(1)
                self.log("✅ 点击添加时间/Addtime完毕")
                time.sleep(2)

                self.log("🖱️ 点击观看广告/WatchAD")
                sb.wait_for_element_visible("#watchAdBtn", timeout=10)
                sb.click("#watchAdBtn")
                time.sleep(15)
                self.log("✅ 点击观看广告/WatchAD完毕")

                # 通常成功后会返回服务器面板登录页面,因为没有cookies
                click_screenshot = f"{self.screenshot_dir}/click.png"
                sb.save_screenshot(click_screenshot)
                self.send_telegram_notify("✅访问页面并通过Cloudflare认证", click_screenshot)

                # 6. 再次访问目标页面
                self.log("🔗 再次访问目标页面...")
                sb.uc_open_with_reconnect(TAGET, reconnect_time=25)
                time.sleep(5)
                after = sb.get_text("#timer-page-countdown") # Renew前剩余时间

                self.log("✅ 全部流程执行完毕")
                finish_screenshot = f"{self.screenshot_dir}/finish.png"
                sb.save_screenshot(finish_screenshot)
                self.send_telegram_notify(f"🎉 FalixNodes 保活成功\n🖥️ 编号: {SERVERNUM}\n🕒 保活前剩余运行时间: {before}\n🚀 保活后剩余运行时间: {after}", finish_screenshot)
            
            except Exception as e:
                self.log(f"❌ 运行异常: {e}")
                import traceback
                traceback.print_exc()
                sb.save_screenshot(f"{self.screenshot_dir}/error.png")


if __name__ == "__main__":
    FalixNodesRenewal().run()
