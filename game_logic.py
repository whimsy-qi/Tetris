"""终端俄罗斯方块：纯逻辑（棋盘、方块、碰撞、旋转、消行、计分）。

本模块不读按键、不画屏幕、不 sleep；界面与循环见 tetris.py。
"""

import random

ROWS = 20
COLS = 10

# 每消除一行加 100 分（spec 6.6 / R3）。
LINE_SCORE = 100

PLAYING = "Playing"
PAUSED = "Paused"
GAME_OVER = "Game Over"

# 游戏模式，见 spec 6.9：单人一块棋盘，双人两块。
MODE_SINGLE = "single"
MODE_VERSUS = "versus"

# 七种方块的初始方阵，见 spec 6.2（`.` 空、`X` 实心）。
SHAPES = {
    "I": ("....", "XXXX", "....", "...."),
    "O": ("XX", "XX"),
    "T": ("XXX", ".X.", "..."),
    "S": (".XX", "XX.", "..."),
    "Z": ("XX.", ".XX", "..."),
    "J": ("X..", "XXX", "..."),
    "L": ("..X", "XXX", "..."),
}

# 旋转中心格（方阵坐标），见 spec 6.2；O 为 2×2 对称，无中心。
ROTATION_CENTERS = {
    "I": (1, 1),
    "O": None,
    "T": (1, 1),
    "S": (1, 1),
    "Z": (1, 1),
    "J": (1, 1),
    "L": (1, 1),
}


def create_board():
    """返回 20 行 × 10 列、全 0 的棋盘。"""
    return [[0] * COLS for _ in range(ROWS)]


def new_piece(name=None):
    """生成方块，返回 {"name", "cells", "center"}，见 spec 6.2/6.3。"""
    if name is None:
        # spec 6.1 / R4：七种方块独立等概率，不做 7 袋。
        name = random.choice(list(SHAPES))
    shape = SHAPES[name]
    start_col = (COLS - len(shape[0])) // 2
    cells = tuple(
        (row, start_col + col)
        for row, line in enumerate(shape)
        for col, char in enumerate(line)
        if char == "X"
    )
    center = ROTATION_CENTERS[name]
    if center is not None:
        center = (center[0], start_col + center[1])
    return {"name": name, "cells": cells, "center": center}


def can_place(board, cells):
    """所有格都在界内且落在空格上。"""
    for row, col in cells:
        if not (0 <= row < ROWS and 0 <= col < COLS):
            return False
        if board[row][col]:
            return False
    return True


def _shift_center(center, drow, dcol):
    if center is None:
        return None
    return (center[0] + drow, center[1] + dcol)


def try_move(board, piece, drow, dcol):
    """平移一格；能放返回新方块，否则返回 None（原方块不变）。"""
    cells = tuple((row + drow, col + dcol) for row, col in piece["cells"])
    if not can_place(board, cells):
        return None
    return {
        "name": piece["name"],
        "cells": cells,
        "center": _shift_center(piece["center"], drow, dcol),
    }


def rotate_cw(piece):
    """绕中心格顺时针旋转 90°，见 spec 6.4；O 为空操作。"""
    center = piece["center"]
    if center is None:
        return {"name": piece["name"], "cells": piece["cells"], "center": None}
    center_row, center_col = center
    # 约定 R2：(Δ行, Δ列) → (Δ列, −Δ行)，中心格位置不变。
    cells = tuple(
        (center_row + (col - center_col), center_col - (row - center_row))
        for row, col in piece["cells"]
    )
    return {"name": piece["name"], "cells": cells, "center": center}


def lock_piece(board, cells):
    """把方块格固定进棋盘。"""
    for row, col in cells:
        board[row][col] = 1


def clear_lines(board):
    """返回 (新棋盘, 消除行数)，不修改传入的棋盘，见附录 A。"""
    remaining = [row for row in board if not all(cell == 1 for cell in row)]
    cleared = len(board) - len(remaining)
    # 顶部补入空行，棋盘恒为 20 行 × 10 列（spec 6.6）。
    new_board = [[0] * COLS for _ in range(cleared)]
    new_board.extend(list(row) for row in remaining)
    return new_board, cleared


