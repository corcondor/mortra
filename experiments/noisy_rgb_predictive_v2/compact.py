"""Copy compact saved outputs without editing large original artifacts."""
import argparse
from pathlib import Path
import shutil


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    names={'result.json','acquisition_result.json','source_snapshot.json','config.json',
           'checkpoint.json','calibration.json','model_audit.json','heldout_summary.json','control.json',
           'artifact_hashes.json','diagnosis.json','run.log'}
    for f in args.input.rglob('*'):
        if f.is_file() and (f.name in names or f.suffix=='.png'):
            out=args.output/f.relative_to(args.input)
            out.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(f,out)


if __name__=='__main__':
    main()
