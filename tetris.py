"""终端俄罗斯方块：界面、按键读取与游戏循环（入口）。

逻辑全部在 game_logic.py；本模块只负责显示、输入与定时。
"""

import os
import shutil
import sys
import time

import game_logic

# 完整界面不得小于 40 字符列 × 28 字符行，见 spec 5.2 / 5.4。
MIN_COLS = 40
MIN_ROWS = 28

CELL = "[]"
EMPTY = "  "
BOARD_WIDTH = game_logic.COLS * len(CELL) + 2
INFO_GAP = "  "

DROP_INTERVAL = 0.5
POLL_INTERVAL = 0.05

KEY_HELP = ("A/D move", "S down", "W rotate", "P pause", "R restart", "Q quit")

TOO_SMALL_HINT = "请将终端调整为至少 40 列 × 28 行"
STARTUP_HINT = "请将终端调整为至少 40 列 × 28 行后重新运行"
QUIT_HINT = "按 Q 退出"

CLEAR_SCREEN = "\x1b[2J\x1b[H"

_saved_posix_attrs = None


def terminal_size():
    size = shutil.get_terminal_size()
    return size.columns, size.lines


def fits_terminal(size):
    cols, rows = size
    return cols >= MIN_COLS and rows >= MIN_ROWS


def render_board(board, piece_cells=()):
    """22 行、每行 22 字符（含 1 字符边框），见 spec 5.2。"""
    active = set(piece_cells)
    border = "+" + "-" * (BOARD_WIDTH - 2) + "+"
    lines = [border]
    for row in range(game_logic.ROWS):
        row_chars = "".join(
            CELL if board[row][col] or (row, col) in active else EMPTY
            for col in range(game_logic.COLS)
        )
        lines.append("|" + row_chars + "|")
    lines.append(border)
    return lines


def render_info(score, state):
    """信息区：分数、状态、空行、按键说明，见 spec 5.1。"""
    return ["Score: {}".format(score), "State: {}".format(state), ""] + list(KEY_HELP)


def render(game):
    """按 spec 5.1 左右拼接；裁掉尾随空格以守住 40 列上限。"""
    piece_cells = game.piece["cells"] if game.piece else ()
    board_lines = render_board(game.board, piece_cells)
    info_lines = [""] + render_info(game.score, game.state)
    lines = []
    for index, board_line in enumerate(board_lines):
        info = info_lines[index] if index < len(info_lines) else ""
        lines.append((board_line + INFO_GAP + info).rstrip())
    if game.too_small:
        lines.append(TOO_SMALL_HINT)
    return lines


def draw(game):
    """回到左上角逐行覆盖并擦到行尾，避免整屏闪烁。"""
    lines = render(game)
    sys.stdout.write("\x1b[H" + "\n".join(line + "\x1b[K" for line in lines) + "\x1b[J")
    sys.stdout.flush()


def configure_output():
    """提示文字含中文；输出被重定向到非 UTF-8 编码时不让程序崩溃。"""
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass


def setup_terminal():
    """进入无需回车的原始输入模式；退出前必须调用 restore_terminal。"""
    global _saved_posix_attrs
    if os.name == "nt":
        _enable_ansi()
        return
    import termios
    import tty

    fd = sys.stdin.fileno()
    _saved_posix_attrs = termios.tcgetattr(fd)
    tty.setcbreak(fd)


def restore_terminal():
    global _saved_posix_attrs
    if _saved_posix_attrs is not None:
        import termios

        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _saved_posix_attrs)
        _saved_posix_attrs = None


def _enable_ansi():
    """旧式控制台需要显式打开虚拟终端处理，Windows Terminal 默认已开。"""
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except (AttributeError, OSError):
        pass


def read_key():
    """非阻塞读一个键；没有按键时返回 None。"""
    if os.name == "nt":
        import msvcrt

        if not msvcrt.kbhit():
            return None
        char = msvcrt.getwch()
        if char in ("\x00", "\xe0"):
            msvcrt.getwch()  # 方向键等双字节键：丢掉第二字节后忽略
            return None
        return char
    import select

    ready, _, _ = select.select([sys.stdin], [], [], 0)
    if not ready:
        return None
    return sys.stdin.read(1)


def handle_key(game, key):
    """执行一个按键；返回是否需要重置自动下落计时。"""
    if key is None:
        return False
    key = key.lower()
    if key == "a":
        game.move_left()
    elif key == "d":
        game.move_right()
    elif key == "s":
        game.soft_drop()
        return True
    elif key == "w":
        game.rotate()
    elif key == "p":
        game.toggle_pause()
        return game.state == game_logic.PLAYING
    elif key == "r":
        game.restart()
        return True
    return False


def _play(game):
    last_drop = time.monotonic()
    draw(game)
    while True:
        key = read_key()
        if key is not None and key.lower() == "q":
            return
        too_small = not fits_terminal(terminal_size())
        restored = game.too_small and not too_small
        game.set_terminal_too_small(too_small)
        if restored:
            last_drop = time.monotonic()  # 恢复后从此刻重新计时（spec 5.4）
        if not too_small and handle_key(game, key):
            last_drop = time.monotonic()
        now = time.monotonic()
        if (
            not too_small
            and game.state == game_logic.PLAYING
            and now - last_drop >= DROP_INTERVAL
        ):
            game.step()
            last_drop = now
        draw(game)
        time.sleep(POLL_INTERVAL)


def _wait_for_quit():
    sys.stdout.write(STARTUP_HINT + "\n" + QUIT_HINT + "\n")
    sys.stdout.flush()
    while True:
        key = read_key()
        if key is not None and key.lower() == "q":
            return
        time.sleep(POLL_INTERVAL)


def main():
    configure_output()
    setup_terminal()
    try:
        if not fits_terminal(terminal_size()):
            _wait_for_quit()
        else:
            _play(game_logic.Game())
    except KeyboardInterrupt:
        pass  # finally 会恢复终端并清屏
    finally:
        restore_terminal()
        sys.stdout.write(CLEAR_SCREEN)
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
