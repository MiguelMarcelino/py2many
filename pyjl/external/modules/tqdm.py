
import ast
import tqdm
from typing import Callable, Dict, Tuple, Union

class JuliaExternalModulePlugins():
    def visit_tqdm(self, node: ast.Call, vargs: list[str], kwargs: list[str]):
        self._usings.add("ProgressBars")
        # Using tqdm alias (Identical to using ProgressBar)
        return f"tqdm({', '.join(vargs)})"


FuncType = Union[Callable, str]

FUNC_DISPATCH_TABLE: Dict[FuncType, Tuple[Callable, bool]] = {
    tqdm.tqdm: (JuliaExternalModulePlugins.visit_tqdm, True),
}

IGNORED_MODULE_SET = set(["tqdm"])