import contextlib
import io
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from scripts import latency_pattern


class LatencyPatternTests(unittest.TestCase):
    def test_missing_player_and_invalid_duration_do_not_start_a_process(self):
        for args in ([], ['--seconds', '0'], ['--seconds', '-1']):
            with self.subTest(args=args), patch.object(shutil, 'which', return_value=None), \
                    patch.object(latency_pattern.subprocess, 'run') as run, \
                    contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as result:
                    latency_pattern.main(args)
                self.assertEqual(result.exception.code, 2)
                run.assert_not_called()

    def test_explicit_path_with_spaces_and_player_failure(self):
        with tempfile.TemporaryDirectory(prefix='latency test ') as directory:
            player = Path(directory) / 'ffplay.exe'
            player.touch()
            with patch.object(latency_pattern.subprocess, 'run') as run, \
                    contextlib.redirect_stdout(io.StringIO()):
                run.return_value.returncode = 7
                self.assertEqual(latency_pattern.main(['--ffplay', str(player), '--seconds', '10']), 7)
            command = run.call_args.args[0]
            self.assertEqual(command[0], str(player))
            self.assertEqual(command[command.index('-t') + 1], '10')
            self.assertEqual(command[command.index('-f') + 1], 'lavfi')
            self.assertNotIn('shell', run.call_args.kwargs)

    def test_winget_discovery_without_path_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            player = Path(directory) / 'ffplay.exe'
            player.touch()
            with patch.object(shutil, 'which', side_effect=[None, str(player)]) as which, \
                    patch.object(latency_pattern.subprocess, 'run') as run, \
                    contextlib.redirect_stdout(io.StringIO()):
                run.return_value.returncode = 0
                self.assertEqual(latency_pattern.main([]), 0)
            self.assertTrue(which.call_args.kwargs['path'].endswith(str(Path('Microsoft/WinGet/Links'))))
            self.assertEqual(run.call_args.args[0][0], str(player))


if __name__ == '__main__':
    unittest.main()
