import re
from contextlib import contextmanager
from dataclasses import dataclass
from unittest.mock import MagicMock

import aqt
import os

from _pytest.monkeypatch import MonkeyPatch
from aqt.addons import AddonsDialog, ConfigEditor
from aqt.qt import QColor, QWidget, QPixmap

from tests.anki_tools import move_main_window_to_state, anki_version
from tests.conftest import wait_until, wait


image_save_folder = os.getcwd()


def get_screenshot(window: QWidget) -> QPixmap:
    return window.screen().grabWindow(window.winId()).toImage()


def get_color(obj: "QWidget | QPixmap", x: int, y: int) -> str:
    if isinstance(obj, QWidget):
        obj = get_screenshot(obj)
    return QColor(obj.pixel(x, y)).name()


def save_screenshot(window: QWidget, image_name: str):
    image = get_screenshot(window)
    image_path = os.path.join(image_save_folder, image_name)
    image.save(image_path)
    print(f":: saved image: {image_path}")


@contextmanager
def screenshot_saved_on_error(window: QWidget, image_name: str):
    try:
        yield
    except Exception:
        save_screenshot(window, image_name)
        raise


def set_window_dimensions(window: QWidget, width: int, height: int):
    window.resize(width, height)


########################################################################################


def test_main_window(setup):
    window = aqt.mw
    set_window_dimensions(window, 500, 500)

    # looking for the gray line below upper links.
    # it might have different colors, so just see if there's anything at all
    def main_window_ready():
        screenshot = get_screenshot(window)
        different_colors = {get_color(screenshot, 5, 40 + x) for x in range(16)}
        return len(different_colors) > 1

    with screenshot_saved_on_error(window, "test_main_window.png"):
        wait_until(main_window_ready)

        assert get_color(window, 5, 5) == "#eeebe7"  # menu
        assert get_color(window, 5, 40) == "#eeebe7"  # links
        assert get_color(window, 5, 280) == "#eeebe7"  # main area
        assert get_color(window, 5, 490) == "#e5dfd9"  # bottom area


# on Anki 2.1.49 tag area is an input field and has white background
# on Anki 2.1.49+ it's a special thing with tags and has transparent background
def test_add_cards_dialog(setup):
    dialog = aqt.dialogs.open("AddCards", aqt.mw)
    set_window_dimensions(dialog, 500, 500)

    with screenshot_saved_on_error(dialog, "test_add_cards_dialog.png"):
        wait_until(lambda: get_color(dialog, 330, 230) == "#ffffff")  # field2
        assert get_color(dialog, 5, 5) == "#eeebe7"  # edge
        assert get_color(dialog, 270, 80) == "#eeebe7"  # buttons area
        assert get_color(dialog, 270, 270) == "#eeebe7"  # main area
        if anki_version >= (2, 1, 50):
            assert get_color(dialog, 270, 430) == "#eeebe7"  # tags area
        assert get_color(dialog, 5, 490) == "#e5dfd9"  # bottom area


def test_edit_current_dialog(setup):
    move_main_window_to_state("review")
    dialog = aqt.dialogs.open("EditCurrent", aqt.mw)
    set_window_dimensions(dialog, 500, 500)

    with screenshot_saved_on_error(dialog, "test_edit_current_dialog.png"):
        wait_until(lambda: get_color(dialog, 330, 200) == "#ffffff")  # field2

        assert get_color(dialog, 5, 5) == "#eeebe7"  # edge
        assert get_color(dialog, 270, 60) == "#eeebe7"  # buttons area
        assert get_color(dialog, 270, 270) == "#eeebe7"  # main area
        if anki_version >= (2, 1, 50):
            assert get_color(dialog, 270, 440) == "#eeebe7"  # tags area
        assert get_color(dialog, 5, 490) == "#e5dfd9"  # bottom area


def test_previewer(setup):
    browser = aqt.dialogs.open("Browser", aqt.mw)
    wait_until(lambda: browser.editor.note is not None)

    browser.onTogglePreview()
    previewer = browser._previewer
    set_window_dimensions(previewer, 500, 500)

    with screenshot_saved_on_error(previewer, "test_previewer.png"):
        wait_until(lambda: get_color(previewer, 30, 30) == "#ff0000")  # our red marker

        assert get_color(previewer, 5, 5) == "#eeebe7"  # edge
        assert get_color(previewer, 5, 490) == "#e5dfd9"  # bottom area


########################################################################################


def replace_in_config(pattern: str, replacement: str):
    addon = "anki_wallpaper"
    config = aqt.mw.addonManager.getConfig(addon)

    addons_dialog = AddonsDialog(aqt.mw.addonManager)
    config_editor = ConfigEditor(addons_dialog, addon, config)

    text = config_editor.form.editor.toPlainText()
    changed_text = re.sub(pattern, replacement, text)
    assert changed_text != text
    config_editor.form.editor.setPlainText(changed_text)

    config_editor.accept()
    addons_dialog.accept()


@dataclass
class Called:
    mock: MagicMock

    @property
    def times(self):
        return self.mock.call_count

    @property
    def first_argument(self):
        return self.mock.call_args_list[0].args[0]

    @property
    def text_argument(self):
        return self.mock.call_args_list[0].kwargs["text"]


@contextmanager
def method_mocked(*args):
    with MonkeyPatch().context() as context:
        mock = MagicMock()
        context.setattr(*args, mock)
        yield Called(mock)


def test_anki_freaks_out_with_invalid_json_schema(setup):
    with method_mocked(aqt.addons, "showInfo") as called:
        replace_in_config("a", "b")
        assert called.times == 1
        assert "is a required property" in called.first_argument

    with method_mocked(aqt.addons, "showInfo") as called:
        replace_in_config("edit_current", "edit_kitten")
        assert called.times == 1
        assert "is not one of" in called.first_argument


def test_anki_freaks_out_with_inaccessible_folder(setup):
    with method_mocked(setup.anki_wallpaper.configuration, "showWarning") as called:
        replace_in_config(r'"/[^"]+"', '"/root/"')
        assert called.times == 1
        assert "Permission denied" in called.text_argument


def test_anki_freaks_out_with_not_existing_folder(setup):
    with method_mocked(setup.anki_wallpaper.configuration, "showWarning") as called:
        replace_in_config(r'"/[^"]+"', '"/owo whats this/"')
        assert called.times == 1
        assert "No such file" in called.text_argument

def test_anki_freaks_out_with_wanted_files_missing(setup):
    from anki_wallpaper.configuration import read_config, FOLDER_WITH_WALLPAPERS

    wallpaper_folder = read_config()[FOLDER_WITH_WALLPAPERS]
    os.remove(os.path.join(wallpaper_folder, "kitten.dark.png"))
    os.remove(os.path.join(wallpaper_folder, "puppy.dark.png"))

    with method_mocked(setup.anki_wallpaper.configuration, "showWarning") as called:
        replace_in_config(': 0', ': 1')
        assert called.times == 1
        assert "does not contain dark wallpapers" in called.text_argument
