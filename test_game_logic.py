"""game_logic.py 的逻辑测试；不启动终端界面。"""

import unittest
from unittest import mock

import game_logic
from game_logic import COLS, ROWS, create_board


def make_game(piece="O"):
    """固定随机结果，让出生方块确定。"""
    with mock.patch("game_logic.random.choice", return_value=piece):
        return game_logic.Game()


class BoardTest(unittest.TestCase):
    def test_new_board_is_20_rows_by_10_columns(self):
        board = create_board()
        self.assertEqual(len(board), ROWS)
        self.assertEqual(ROWS, 20)
        for row in board:
            self.assertEqual(len(row), COLS)
            self.assertEqual(COLS, 10)
        self.assertEqual(sum(cell for row in board for cell in row), 0)


class PieceTest(unittest.TestCase):
    # 由 spec 6.2 初始朝向 + 6.3 出生位置推出（实施前已与你核对）。
    EXPECTED_CELLS = {
        "I": {(1, 3), (1, 4), (1, 5), (1, 6)},
        "O": {(0, 4), (0, 5), (1, 4), (1, 5)},
        "T": {(0, 3), (0, 4), (0, 5), (1, 4)},
        "S": {(0, 4), (0, 5), (1, 3), (1, 4)},
        "Z": {(0, 3), (0, 4), (1, 4), (1, 5)},
        "J": {(0, 3), (1, 3), (1, 4), (1, 5)},
        "L": {(0, 5), (1, 3), (1, 4), (1, 5)},
    }

    def test_initial_cells_of_each_piece(self):
        for name, expected in self.EXPECTED_CELLS.items():
            with self.subTest(name=name):
                piece = game_logic.new_piece(name)
                self.assertEqual(piece["name"], name)
                self.assertEqual(set(piece["cells"]), expected)

    def test_rotation_centers(self):
        for name in ("I", "T", "S", "Z", "J", "L"):
            with self.subTest(name=name):
                self.assertEqual(game_logic.new_piece(name)["center"], (1, 4))
        self.assertIsNone(game_logic.new_piece("O")["center"])

    def test_new_piece_uses_random_choice_when_name_omitted(self):
        with mock.patch("game_logic.random.choice", return_value="T"):
            piece = game_logic.new_piece()
        self.assertEqual(piece["name"], "T")


class MoveTest(unittest.TestCase):
    def test_move_left_and_right_by_one_column(self):
        game = make_game("O")
        start = set(game.piece["cells"])
        self.assertTrue(game.move_left())
        self.assertEqual(set(game.piece["cells"]), {(row, col - 1) for row, col in start})
        self.assertTrue(game.move_right())
        self.assertEqual(set(game.piece["cells"]), start)

    def test_move_is_rejected_at_left_wall(self):
        game = make_game("O")
        for _ in range(4):
            self.assertTrue(game.move_left())
        before = set(game.piece["cells"])
        self.assertEqual(min(col for _, col in before), 0)
        self.assertFalse(game.move_left())
        self.assertEqual(set(game.piece["cells"]), before)

    def test_move_is_rejected_at_right_wall(self):
        game = make_game("O")
        for _ in range(4):
            self.assertTrue(game.move_right())
        before = set(game.piece["cells"])
        self.assertEqual(max(col for _, col in before), 9)
        self.assertFalse(game.move_right())
        self.assertEqual(set(game.piece["cells"]), before)

    def test_move_is_rejected_when_target_cell_is_fixed(self):
        game = make_game("O")
        game.board[1][3] = 1
        before = set(game.piece["cells"])
        self.assertFalse(game.move_left())
        self.assertEqual(set(game.piece["cells"]), before)


class FallTest(unittest.TestCase):
    def test_soft_drop_moves_down_one_row(self):
        game = make_game("O")
        before = set(game.piece["cells"])
        self.assertTrue(game.soft_drop())
        self.assertEqual(set(game.piece["cells"]), {(row + 1, col) for row, col in before})

    def test_step_moves_down_one_row(self):
        game = make_game("O")
        before = set(game.piece["cells"])
        self.assertTrue(game.step())
        self.assertEqual(set(game.piece["cells"]), {(row + 1, col) for row, col in before})


