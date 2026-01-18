"""
应用程序入口
启动NiceGUI Web界面
"""
from nicegui import ui
from ui.pages import setup_ui
import sys
from pathlib import Path


def check_dependencies():
    """检查必要的依赖"""
    required_modules = [
        'nicegui',
        'PIL',
        'piexif',
        'gpxpy',
        'pandas',
        'python-dateutil'
    ]
    
    missing = []
    for module in required_modules:
        try:
            if module == 'PIL':
                __import__('PIL')
            elif module == 'python-dateutil':
                __import__('dateutil')
            else:
                __import__(module)
        except ImportError:
            missing.append(module)
    
    if missing:
        print("❌ 缺少以下依赖包：")
        for module in missing:
            print(f"  - {module}")
        print("\n请运行以下命令安装：")
        print(f"  pip install {' '.join(missing)}")
        return False
    
    return True


def main():
    """主函数"""
    print("=" * 60)
    print("📍 tracklog-to-exif|照片exif的GPS标注")
    print("=" * 60)
    
    # 检查依赖
    print("正在检查依赖包...")
    if not check_dependencies():
        sys.exit(1)
    print("✓ 依赖检查通过")
    
    # 确保核心目录存在
    core_dir = Path(__file__).parent / 'core'
    ui_dir = Path(__file__).parent / 'ui'
    
    if not core_dir.exists():
        print("❌ 错误：找不到 core 目录")
        sys.exit(1)
    
    if not ui_dir.exists():
        print("❌ 错误：找不到 ui 目录")
        sys.exit(1)
    
    print("✓ 项目结构检查通过")
    
    # 设置UI
    print("正在启动Web界面...")
    setup_ui()
    
    # 启动NiceGUI
    print("✓ Web服务器启动成功")
    print("-" * 60)
    print("📱 请在浏览器中访问：http://localhost:12138")
    print("💡 提示：按 Ctrl+C 停止服务器")
    print("=" * 60)
    
    try:
        ui.run(
            title='tracklog-to-exif|照片exif的GPS标注',
            port=12138,
            show=True,
            reload=False
        )
    except KeyboardInterrupt:
        print("\n\n👋 服务器已停止")
    except Exception as e:
        print(f"\n❌ 启动失败：{e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

