"""Repite casos afectados por correcciones y verifica el cierre de evidencia."""
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    commands=[
        ['experiments/run_suite.py','functional','--no-build','--config','functional-uniform-10mb-lru','--config','functional-uniform-2mb-lru'],
        ['experiments/run_suite.py','ttl','--no-build'],
        ['experiments/run_experiment.py','experiments/configs/preloaded-5mb-lru.json','--no-build'],
        ['experiments/check_resilience.py'],
        ['experiments/analyze_results.py','--require-complete'],
        ['experiments/verify_evidence.py'],
        ['experiments/build_report.py'],
    ]
    for command in commands:
        subprocess.run([sys.executable,*command],cwd=ROOT,check=True)


if __name__=='__main__':
    main()
