
# TODO: Not actually a Rewriter (more of a transformer)
import ast
from typing import Any, Dict

from py2many.ast_helpers import get_id
from py2many.tracer import find_in_body

def analyse_loops(node, extension=False):
    visitor = JuliaLoopAnalysis()
    visitor.visit(node)

class JuliaLoopAnalysis(ast.NodeTransformer):
    def __init__(self) -> None:
        super().__init__()
        self.current_targets = []

    def visit_Module(self, node: ast.Module) -> Any:
        self._generic_analysis_visit(node)
        return self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self._generic_analysis_visit(node)
        return self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> Any:
        # TODO
        return self.generic_visit(node)

    def _generic_analysis_visit(self, node):
        for_targets = []
        for n in node.body:
            self.generic_visit(n)
            if isinstance(n, ast.For):
                for_targets.append(get_id(n.target))
                self.current_targets.append(get_id(n.target))

            if isinstance(n, ast.Assign):
                # Verify pre-condition
                for t in n.targets:
                    if get_id(t) in for_targets:
                        return False 

                if get_id(n.value) in for_targets:
                    # TODO
                    pass
            
            if isinstance(n, ast.Call):
                for n in n.args:
                    if n in for_targets:
                        # TODO
                        pass

            if isinstance(n, ast.Return):
                if n.value in for_targets:
                    # TODO
                    pass

