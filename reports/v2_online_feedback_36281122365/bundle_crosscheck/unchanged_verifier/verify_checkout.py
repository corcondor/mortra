"""Compare source excerpts against the real pinned checkout, without running it.
Usage: python verify_checkout.py /path/to/mortra
This check was not executed against a full local checkout in the sandbox run.
"""
import argparse,ast,copy,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
NAMES=('MicroGame','StructuralLearner','solve_fixed_field','evaluate_random_player','evaluate_game')
class StripDocs(ast.NodeTransformer):
    def generic_visit(self,node):
        node=super().generic_visit(node)
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and node.body:
            first=node.body[0]
            if isinstance(first,ast.Expr) and isinstance(first.value,ast.Constant) and isinstance(first.value.value,str):
                node.body=node.body[1:]
        return node

def definitions(path):
    tree=ast.parse(path.read_text(encoding='utf8'))
    return {n.name:ast.dump(StripDocs().visit(copy.deepcopy(n)),include_attributes=False)
            for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in NAMES}

def main(repo):
    source=repo/'scripts/evaluate_autonomous_game_design_loop.py'
    data=source.read_bytes().replace(b'\r\n',b'\n')
    blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
    expected='9560ba0d2b1782cf6c54d69e43b5ad906810063b'
    a=definitions(source);b=definitions(ROOT/'reference/v2_source_excerpt.py')
    result={'full_script_git_blob_lf':blob,'expected':expected,
            'matches':{n:a.get(n)==b.get(n) and n in a for n in NAMES},
            'comparison':'executable AST; documentation strings and comments excluded'}
    print(json.dumps(result,indent=2)); assert blob==expected and all(result['matches'].values())
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('repository',type=Path);main(p.parse_args().repository)
