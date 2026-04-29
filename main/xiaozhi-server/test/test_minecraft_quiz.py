import random
import unittest

from core.handle.minecraft_quiz import MinecraftQuizGame


class MinecraftQuizGameTests(unittest.TestCase):
    def test_question_bank_has_expected_scale(self):
        game = MinecraftQuizGame(rng=random.Random(123))

        self.assertGreaterEqual(len(game.question_bank), 40)

    def test_generate_question_returns_scene_with_three_shuffled_options(self):
        game = MinecraftQuizGame(rng=random.Random(123))

        question_text, answer, timeout = game.generate_question(
            round_index=0,
            consecutive_correct=0,
            consecutive_wrong=0,
        )

        self.assertIn("A.", question_text)
        self.assertIn("B.", question_text)
        self.assertIn("C.", question_text)
        self.assertEqual(timeout, 15)
        self.assertEqual(set(answer["options"].keys()), {"A", "B", "C"})
        self.assertIn(answer["correct_option"], {"A", "B", "C"})
        self.assertTrue(answer["correct_text"])
        self.assertIn(answer["correct_text"], answer["options"].values())

    def test_check_answer_accepts_letter_ordinal_and_option_text(self):
        game = MinecraftQuizGame(rng=random.Random(123))
        _, answer, _ = game.generate_question(0, 0, 0)

        correct_option = answer["correct_option"]
        correct_text = answer["correct_text"]
        ordinal_map = {"A": "第一个", "B": "第二个", "C": "第三个"}
        wrong_option = next(opt for opt in ("A", "B", "C") if opt != correct_option)

        self.assertTrue(
            game.check_answer(game.normalize_input(correct_option.lower()), answer)
        )
        self.assertTrue(
            game.check_answer(game.normalize_input(ordinal_map[correct_option]), answer)
        )
        self.assertTrue(
            game.check_answer(game.normalize_input(correct_text), answer)
        )
        self.assertFalse(
            game.check_answer(game.normalize_input(wrong_option.lower()), answer)
        )

    def test_check_answer_accepts_prefixed_option_letter(self):
        game = MinecraftQuizGame(rng=random.Random(123))
        _, answer, _ = game.generate_question(0, 0, 0)

        user_text = f"我选 {answer['correct_option']}"

        self.assertTrue(
            game.check_answer(game.normalize_input(user_text), answer)
        )

    def test_check_answer_accepts_common_asr_confusion_for_iron_ingot(self):
        game = MinecraftQuizGame(rng=random.Random(123))
        rail_question = next(q for q in game.question_bank if q["id"] == "craft_rail")
        answer = game._build_answer_payload(rail_question, [0, 1, 2])

        self.assertTrue(
            game.check_answer(game.normalize_input("黑铁力"), answer)
        )

    def test_wrong_feedback_and_hint_reference_current_question(self):
        game = MinecraftQuizGame(rng=random.Random(123))
        _, answer, _ = game.generate_question(0, 0, 0)

        hint = game.get_hint(answer)
        feedback = game.get_wrong_feedback("B", answer)

        self.assertTrue(hint)
        self.assertIn(answer["correct_text"], feedback)
        self.assertIn(answer["correct_option"], feedback)


if __name__ == "__main__":
    unittest.main()
