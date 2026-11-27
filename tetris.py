"""终端俄罗斯方块：界面、按键读取与游戏循环（入口）。

逻辑全部在 game_logic.py；本模块只负责显示、输入与定时。
"""

import os
import shutil
import sys
import time

import game_logic

# 各模式所需的最小终端尺寸，见 spec 5.3。
MIN_SIZE = {
    game_logic.MODE_SINGLE: (40, 28),
    game_logic.MODE_VERSUS: (46, 26),
}

CELL = "[]"
EMPTY = "  "
BOARD_WIDTH = game_logic.COLS * len(CELL) + 2
INFO_GAP = "  "
BOARD_GAP = "  "

POLL_INTERVAL = 0.05

KEY_HELP = ("A/D move", "S down", "W rotate", "P pause", "R restart", "M mode", "Q quit")
VERSUS_HELP = ("P1 A/D/S/W   P2 arrows   P pause   M mode", "R restart   Q quit")
MENU_LINES = (
    "终端俄罗斯方块 · v2",
    "",
    "1  单人模式",
    "2  双人模式",
    "",
    "Q  退出",
)

TOO_SMALL_HINT = "终端太小：需要至少 {cols} 列 × {rows} 行"
STARTUP_HINT = "请将终端调整为至少 {cols} 列 × {rows} 行后重新运行"
QUIT_HINT = "按 Q 退出"

CLEAR_SCREEN = "\x1b[2J\x1b[H"

# 方向键：Windows 用扫描码，POSIX 用 ESC [ 序列（spec 5.4）。
WINDOWS_ARROWS = {72: "up", 80: "down", 75: "left", 77: "right"}
POSIX_ARROWS = {"[A": "up", "[B": "down", "[C": "right", "[D": "left"}

_saved_posix_attrs = None


def terminal_size():
    size = shutil.get_terminal_size()
    return size.columns, size.lines


def fits_terminal(mode):
    cols, rows = terminal_size()
    need_cols, need_rows = MIN_SIZE[mode]
    return cols >= need_cols and rows >= need_rows


def render_board(board, piece_cells=()):
    """22 行、每行 22 字符（含 1 字符边框），见 spec 5.3。"""
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


def _too_small_line(mode):
    cols, rows = MIN_SIZE[mode]
    return TOO_SMALL_HINT.format(cols=cols, rows=rows)


def render_single(match):
    """单人：棋盘在左、信息区在右（沿用 v1 布局，spec 5.1）。"""
    game = match.games[0]
    board_lines = render_board(game.board, game.piece["cells"] if game.piece else ())
    info = [
        "",
        "Score: {}".format(game.score),
        "State: {}".format(game.state),
        "Combo: {}".format(game.combo),
        "Level: {}".format(game.level),
        "",
    ]
    info += list(KEY_HELP)
    lines = []
    for index, board_line in enumerate(board_lines):
        extra = info[index] if index < len(info) else ""
        lines.append((board_line + INFO_GAP + extra).rstrip())
    if match.too_small:
        lines.append(_too_small_line(match.mode))
    return lines


def status_line(match):
    """双人状态提示放在棋盘下方那一行，避免额外占用行数（spec 5.2）。"""
    if match.state == game_logic.GAME_OVER:
        return "Game Over - " + match.result()
    if match.state == game_logic.PAUSED:
        return "Paused - press P"
    return ""


def render_versus(match):
    """双人：两块 22 列棋盘并排，顶部信息、底部提示，共 26 行（spec 5.2）。"""
    left, right = match.games
    left_board = render_board(left.board, left.piece["cells"] if left.piece else ())
    right_board = render_board(right.board, right.piece["cells"] if right.piece else ())
    # 分数可能上到 6 位数，抬头用紧凑写法，保证整行仍 ≤46 列（spec 5.3）。
    header = "P1 {} L{} C{}".format(left.score, left.level, left.combo).ljust(BOARD_WIDTH)
    header += BOARD_GAP + "P2 {} L{} C{}".format(right.score, right.level, right.combo)
    lines = [header.rstrip()]
    for index in range(len(left_board)):
        lines.append(left_board[index] + BOARD_GAP + right_board[index])
    lines.append(status_line(match))
    lines.extend(VERSUS_HELP)
    if match.too_small:
        lines.append(_too_small_line(match.mode))
    return [line.rstrip() for line in lines]


def render(match):
    if match.mode == game_logic.MODE_VERSUS:
        return render_versus(match)
    return render_single(match)


def draw(match):
    """回到左上角逐行覆盖并擦到行尾，避免整屏闪烁。"""
    lines = render(match)
    sys.stdout.write("\x1b[H" + "\n".join(line + "\x1b[K" for line in lines) + "\x1b[J")
    sys.stdout.flush()


