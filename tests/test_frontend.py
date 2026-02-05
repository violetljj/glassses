# -*- coding: utf-8 -*-
"""
前端 E2E 测试 (Playwright)

测试 A.VISION Web 界面的核心功能
注意：需要先启动后端服务才能运行这些测试

运行方式：
1. 启动后端: python main.py
2. 运行测试: pytest tests/test_frontend.py -v
"""
import pytest

# 检查 playwright 是否可用
try:
    from playwright.sync_api import sync_playwright, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


@pytest.fixture(scope="module")
def browser_page():
    """创建浏览器实例和页面"""
    if not PLAYWRIGHT_AVAILABLE:
        pytest.skip("Playwright 未安装，跳过前端测试")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        yield page
        browser.close()


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright 未安装")
class TestFrontendHUD:
    """测试 HUD 界面元素"""

    @pytest.fixture(autouse=True)
    def setup(self, browser_page):
        """每个测试前导航到首页"""
        self.page = browser_page
        try:
            self.page.goto("http://localhost:5000", timeout=5000)
            self.page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pytest.skip("后端服务未运行，跳过前端测试")

    def test_page_title(self):
        """验证页面标题"""
        assert "A.VISION" in self.page.title()

    def test_hero_title_visible(self):
        """验证主标题可见"""
        hero = self.page.locator(".hero-title")
        assert hero.is_visible()

    def test_video_element_exists(self):
        """验证视频元素存在"""
        video = self.page.locator("#video-stream")
        assert video.count() == 1

    def test_metrics_cards_visible(self):
        """验证指标卡片显示"""
        metrics = self.page.locator(".metric-card")
        # 应该有 4 个指标卡片 (FPS, 延迟, 推理, 检测)
        assert metrics.count() >= 4

    def test_glass_panels_exist(self):
        """验证玻璃面板存在"""
        panels = self.page.locator(".glass-panel")
        assert panels.count() >= 3  # 控制台、语音交互、日志

    def test_status_indicators_exist(self):
        """验证状态指示灯存在"""
        infer_dot = self.page.locator("#dot-infer")
        audio_dot = self.page.locator("#dot-audio")
        assert infer_dot.count() == 1
        assert audio_dot.count() == 1

    def test_voice_panel_visible(self):
        """验证语音交互面板可见"""
        voice_panel = self.page.locator("#voice-panel")
        assert voice_panel.is_visible()


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright 未安装")
class TestFrontendAPI:
    """测试前端与后端 API 交互"""

    @pytest.fixture(autouse=True)
    def setup(self, browser_page):
        self.page = browser_page
        try:
            self.page.goto("http://localhost:5000", timeout=5000)
            self.page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pytest.skip("后端服务未运行，跳过前端测试")

    def test_health_api_accessible(self):
        """验证健康检查 API 可访问"""
        response = self.page.request.get("http://localhost:5000/health")
        assert response.ok
        data = response.json()
        assert data.get("ok") is True

    def test_detect_api_returns_data(self):
        """验证检测 API 返回数据"""
        response = self.page.request.get("http://localhost:5000/detect")
        assert response.ok
        data = response.json()
        # 验证返回的数据结构
        assert "fps" in data or "infer_ms" in data or "boxes" in data


# 独立运行提示
if __name__ == "__main__":
    print("请使用 pytest 运行测试:")
    print("  pytest tests/test_frontend.py -v")
    print("")
    print("注意：请先启动后端服务:")
    print("  python main.py")
