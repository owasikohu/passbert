"""Sequential, resumable collection -> descriptor replay -> audit -> train-only label pilot."""
import argparse
import subprocess
import sys
p=argparse.ArgumentParser();p.add_argument('--target',type=int,default=10000);p.add_argument('--root',default='artifacts/corpus-10k');p.add_argument('--workers',type=int,default=8);p.add_argument('--pilot',type=int,default=500);args=p.parse_args()
def run(module,*arguments):subprocess.run([sys.executable,'-m',module,*map(str,arguments)],check=True)
run('scripts.collect_commoncrawl','--target',args.target,'--output',args.root,'--workers',args.workers)
run('scripts.enrich_corpus','--root',args.root)
run('scripts.audit_corpus','--root',args.root)
run('scripts.label_corpus','--input',args.root+'/train.jsonl','--output',args.root+'/label-pilot','--limit',args.pilot)
