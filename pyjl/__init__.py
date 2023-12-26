import os

from distutils import spawn
from functools import lru_cache
from pathlib import Path
from subprocess import run

from py2many.language import LanguageSettings

from .inference import infer_julia_types
from .rewriters import (
    JuliaUnittestRewriter,
    JuliaMainRewriter,
    JuliaNestingRemoval,
    JuliaImportRewriter,
    JuliaGeneratorRewriter,
    JuliaOffsetArrayRewriter,
    JuliaIndexingRewriter,
    JuliaOrderedCollectionRewriter,
    JuliaCtypesRewriter,
    JuliaCtypesCallbackRewriter,
    JuliaArgumentParserRewriter,
    JuliaClassWrapper,
    JuliaMethodCallRewriter,
    JuliaAugAssignRewriter,
    JuliaBoolOpRewriter,
    VariableScopeRewriter,
    JuliaIORewriter,
    JuliaArbitraryPrecisionRewriter,
    JuliaContextManagerRewriter,
    JuliaExceptionRewriter,
    JuliaModuleRewriter,
)

from .optimizations import (
    AlgebraicSimplification,
    OperationOptimizer,
    PerformanceOptimizations,
)

from .transpiler import JuliaMethodCallRewriter, JuliaTranspiler
from .transformers import find_ordered_collections, parse_decorators
from .analysis import (
    analyse_variable_scope,
    detect_broadcast,
    detect_ctypes_callbacks,
    loop_range_optimization_analysis,
)


def _find_julia_base_funcs():
    """Finds Julia base functions"""
    proc = run(
        [
            "julia",
            "-e",
            "println([n for n in names(Base, all=true) if isdefined(Base, n) && isa(getfield(Base, n), Function)])",
        ],
        capture_output=True,
    )
    if not proc.returncode and proc.stdout:
        return proc.stdout
    return b""


@lru_cache()
def _julia_formatter_path():
    proc = run(
        ["julia", "-e", "import JuliaFormatter;print(pathof(JuliaFormatter))"],
        capture_output=True,
    )
    if not proc.returncode and proc.stdout:
        return str(Path(proc.stdout.decode("utf8")).parent.parent / "bin" / "format.jl")


def settings(args, env=os.environ):
    format_jl = spawn.find_executable("format.jl")

    # Parse Julia base functions
    # (TODO: Improve time it takes to import all functions)
    output = _find_julia_base_funcs().decode(encoding="utf-8")
    output = output.split(", ")
    jl_func_list: set[str] = set()
    for func in output:
        # Remove ":", as elements are Symbols
        jl_func_list.add(func[1:])
    # Remove all Python builtin functions
    jl_func_list.difference_update(set(dir(builtins)))

    return LanguageSettings(
        transpiler=JuliaTranspiler(jl_func_list),
        ext=".jl",
        display_name="Julia",
        formatter=format_jl,
        indent=None,
        rewriters=[],
        transformers=[
            parse_decorators,
            analyse_variable_scope,
            loop_range_optimization_analysis,
            find_ordered_collections,
            detect_broadcast,
            detect_ctypes_callbacks,
        ],
        post_rewriters=[
            JuliaUnittestRewriter(),
            JuliaMainRewriter(),
            JuliaNestingRemoval(),
            JuliaImportRewriter(),
            JuliaGeneratorRewriter(),
            JuliaOffsetArrayRewriter(),
            JuliaIndexingRewriter(),
            JuliaOrderedCollectionRewriter(),
            JuliaCtypesRewriter(),
            JuliaCtypesCallbackRewriter(),
            JuliaArgumentParserRewriter(),
            JuliaClassWrapper(),
            JuliaMethodCallRewriter(),
            JuliaAugAssignRewriter(),
            JuliaBoolOpRewriter(),
            VariableScopeRewriter(),
            JuliaIORewriter(),
            JuliaArbitraryPrecisionRewriter(),
            JuliaContextManagerRewriter(),
            JuliaExceptionRewriter(),
            JuliaModuleRewriter(),
        ],
        optimization_rewriters=[
            AlgebraicSimplification(),
            OperationOptimizer(),
            PerformanceOptimizations(),
        ],
        inference=infer_julia_types,
    )
