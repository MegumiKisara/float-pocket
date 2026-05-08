

1. 该项目用uv管理包
2. 重新打包后，不要修改上一次该应用的设置信息
3. 每次修改后都要重启应用
4. 不要自己提交git，听我指令

5. QAction/QMenu 等 Qt 对象必须设置 parent 或由 Python 变量持有，防止被 GC 回收导致无声失效

6. 开发运行: uv run python main.py

7. 打包: uv run pyinstaller FloatPocket.spec

8. DATA_DIR = <exe所在目录>/data/ (打包后) 或 项目根目录/data/ (开发时)
   config.json 存储所有用户配置，修改配置逻辑时确保不覆盖已有设置

9. 修改 hotkey 相关代码时，需同步更新 hotkey_module.py 和 tray_module 中配置界面的快捷键列表

10. 应用通过 QLockFile(data/instance.lock) 实现单实例，调试时如果报"已在运行中"，删除该文件即可