class LockTest(unittest.TestCase):
    def test_step_locks_piece_into_board_when_it_cannot_fall(self):
        game = make_game("O")
        while game.step():
            pass
        self.assertEqual(game.board[18][4], 1)
        self.assertEqual(game.board[18][5], 1)
        self.assertEqual(game.board[19][4], 1)
        self.assertEqual(game.board[19][5], 1)

    def test_new_piece_spawns_after_lock_and_score_is_unchanged(self):
        with mock.patch("game_logic.random.choice", return_value="O"):
            game = game_logic.Game()
            while game.step():
                pass
            self.assertIsNotNone(game.piece)
            self.assertEqual(set(game.piece["cells"]), PieceTest.EXPECTED_CELLS["O"])
            self.assertEqual(game.score, 0)
            self.assertEqual(game.state, game_logic.PLAYING)

    def _make_game_over(self):
        game = make_game("O")
        game.board[2][4] = 1
        game.board[2][5] = 1
        game.step()
        return game

    def test_game_over_when_spawn_is_blocked(self):
        game = self._make_game_over()
        self.assertEqual(game.state, game_logic.GAME_OVER)
        self.assertIsNone(game.piece)

    def test_controls_are_ignored_after_game_over(self):
        game = self._make_game_over()
        snapshot = [row[:] for row in game.board]
        self.assertFalse(game.move_left())
        self.assertFalse(game.move_right())
        self.assertFalse(game.soft_drop())
        self.assertFalse(game.step())
        self.assertEqual(game.board, snapshot)


class RotateTest(unittest.TestCase):
    def test_rotate_t_clockwise_around_center(self):
        game = make_game("T")
        center = game.piece["center"]
        self.assertEqual(center, (1, 4))
        self.assertTrue(game.rotate())
        self.assertEqual(set(game.piece["cells"]), {(0, 5), (1, 4), (1, 5), (2, 5)})
        self.assertEqual(game.piece["center"], center)

    def test_rotate_i_clockwise_around_center(self):
        game = make_game("I")
        self.assertTrue(game.rotate())
        self.assertEqual(set(game.piece["cells"]), {(0, 4), (1, 4), (2, 4), (3, 4)})

    def test_rotate_o_is_a_no_op(self):
        game = make_game("O")
        before = set(game.piece["cells"])
        game.rotate()
        self.assertEqual(set(game.piece["cells"]), before)

    def test_rotate_is_cancelled_at_the_left_wall(self):
        game = make_game("T")
        self.assertTrue(game.rotate())  # 先转成竖着的 T
        for _ in range(4):
            self.assertTrue(game.move_left())  # 贴左墙
        before = set(game.piece["cells"])
        self.assertFalse(game.rotate())
        self.assertEqual(set(game.piece["cells"]), before)

    def test_rotate_is_cancelled_by_fixed_cells(self):
        game = make_game("T")
        game.board[2][5] = 1  # 旋转后需要占用的格
        before = set(game.piece["cells"])
        self.assertFalse(game.rotate())
        self.assertEqual(set(game.piece["cells"]), before)

    def test_four_clockwise_rotations_restore_cells(self):
        game = make_game("T")
        before = set(game.piece["cells"])
        for _ in range(4):
            self.assertTrue(game.rotate())
        self.assertEqual(set(game.piece["cells"]), before)

    def test_rotate_is_ignored_after_game_over(self):
        game = make_game("O")
        game.board[2][4] = 1
        game.board[2][5] = 1
        game.step()
        self.assertEqual(game.state, game_logic.GAME_OVER)
        before = [row[:] for row in game.board]
        self.assertFalse(game.rotate())
        self.assertEqual(game.board, before)


def empty_board():
    return [[0] * COLS for _ in range(ROWS)]


def force_clear(game, lines=1):
    """把棋盘铺成只差两格的 n 行，让 O 方块落到底补满并消行（连击测试用）。"""
    game.board = empty_board()
    for row in range(ROWS - lines, ROWS):
        for col in (0, 1, 2, 3, 6, 7, 8, 9):
            game.board[row][col] = 1
    game.piece = game_logic.new_piece("O")
    while game.step():
        pass


