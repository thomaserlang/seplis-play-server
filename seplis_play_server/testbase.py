def run_file(file_):
    import subprocess

    subprocess.call(["pytest", "--tb=short", str(file_)])
