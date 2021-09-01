
import logging
import subprocess
import sys


def run_cmd(cmd, quiet=False):
    proc = subprocess.run(args=cmd.split(), capture_output=True)

    if proc.returncode:
        logging.warning(proc.stderr.decode('utf-8').rstrip())

    output = proc.stdout.decode('utf-8').rstrip()

    if not quiet:
        logging.info(output)

    proc.check_returncode()

    return output