def draw_lines(lines):
    sys.stdout.write(CLEAR_SCREEN + "\n".join(lines))
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


def _read_escape_tail(msvcrt):
    """读取 ESC 之后的 2 个字符（形如 '[A'），用于兼容把方向键送成 VT 序列的终端。"""
    seq = ""
    deadline = time.monotonic() + 0.02
    while len(seq) < 2 and time.monotonic() < deadline:
        if msvcrt.kbhit():
            seq += msvcrt.getwch()
        else:
            time.sleep(0.002)
    return seq


def read_key():
    """非阻塞读一个键；返回单字符或 'up'/'down'/'left'/'right'，没按键返回 None。"""
    if os.name == "nt":
        import msvcrt

        if not msvcrt.kbhit():
            return None
        char = msvcrt.getwch()
        if char in ("\x00", "\xe0"):
            # 常规控制台：前缀 0xE0/0x00 + 扫描码。
            code = msvcrt.getwch()
            return WINDOWS_ARROWS.get(ord(code))
        if char == "\x1b":
            # VT 输入模式的终端（部分 Windows Terminal / ConPTY 配置）：ESC [ A 这样的序列。
            return POSIX_ARROWS.get(_read_escape_tail(msvcrt))
        return char
    import select

    ready, _, _ = select.select([sys.stdin], [], [], 0)
    if not ready:
        return None
    char = sys.stdin.read(1)
    if char != "\x1b":
        return char
    # 方向键是 ESC + '[' + 字母；ESC 单独按下时读不到后续字符，返回 None 忽略。
    seq = ""
    while len(seq) < 2:
        ready, _, _ = select.select([sys.stdin], [], [], 0.02)
        if not ready:
            break
        seq += sys.stdin.read(1)
    return POSIX_ARROWS.get(seq)


def handle_key(match, key):
    """执行一个按键；返回要重置下落的玩家编号，'all' 表示全部，None 表示不需要。"""
    if not key:
        return None
    key = key.lower()
    if key == "p":
        match.toggle_pause()
        return "all"
    if key == "r":
        match.restart()
        return "all"
    if key == "m":
        match.switch_mode()
        return "all"
    if key in ("a", "d", "s", "w"):
        player, action = 0, key
    elif key in ("up", "down", "left", "right") and match.mode == game_logic.MODE_VERSUS:
        player, action = 1, {"left": "a", "right": "d", "down": "s", "up": "w"}[key]
    else:
        return None
    game = match.games[player]
    if action == "a":
        game.move_left()
    elif action == "d":
        game.move_right()
    elif action == "s":
        game.soft_drop()
        return player
    elif action == "w":
        game.rotate()
    return None


def _play(match):
    """主循环：按键 → 定时下落 → 重画；每块棋盘各自计时，便于将来独立调速。"""
    timers = [time.monotonic() for _ in match.games]
    draw(match)
    while True:
        key = read_key()
        if key and key.lower() == "q":
            return
        size_ok = fits_terminal(match.mode)
        restored = match.too_small and size_ok
        match.set_terminal_too_small(not size_ok)
        if restored:
            timers = [time.monotonic() for _ in match.games]
        if size_ok:
            target = handle_key(match, key)
            now = time.monotonic()
            if target == "all":
                timers = [now for _ in match.games]
            elif isinstance(target, int):
                timers[target] = now
        if size_ok and match.state == game_logic.PLAYING:
            now = time.monotonic()
            for index, game in enumerate(match.games):
                if now - timers[index] >= game.drop_interval:
                    game.step()
                    timers[index] = now
        draw(match)
        time.sleep(POLL_INTERVAL)


def _choose_mode():
    """启动菜单：1 单人、2 双人、Q 退出（spec FR-13）。"""
    draw_lines(MENU_LINES)
    while True:
        key = read_key()
        if key:
            key = key.lower()
            if key == "1":
                return game_logic.MODE_SINGLE
            if key == "2":
                return game_logic.MODE_VERSUS
            if key == "q":
                return None
        time.sleep(POLL_INTERVAL)


def _wait_for_quit(mode):
    cols, rows = MIN_SIZE[mode]
    draw_lines(
        [
            STARTUP_HINT.format(cols=cols, rows=rows),
            QUIT_HINT,
        ]
    )
    while True:
        key = read_key()
        if key and key.lower() == "q":
            return
        time.sleep(POLL_INTERVAL)


def main():
    configure_output()
    setup_terminal()
    try:
        mode = _choose_mode()
        if mode is None:
            return 0
        match = game_logic.Match(mode)
        if not fits_terminal(mode):
            _wait_for_quit(mode)
        else:
            _play(match)
    except KeyboardInterrupt:
        pass  # finally 会恢复终端并清屏
    finally:
        restore_terminal()
        sys.stdout.write(CLEAR_SCREEN)
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
