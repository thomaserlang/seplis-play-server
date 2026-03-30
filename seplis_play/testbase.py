def run_file(file_name: str) -> None:
    import subprocess

    subprocess.call(['pytest', '--tb=short', file_name])