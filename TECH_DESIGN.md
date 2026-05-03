# FloatPocket 自用悬浮工具 技术文档（AI读取精简版）

# 1\. 文档概述

明确FloatPocket（Windows悬浮工具）技术实现、技术栈、模块设计、测试及部署，适配AI读取，聚焦核心开发信息，用于开发指导与维护。核心功能：系统托盘、悬浮球、剪贴板OCR/翻译、单层快捷应用、计划表，本地存储无云端交互。

# 2\. 技术选型

## 2\.1 核心技术栈

|技术类别|选型方案|核心用途|
|---|---|---|
|主程序框架|Python 3\.9\+ \+ PySide6|悬浮窗、托盘、UI界面、核心交互实现|
|全局快捷键|pynput|后台监听全局热键，唤起悬浮球|
|剪贴板操作|Pillow \+ PySide6 QClipboard|读取剪贴板图片，格式转换适配OCR|
|API调用|requests|调用OCR/翻译API，处理请求与异常|
|数据存储|JSON文件（本地存储）|存储配置、应用分类、待办数据，持久化|
|打包工具|auto\-py\-to\-exe|打包单EXE，免安装，适配Windows|
|Python依赖管理|uv|高效管理Python依赖，替代直接pip安装|

## 2\.2 uv依赖管理配置

使用uv管理Python依赖，替代传统pip，配置文件为pyproject\.toml，核心配置如下：

```toml
# pyproject.toml
[project]
name = "float-pocket"
version = "1.0.0"
dependencies = [
  "PySide6==6.5.2",
  "pynput==1.7.6",
  "Pillow==10.1.0",
  "requests==2.31.0",
  "pyperclip==1.8.2",
  "auto-py-to-exe==2.24",
]

[tool.uv]
python-version = "3.9"  # 适配Python 3.9+

```

uv核心操作命令（AI可直接执行）：

- 安装uv：`pip install uv`

- 安装依赖：`uv install`（读取pyproject\.toml自动安装所有依赖）

- 新增依赖：`uv add 依赖名==版本号`

- 删除依赖：`uv remove 依赖名`

# 3\. 系统架构设计

模块化架构，低耦合，核心模块及职责（AI开发核心参考）：

- 主程序入口（main\.py）：初始化各模块，协调交互，启动应用

- 系统托盘模块（TrayModule）：托盘常驻、左右键交互，关联悬浮球

- 悬浮球模块（FloatBallModule）：唤起/隐藏、拖动、边缘吸附、功能菜单

- 配置管理模块（ConfigModule）：管理全局配置，JSON读写，开机自启实现

- OCR翻译模块（OcrTranslateModule）：剪贴板图片读取、API调用、结果展示/复制

- 快捷应用模块（AppLauncherModule）：单层分类、应用管理与启动

- 计划表模块（TodoListModule）：待办增删改查，本地持久化

# 4\. 核心模块实现细节（AI开发重点）

## 4\.1 主程序入口（main\.py）

```python
import sys
from PySide6.QtWidgets import QApplication
from tray_module import TrayModule
from float_ball import FloatBallModule
from config_module import ConfigModule

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    config_module = ConfigModule()
    float_ball = FloatBallModule(config_module)
    tray_module = TrayModule(app, float_ball, config_module)
    sys.exit(app.exec())
```

## 4\.2 OCR翻译模块（核心功能）

```python
import base64
import requests
from PIL import Image
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QClipboard

class OcrTranslateModule(QWidget):
    def __init__(self, config_module):
        super().__init__()
        self.config = config_module
        self.clipboard = QClipboard()
        
    def get_clipboard_image(self):
        """读取剪贴板图片，转base64"""
        if self.clipboard.mimeData().hasImage():
            image = self.clipboard.image()
            image_bytes = image.toImage().bits().asstring(image.byteCount())
            return base64.b64encode(image_bytes).decode('utf-8')
        return None
    
    def call_ocr_api(self, image_base64):
        """调用OCR API，返回识别结果/错误提示"""
        url = self.config.get("api_url")
        api_key = self.config.get("api_key")
        headers = {"Authorization": f"Bearer {api_key}"}
        data = {"image": image_base64, "type": "ocr"}
        try:
            response = requests.post(url, json=data, timeout=10)
            response.raise_for_status()
            return response.json().get("result", "")
        except Exception as e:
            return f"识别失败：{str(e)}"
    
    def call_translate_api(self, image_base64):
        """调用翻译API，返回翻译结果/错误提示"""
        url = self.config.get("api_url")
        api_key = self.config.get("api_key")
        headers = {"Authorization": f"Bearer {api_key}"}
        data = {"image": image_base64, "type": "translate"}
        try:
            response = requests.post(url, json=data, timeout=10)
            response.raise_for_status()
            return response.json().get("result", "")
        except Exception as e:
            return f"翻译失败：{str(e)}"
```

## 4\.3 快捷应用模块（单层分类）

apps\.json核心结构（AI读取配置参考）：

```json
{
  "categories": ["开发工具", "办公软件", "未分类"],
  "apps": [
    {
      "name": "VSCode",
      "path": "C:\\Program Files\\Microsoft VS Code\\Code.exe",
      "category": "开发工具"
    }
  ]
}
```

## 4\.4 配置管理模块（核心配置）

config\.json核心结构：

```json
{
  "auto_start": true,
  "global_hotkey": "ctrl+alt+s",
  "float_ball": {"size": 60, "opacity": 0.8, "edge_adsorption": true},
  "api_config": {"api_url": "https://api.example.com/ocr-translate", "api_key": "your_api_key", "timeout": 10},
  "theme": "light"
}
```

# 5\. 测试与打包部署（精简核心）

## 5\.1 核心测试点

- 功能测试：托盘/悬浮球交互、OCR/翻译（剪贴板粘贴\+API调用）、快捷应用分类与启动、配置生效

- 稳定性测试：后台常驻无闪退、高频操作无卡顿、异常场景（断网/密钥错误）提示正常

- 兼容性测试：适配Windows 10/11 64位，打包后EXE可直接运行

## 5\.2 打包部署（uv依赖下）

1. 用uv安装所有依赖：`uv install`

2. 打包：运行auto\-py\-to\-exe，配置main\.py路径、单EXE、隐藏控制台、图标，添加assets/config目录

3. 部署：复制EXE到任意目录，双击运行，可开启开机自启

# 6\. 核心注意事项（AI开发提醒）

- uv依赖管理：通过pyproject\.toml管理依赖，避免版本冲突

- API调用：确保api\_url和api\_key正确，网络通畅，异常需捕获并提示

- 数据存储：JSON文件需有读写权限，程序启动时加载默认配置

> （注：文档部分内容可能由 AI 生成）