class Game:
    """一局游戏的状态机：棋盘、分数、状态、当前方块。"""

    def __init__(self):
        self.board = create_board()
        self.score = 0
        self.state = PLAYING
        self.piece = None
        self.too_small = False
        self.manual_paused = False
        self._spawn()

    def _spawn(self):
        piece = new_piece()
        if not can_place(self.board, piece["cells"]):
            # spec 6.7 / FR-8：出生位置放不下就结束。
            self.piece = None
            self.state = GAME_OVER
            return
        self.piece = piece

    def _controllable(self):
        return self.state == PLAYING and self.piece is not None

    def move_left(self):
        return self._shift(0, -1)

    def move_right(self):
        return self._shift(0, 1)

    def _shift(self, drow, dcol):
        if not self._controllable():
            return False
        moved = try_move(self.board, self.piece, drow, dcol)
        if moved is None:
            return False
        self.piece = moved
        return True

    def rotate(self):
        """W 键：绕中心顺时针旋转；越界或重叠则整次取消，见 FR-5。"""
        if not self._controllable():
            return False
        rotated = rotate_cw(self.piece)
        if not can_place(self.board, rotated["cells"]):
            return False
        self.piece = rotated
        return True

    def soft_drop(self):
        """S 键：立即下移 1 行；已不能下移则固定，见 spec 6.5/FR-4。"""
        return self._fall()

    def step(self):
        """自动下落一次：能下则下，不能下则固定，见 spec 6.5/FR-2。"""
        return self._fall()

    def _fall(self):
        if not self._controllable():
            return False
        moved = try_move(self.board, self.piece, 1, 0)
        if moved is None:
            self._lock_and_clear()
            return False
        self.piece = moved
        return True

    def _lock_and_clear(self):
        lock_piece(self.board, self.piece["cells"])
        self.piece = None
        self.board, cleared = clear_lines(self.board)
        self.score += cleared * LINE_SCORE
        self._spawn()

    def toggle_pause(self):
        """P 键：Playing ↔ Paused；终端过小时按键不处理，见 spec 5.4/FR-11。"""
        if self.too_small:
            return False
        if self.state == PLAYING:
            self.state = PAUSED
            self.manual_paused = True
            return True
        if self.state == PAUSED:
            self.state = PLAYING
            self.manual_paused = False
            return True
        return False

    def set_terminal_too_small(self, too_small):
        """缩小→Paused、恢复→Playing；手动暂停的 Paused 要一直保持，见 FR-9/5.4。"""
        if too_small == self.too_small:
            return
        self.too_small = too_small
        if too_small:
            if self.state == PLAYING:
                self.state = PAUSED
        elif self.state == PAUSED and not self.manual_paused:
            self.state = PLAYING

    def restart(self):
        """R 键：任意状态都可重开，见 FR-12。"""
        self.board = create_board()
        self.score = 0
        self.state = PLAYING
        self.piece = None
        self.manual_paused = False
        self._spawn()

class Match:
    """一盘对局：单人 1 块棋盘、双人 2 块，管模式切换、暂停与胜负（spec 6.8/6.9）。"""

    def __init__(self, mode=MODE_SINGLE):
        self.mode = mode
        self.games = self._new_games(mode)
        self.too_small = False

    @staticmethod
    def _new_games(mode):
        count = 1 if mode == MODE_SINGLE else 2
        return [Game() for _ in range(count)]

    def over(self):
        """任一方顶死即整局结束；单人就是普通 Game Over。"""
        return any(game.state == GAME_OVER for game in self.games)

    @property
    def state(self):
        if self.over():
            return GAME_OVER
        if all(game.state == PAUSED for game in self.games):
            return PAUSED
        return PLAYING

    def result(self):
        """结束后返回 'Game Over' / 'P1 wins' / 'P2 wins' / 'Draw'，未结束为空串。"""
        if not self.over():
            return ""
        if len(self.games) == 1:
            return GAME_OVER
        dead = [game.state == GAME_OVER for game in self.games]
        if all(dead):
            return "Draw"
        return "P2 wins" if dead[0] else "P1 wins"

    def toggle_pause(self):
        """P 键：双人时同时暂停/继续；结束后或终端过小时不处理（spec 6.7/5.5）。"""
        if self.over() or self.too_small:
            return False
        for game in self.games:
            game.toggle_pause()
        return True

    def restart(self):
        """R 键：保持当前模式重开（spec FR-12）。"""
        self.games = self._new_games(self.mode)

    def switch_mode(self):
        """M 键：切到另一模式并重开（spec FR-14）。"""
        self.mode = MODE_VERSUS if self.mode == MODE_SINGLE else MODE_SINGLE
        self.games = self._new_games(self.mode)
        self.too_small = False
        return self.mode

    def set_terminal_too_small(self, too_small):
        """把终端尺寸状态分发给每块棋盘，沿用 v1 的暂停/恢复语义。"""
        self.too_small = too_small
        for game in self.games:
            game.set_terminal_too_small(too_small)