class ClearLinesTest(unittest.TestCase):
    def test_sample_a_single_full_bottom_row_is_cleared(self):
        board = empty_board()
        board[19] = [1] * COLS
        new_board, cleared = game_logic.clear_lines(board)
        self.assertEqual(cleared, 1)
        self.assertEqual(len(new_board), ROWS)
        self.assertTrue(all(cell == 0 for row in new_board for cell in row))

    def test_sample_b_two_full_rows_are_cleared(self):
        board = empty_board()
        board[18] = [1] * COLS
        board[19] = [1] * COLS
        new_board, cleared = game_logic.clear_lines(board)
        self.assertEqual(cleared, 2)
        self.assertEqual((len(new_board), len(new_board[0])), (20, 10))
        self.assertTrue(all(cell == 0 for row in new_board for cell in row))

    def test_sample_c_row_with_a_gap_is_not_cleared(self):
        board = empty_board()
        board[19] = [1] * COLS
        board[19][4] = 0
        new_board, cleared = game_logic.clear_lines(board)
        self.assertEqual(cleared, 0)
        self.assertEqual(new_board, board)

    def test_sample_d_rows_above_shift_down(self):
        board = empty_board()
        board[19] = [1] * COLS
        board[18][0] = 1
        new_board, cleared = game_logic.clear_lines(board)
        self.assertEqual(cleared, 1)
        self.assertEqual(new_board[19][0], 1)
        self.assertEqual(sum(new_board[19]), 1)
        self.assertTrue(all(cell == 0 for cell in new_board[18]))

    def test_clear_lines_does_not_modify_the_input_board(self):
        board = empty_board()
        board[19] = [1] * COLS
        snapshot = [row[:] for row in board]
        game_logic.clear_lines(board)
        self.assertEqual(board, snapshot)

    def test_clear_lines_keeps_board_at_20_by_10(self):
        board = empty_board()
        for row in range(15, 20):
            board[row] = [1] * COLS
        new_board, cleared = game_logic.clear_lines(board)
        self.assertEqual(cleared, 5)
        self.assertEqual(len(new_board), 20)
        self.assertTrue(all(len(row) == 10 for row in new_board))


class ScoreTest(unittest.TestCase):
    def test_single_line_adds_100_points(self):
        game = make_game("O")
        for col in (0, 1, 2, 3, 6, 7, 8, 9):
            game.board[19][col] = 1
        while game.step():
            pass
        self.assertEqual(game.score, 100)
        self.assertEqual(game.board[19][4], 1)  # 上方残留格下移到底行
        self.assertTrue(all(cell == 0 for cell in game.board[18]))

    def test_sample_f_100_plus_two_lines_is_300(self):
        game = make_game("O")
        game.score = 100
        for col in (0, 1, 2, 3, 6, 7, 8, 9):
            game.board[18][col] = 1
            game.board[19][col] = 1
        while game.step():
            pass
        self.assertEqual(game.score, 300)
        self.assertTrue(all(cell == 0 for row in game.board for cell in row))


class PauseTest(unittest.TestCase):
    def test_pause_blocks_controls(self):
        game = make_game("O")
        self.assertTrue(game.toggle_pause())
        self.assertEqual(game.state, game_logic.PAUSED)
        snapshot = [row[:] for row in game.board]
        cells = set(game.piece["cells"])
        self.assertFalse(game.move_left())
        self.assertFalse(game.move_right())
        self.assertFalse(game.soft_drop())
        self.assertFalse(game.rotate())
        self.assertFalse(game.step())
        self.assertEqual(game.board, snapshot)
        self.assertEqual(set(game.piece["cells"]), cells)

    def test_resume_returns_to_playing(self):
        game = make_game("O")
        game.toggle_pause()
        self.assertTrue(game.toggle_pause())
        self.assertEqual(game.state, game_logic.PLAYING)
        before = set(game.piece["cells"])
        self.assertTrue(game.step())
        self.assertEqual(set(game.piece["cells"]), {(row + 1, col) for row, col in before})


class TerminalSizeTest(unittest.TestCase):
    def test_shrink_pauses_and_restore_resumes(self):
        game = make_game("O")
        game.set_terminal_too_small(True)
        self.assertEqual(game.state, game_logic.PAUSED)
        snapshot = [row[:] for row in game.board]
        self.assertFalse(game.step())
        self.assertEqual(game.board, snapshot)
        game.set_terminal_too_small(False)
        self.assertEqual(game.state, game_logic.PLAYING)

    def test_manual_pause_survives_resize(self):
        game = make_game("O")
        self.assertTrue(game.toggle_pause())
        game.set_terminal_too_small(True)
        game.set_terminal_too_small(False)
        self.assertEqual(game.state, game_logic.PAUSED)
        self.assertTrue(game.toggle_pause())
        self.assertEqual(game.state, game_logic.PLAYING)

    def test_pause_key_is_ignored_while_terminal_is_too_small(self):
        game = make_game("O")
        game.set_terminal_too_small(True)
        self.assertFalse(game.toggle_pause())
        self.assertEqual(game.state, game_logic.PAUSED)


