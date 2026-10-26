from searchengine.cli import main


def test_cli_runs():
    assert main([]) == 0
