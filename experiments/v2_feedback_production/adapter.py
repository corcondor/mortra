"""One-expression arm extension of the previously validated loop adapter."""
import ast
import inspect

from experiments.self_design_v2_feedback_loop import adapter as reference
from experiments.v2_online_feedback.adapter import ARMS


def compile_feedback():
    import textwrap
    original = ast.parse(textwrap.dedent(inspect.getsource(reference.FeedbackLoopAdapter.feedback)))
    replaced = 0
    class Replace(ast.NodeTransformer):
        def visit_Subscript(self, node):
            nonlocal replaced
            if ast.unparse(node) == "ARMS[2]":
                replaced += 1
                return ast.copy_location(ast.parse("self.arm", mode="eval").body, node)
            return self.generic_visit(node)
    tree = Replace().visit(original)
    assert replaced == 1
    namespace = dict(vars(reference))
    exec(compile(ast.fix_missing_locations(tree), "<feedback-arm-only>", "exec"), namespace)
    return namespace["feedback"]


class ArmFeedbackLoopAdapter(reference.FeedbackLoopAdapter):
    feedback = compile_feedback()

    def __init__(self, module, output, arm):
        assert arm in ARMS
        self.arm = arm
        super().__init__(module, output)