class RestartTest(unittest.TestCase):
    def test_restart_from_playing_clears_board_and_score(self):
        game = make_game("O")
        game.score = 500
        game.board[19] = [1] * COLS
        game.restart()
        self.assertEqual(game.state, game_logic.PLAYING)
        self.assertEqual(game.score, 0)
        self.assertTrue(all(cell == 0 for row in game.board for cell in row))
        self.assertIsNotNone(game.piece)

    def test_restart_from_paused(self):
        game = make_game("O")
        self.assertTrue(game.toggle_pause())
        game.restart()
        self.assertEqual(game.state, game_logic.PLAYING)
        self.assertIsNotNone(game.piece)

    def test_restart_from_game_over(self):
        game = make_game("O")
        game.board[2][4] = 1
        game.board[2][5] = 1
        game.step()
        self.assertEqual(game.state, game_logic.GAME_OVER)
        game.restart()
        self.assertEqual(game.state, game_logic.PLAYING)
        self.assertEqual(game.score, 0)
        self.assertIsNotNone(game.piece)
        self.assertTrue(all(cell == 0 for row in game.board for cell in row))


class MatchTest(unittest.TestCase):
    """双人模式、模式切换与胜负判定（spec 6.8/6.9、FR-13~FR-16）。"""

    def make_match(self, mode):
        with mock.patch("game_logic.random.choice", return_value="O"):
            return game_logic.Match(mode)

    def test_single_mode_has_one_board(self):
        match = self.make_match(game_logic.MODE_SINGLE)
        self.assertEqual(len(match.games), 1)
        self.assertEqual(match.state, game_logic.PLAYING)

    def test_versus_mode_has_two_independent_boards(self):
        match = self.make_match(game_logic.MODE_VERSUS)
        self.assertEqual(len(match.games), 2)
        left, right = match.games
        right_before = set(right.piece["cells"])
        self.assertTrue(left.move_left())
        self.assertEqual(set(right.piece["cells"]), right_before)
        self.assertNotEqual(set(left.piece["cells"]), right_before)

    def test_switch_mode_rebuilds_boards_and_clears_score(self):
        match = self.make_match(game_logic.MODE_SINGLE)
        match.games[0].score = 300
        self.assertEqual(match.switch_mode(), game_logic.MODE_VERSUS)
        self.assertEqual(len(match.games), 2)
        self.assertEqual([game.score for game in match.games], [0, 0])
        self.assertEqual(match.switch_mode(), game_logic.MODE_SINGLE)
        self.assertEqual(len(match.games), 1)

    def test_restart_keeps_mode(self):
        match = self.make_match(game_logic.MODE_VERSUS)
        match.games[0].score = 100
        match.restart()
        self.assertEqual(match.mode, game_logic.MODE_VERSUS)
        self.assertEqual(len(match.games), 2)
        self.assertEqual(match.games[0].score, 0)

    def test_first_player_dead_makes_second_the_winner(self):
        match = self.make_match(game_logic.MODE_VERSUS)
        match.games[0].state = game_logic.GAME_OVER
        self.assertTrue(match.over())
        self.assertEqual(match.state, game_logic.GAME_OVER)
        self.assertEqual(match.result(), "P2 wins")

    def test_second_player_dead_makes_first_the_winner(self):
        match = self.make_match(game_logic.MODE_VERSUS)
        match.games[1].state = game_logic.GAME_OVER
        self.assertEqual(match.result(), "P1 wins")

    def test_both_dead_is_draw(self):
        match = self.make_match(game_logic.MODE_VERSUS)
        for game in match.games:
            game.state = game_logic.GAME_OVER
        self.assertEqual(match.result(), "Draw")

    def test_single_mode_result_is_plain_game_over(self):
        match = self.make_match(game_logic.MODE_SINGLE)
        match.games[0].state = game_logic.GAME_OVER
        self.assertEqual(match.result(), game_logic.GAME_OVER)

    def test_pause_pauses_both_boards_and_resumes(self):
        match = self.make_match(game_logic.MODE_VERSUS)
        self.assertTrue(match.toggle_pause())
        self.assertEqual(
            [game.state for game in match.games],
            [game_logic.PAUSED, game_logic.PAUSED],
        )
        self.assertEqual(match.state, game_logic.PAUSED)
        for game in match.games:
            self.assertFalse(game.step())
        self.assertTrue(match.toggle_pause())
        self.assertEqual(match.state, game_logic.PLAYING)

    def test_pause_is_ignored_after_game_over(self):
        match = self.make_match(game_logic.MODE_VERSUS)
        match.games[0].state = game_logic.GAME_OVER
        self.assertFalse(match.toggle_pause())
        self.assertEqual(match.games[1].state, game_logic.PLAYING)

    def test_terminal_too_small_pauses_both_and_restores(self):
        match = self.make_match(game_logic.MODE_VERSUS)
        match.set_terminal_too_small(True)
        self.assertEqual(match.state, game_logic.PAUSED)
        match.set_terminal_too_small(False)
        self.assertEqual(match.state, game_logic.PLAYING)


