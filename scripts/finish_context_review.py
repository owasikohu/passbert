"""Retrieve the existing context experiment and produce its paired comparison."""
import subprocess
import sys

if __name__=='__main__':
 subprocess.run([sys.executable,'-m','scripts.finish_blind_review','--kernel','owasikohu/passbert-context-review-qwen38-v3','--root','artifacts/context-review-v3'],check=True)
 subprocess.run([sys.executable,'-m','scripts.compare_context_review'],check=True)
 subprocess.run([sys.executable,'-m','scripts.audit_context_review'],check=True)
