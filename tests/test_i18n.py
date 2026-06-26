"""国际化模块测试"""

from PySide6.QtCore import QLocale

from src.i18n import tr, install_language, current_locale, _STRINGS


class TestTranslation:
    """翻译功能测试"""

    def test_tr_chinese(self):
        install_language(QLocale(QLocale.Language.Chinese))
        assert tr("设置") == "设置"
        assert tr("下载队列") == "下载队列"
        assert tr("提示") == "提示"

    def test_tr_english(self):
        install_language(QLocale(QLocale.Language.English))
        assert tr("设置") == "Settings"
        assert tr("下载队列") == "Download Queue"
        assert tr("提示") == "Hint"

    def test_tr_fallback(self):
        install_language(QLocale(QLocale.Language.English))
        unknown_key = "不存在的键"
        assert tr(unknown_key) == unknown_key

    def test_tr_with_formatting(self):
        install_language(QLocale(QLocale.Language.English))
        assert tr("共 {0} 项").format(5) == "5 items"
        assert tr("已添加 {0} 个文件到下载队列").format(3) == "Added 3 file(s) to the download queue"

        install_language(QLocale(QLocale.Language.Chinese))
        assert tr("共 {0} 项").format(5) == "共 5 项"

    def test_download_status_translation(self):
        install_language(QLocale(QLocale.Language.English))
        assert tr("等待下载") == "Waiting"
        assert tr("下载中") == "Downloading"
        assert tr("已暂停") == "Paused"
        assert tr("下载完成") == "Completed"
        assert tr("下载失败") == "Failed"
        assert tr("已取消") == "Canceled"
        assert tr("连接中...") == "Connecting..."

    def test_current_locale(self):
        install_language(QLocale(QLocale.Language.English))
        assert current_locale().name() == "en_US"

        install_language(QLocale(QLocale.Language.Chinese))
        assert current_locale().name() == "zh_CN"


class TestTranslationTable:
    """翻译表完整性测试"""

    def test_all_chinese_keys_have_english_values(self):
        for key, value in _STRINGS.items():
            assert value != key or key.isascii(), f"翻译表中中文键 '{key}' 的值应该是英文"

    def test_common_strings_exist(self):
        common_strings = [
            "设置", "下载队列", "开始", "暂停", "继续", "移除", "清空",
            "等待下载", "下载中", "已暂停", "下载完成", "下载失败", "已取消",
            "提示", "错误", "成功", "完成", "失败", "全部",
        ]
        for s in common_strings:
            assert s in _STRINGS, f"缺少翻译: '{s}'"