class ComboTest(unittest.TestCase):
    """连击计分：第 2 次及以后翻倍、中断清零、不叠乘（spec 6.6 / FR-17）。"""

    def test_first_clear_scores_one_hundred_without_bonus(self):
        game = make_game("O")
        force_clear(game, 1)
        self.assertEqual(game.combo, 1)
        self.assertEqual(game.score, 100)

    def test_second_consecutive_clear_is_doubled(self):
        game = make_game("O")
        force_clear(game, 1)
        force_clear(game, 1)
        self.assertEqual(game.combo, 2)
        self.assertEqual(game.score, 300)

    def test_third_clear_is_still_doubled_not_quadrupled(self):
        game = make_game("O")
        for _ in range(3):
            force_clear(game, 1)
        self.assertEqual(game.combo, 3)
        self.assertEqual(game.score, 500)

    def test_clear_without_clearing_a_line_resets_combo(self):
        game = make_game("O")
        force_clear(game, 1)
        # 空棋盘上固定一块、没有消行 → 连击清零，分数不变
        game.board = empty_board()
        game.piece = game_logic.new_piece("O")
        while game.step():
            pass
        self.assertEqual(game.combo, 0)
        self.assertEqual(game.score, 100)
        # 之后第一次消行回到基础分
        force_clear(game, 1)
        self.assertEqual(game.combo, 1)
        self.assertEqual(game.score, 200)

    def test_two_line_clear_on_second_combo_scores_four_hundred(self):
        game = make_game("O")
        force_clear(game, 1)
        force_clear(game, 2)
        self.assertEqual(game.combo, 2)
        self.assertEqual(game.score, 500)

    def test_restart_resets_combo(self):
        game = make_game("O")
        force_clear(game, 1)
        game.restart()
        self.assertEqual(game.combo, 0)
        self.assertEqual(game.score, 0)


class SpeedTest(unittest.TestCase):
    """速度等级：每累计 10 行升一级、0.8 系数、0.1 秒下限（spec 6.5 / FR-18）。"""

    def test_new_game_starts_at_level_one_with_half_second(self):
        game = make_game("O")
        self.assertEqual(game.lines, 0)
        self.assertEqual(game.level, 1)
        self.assertAlmostEqual(game.drop_interval, 0.5)

    def test_nine_lines_stay_at_level_one(self):
        game = make_game("O")
        for _ in range(9):
            force_clear(game, 1)
        self.assertEqual(game.lines, 9)
        self.assertEqual(game.level, 1)
        self.assertAlmostEqual(game.drop_interval, 0.5)

    def test_ten_lines_upgrade_to_level_two(self):
        game = make_game("O")
        for _ in range(10):
            force_clear(game, 1)
        self.assertEqual(game.lines, 10)
        self.assertEqual(game.level, 2)
        self.assertAlmostEqual(game.drop_interval, 0.4)

    def test_twenty_lines_upgrade_to_level_three(self):
        game = make_game("O")
        for _ in range(10):
            force_clear(game, 2)
        self.assertEqual(game.lines, 20)
        self.assertEqual(game.level, 3)
        self.assertAlmostEqual(game.drop_interval, 0.32)

    def test_interval_never_goes_below_one_tenth_of_a_second(self):
        game = make_game("O")
        for _ in range(100):  # 每次消 2 行，累计 200 行
            force_clear(game, 2)
        self.assertEqual(game.lines, 200)
        self.assertGreater(game.level, 9)
        self.assertAlmostEqual(game.drop_interval, 0.1)

    def test_restart_resets_level_and_interval(self):
        game = make_game("O")
        for _ in range(10):
            force_clear(game, 1)
        game.restart()
        self.assertEqual(game.lines, 0)
        self.assertEqual(game.level, 1)
        self.assertAlmostEqual(game.drop_interval, 0.5)

    def test_each_player_keeps_its_own_level(self):
        with mock.patch("game_logic.random.choice", return_value="O"):
            match = game_logic.Match(game_logic.MODE_VERSUS)
        for _ in range(10):
            force_clear(match.games[0], 1)
        self.assertEqual(match.games[0].level, 2)
        self.assertEqual(match.games[1].level, 1)
        self.assertAlmostEqual(match.games[0].drop_interval, 0.4)
        self.assertAlmostEqual(match.games[1].drop_interval, 0.5)


if __name__ == "__main__":
    unittest.main()
