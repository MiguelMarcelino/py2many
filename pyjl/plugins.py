import argparse
import io
import itertools
import math
import operator
import time
import os
import ast
import random
import re
import sys
import unittest
from py2many.exceptions import AstUnsupportedOperation

import pyjl.juliaAst as juliaAst

from tempfile import NamedTemporaryFile
from typing import Any, Callable, Dict, Generator, List, Tuple, Union

from py2many.ast_helpers import get_id

from py2many.tracer import find_closest_scope, find_node_by_name_and_type, find_node_by_type, is_class_type

try:
    from dataclasses import dataclass
except ImportError:
    ArgumentParser = "ArgumentParser"
    ap_dataclass = "ap_dataclass"


class JuliaTranspilerPlugins:
    def visit_jl_dataclass(t_self, node: ast.ClassDef, decorator):
        t_self._usings.add("DataClass")

        _, field_repr = JuliaTranspilerPlugins._generic_dataclass_visit(node, decorator)

        # Visit class fields
        fields = "\n".join([
            node.fields_str,
            "_initvars = [" + ", ".join(field_repr) + "]\n"
        ])

        # Struct definition
        bases = [t_self.visit(base) for base in node.jl_bases]
        struct_def = f"mutable struct {node.name} <: {bases[0]}" \
            if bases else f"mutable struct {node.name}"

        body = []
        for b in node.body:
            if isinstance(b, ast.FunctionDef):
                body.append(t_self.visit(b))
        body = "\n".join(body)

        if hasattr(node, "constructor_str"):
            return f"""@dataclass {struct_def} begin
                {fields}
                {node.constructor_str}
            end
            {body}"""

        return f"""
            @dataclass {struct_def} begin
                {fields}
            end
            {body}
        """

    def visit_py_dataclass(t_self, node: ast.ClassDef, decorator) -> str:
        dataclass_data = JuliaTranspilerPlugins._generic_dataclass_visit(node, decorator)
        [d_fields, _] = dataclass_data[0], dataclass_data[1]

        fields: str = node.fields_str
        struct_fields = fields.split("\n")

        # Abstract type
        struct_name = "".join(["Abstract", get_id(node)])

        # get struct variables using getfield
        attr_vars = []
        key_vars = []
        str_struct_fields = []
        for field in struct_fields:
            field_name = field
            field_type = None
            field_split = field.split("::")
            if len(field_split) > 1:
                field_name = field_split[0]
                field_type = field_split[1]

            if field_type:
                st_name = field_type[8:] if field_type.startswith("Abstract") else field_type
                str_struct_fields.append(f"{field_name}::{field_type}"
                                        if is_class_type(field_type, node.scopes)
                                        else f"{field_name}::Abstract{field_type}")  
                key_vars.append(f"self.{field_name}"
                            if (not is_class_type(st_name, node.scopes)) else f"__key(self.{field_name})")
            else:
                str_struct_fields.append(f"{field_name}")
                key_vars.append(f"self.{field_name}")
            attr_vars.append(f"self.{field_name}")   

        # Convert into string
        key_vars = ", ".join(key_vars)
        attr_vars = ", ".join(attr_vars)
        str_struct_fields = ", ".join(str_struct_fields)

        # Visit class body
        body = []
        for b in node.body:
            if isinstance(b, ast.FunctionDef):
                body.append(t_self.visit(b))

        # Add functions to body
        if d_fields["repr"]:
            body.append(f"""
                function __repr__(self::{struct_name})::String 
                    return {struct_name}({attr_vars}) 
                end
            """)
        if d_fields["eq"]:
            body.append(f"""
                function __eq__(self::{struct_name}, other::{struct_name})::Bool
                    return __key(self) == __key(other)
                end
            """)
        if d_fields["order"]:
            body.append(f"""
                function __lt__(self::{struct_name}, other::{struct_name})::Bool
                    return __key(self) < __key(other)
                end\n
                function __le__(self::{struct_name}, other::{struct_name})::Bool
                    return __key(self) <= __key(other)
                end\n
                function __gt__(self::{struct_name}, other::{struct_name})::Bool
                    return __key(self) > __key(other)
                end\n
                function __ge__(self::{struct_name}, other::{struct_name})::Bool
                    return __key(self) >= __key(other)
                end
            """)
        if d_fields["unsafe_hash"]:
            if d_fields["_eq"]:  # && ismutable
                body.append(f"""
                function __hash__(self::{struct_name})
                    return __key(self)
                end
                """)

        body.append(f"""
                function __key(self::{struct_name})
                    ({key_vars})
                end
                """)

        body = "\n".join(body)

        bases = [t_self.visit(base) for base in node.jl_bases]
        struct_def = f"mutable struct {node.name} <: {bases[0]}" \
            if bases else f"mutable struct {node.name}"

        if hasattr(node, "constructor_str"):
            return f"{struct_def}\n{fields}\n{node.constructor_str}\nend\n{body}"

        return f"{struct_def}\n{fields}\nend\n{body}"
        

    def _generic_dataclass_visit(node, decorator):
        fields = {}
        field_repr = []
        keywords = {'init': True, 'repr': True, 'eq': True, 'order': False,
                    'unsafe_hash': False, 'frozen': False}
        parsed_decorators: Dict[str, Dict[str, str]] = node.parsed_decorators

        # Parse received keywords if needed
        if isinstance(decorator, ast.Call):
            parsed_keywords: Dict[str, str] = parsed_decorators[get_id(decorator.func)]
            for (key, value) in parsed_keywords.items():
                keywords[key] = value

        key_map = {False: "false", True: "true"}
        for kw in keywords:
            arg = kw
            value = keywords[arg]
            if value == None:
                return (None, None)
            fields[arg] = value
            field_repr.append(f"_{arg}={key_map[value]}")

        return fields, field_repr

    def visit_JuliaClass(t_self, node: ast.ClassDef, decorator) -> Any:
        t_self._usings.add("Classes")

        # Struct definition
        fields = []
        bases = []
        for b in node.jl_bases:
            b_name = t_self.visit(b)
            if b_name != f"Abstract{node.name}":
                bases.append(b_name)

            # Don't repeat elements of superclasses
            base_class = find_node_by_name_and_type(b_name, ast.ClassDef, node.scopes)[0]
            if base_class:
                base_class_decs = list(map(lambda x: x[0], base_class.fields))
                for (declaration, typename, _) in node.fields:
                    if declaration not in base_class_decs:
                        fields.append((declaration, typename))

        # Change string representation if fields have been changed
        if fields and fields != node.fields:
            fields_str = list(map(lambda x: f"{x[0]}::{x[1]}" if x[1] else x[0], fields))
            node.fields_str = (", ").join(fields_str) if fields else ""

        struct_def = f"{node.name} <: {', '.join(bases)}" \
            if bases else f"{node.name}"

        body = []
        for b in node.body:
            if isinstance(b, ast.FunctionDef):
                body.append(f"{t_self.visit(b)}")
        body = "\n".join(body)

        if hasattr(node, "constructor"):
            return f"@class {struct_def}begin\n{node.fields_str}\n{node.constructor_str}\nend\n{body}"

        return f"@class {struct_def} begin\n{node.fields_str}\nend\n{body}"

    def visit_resumables(t_self, node, decorator):
        # node.scopes[-2] because node.scopes[-1] is the current function
        parent = node.scopes[-2]
        if isinstance(parent, ast.FunctionDef):
            raise AstUnsupportedOperation(
                "Cannot use resumable functions when function is nested", node)

        t_self._usings.add("ResumableFunctions")
        
        funcdef = f"function {node.name}{node.template}({node.parsed_args}){node.return_type}"

        # Visit function body
        body = "\n".join(t_self.visit(n) for n in node.body)
        if body == "...":
            body = ""

        maybe_main = "\nmain()" if node.is_python_main else ""
        return f"@resumable {funcdef}\n{body}\nend\n{maybe_main}"

    def visit_async_ann(self, node, decorator):
        return ""

    def visit_assertTrue(t_self, node, vargs):
        JuliaTranspilerPlugins._generic_test_visit(t_self)
        return f"@test {vargs[1]}"

    def visit_assertFalse(t_self, node, vargs):
        JuliaTranspilerPlugins._generic_test_visit(t_self)
        return f"@test !({vargs[1]})"

    def visit_assertEqual(t_self, node, vargs):
        JuliaTranspilerPlugins._generic_test_visit(t_self)
        arg = t_self.visit(ast.Name(id=vargs[2]))
        return f"@test ({vargs[1]} == {arg})"

    def visit_assertRaises(t_self, node, vargs):
        exception = vargs[1]
        func = vargs[2]
        values = ", ".join(vargs[3:])
        # if len(vargs) > 4:
        #     # Lowering
        #     arr = []
        #     arr.append("# Lowered")
        #     test_vargs: list[str] = vargs[3:]
        #     for v in test_vargs:
        #         arr.append(f"@test_throws {exception} {func}({v})")
        #     return "\n".join(arr)

        return f"@test_throws {exception} {func}({values})"

    def _generic_test_visit(t_self):
        t_self._usings.add("Test")

    # def visit_array(self, node, vargs):
    #     type_code: str = re.sub(r"\"", "", vargs[0])
    #     if type_code in TYPE_CODE_MAP:
    #         return f"Vector{{{TYPE_CODE_MAP[type_code]}}}"

    def visit_open(t_self, node, vargs):
        for_node = find_node_by_type(ast.For, node.scopes)
        # Check if this is always like this
        if for_node is not None:
            return f"readline({vargs[0]})"

        return f"open({vargs[0]}, {vargs[1]})"

    def visit_named_temp_file(t_self, node, vargs):
        node.annotation = ast.Name(id="tempfile._TemporaryFileWrapper")
        node.result_type = True
        return "NamedTempFile::new()"

    def visit_range(t_self, node, vargs: List[str]) -> str:
        end = vargs[0] if len(vargs) == 1 else vargs[1]
        if ((isinstance(end, str) and end.lstrip("-").isnumeric())
                or isinstance(end, int) or isinstance(end, float)):
            end = int(end) - 1
        else:
            end += " - 1"

        if len(node.args) == 1:
            return f"(0:{end})"
        elif len(node.args) == 2:
            return f"({vargs[0]}:{end})"
        elif len(node.args) == 3:
            return f"({vargs[0]}:{vargs[2]}:{end})"

        raise Exception(
            "encountered range() call with unknown parameters: range({})".format(vargs)
        )

    def visit_print(t_self, node, vargs: List[str]) -> str:
        args = ", ".join(vargs)
        if "%" in args:
            # TODO: Further rules are necessary
            res = re.split(r"\s\%\s", args)
            args = ", ".join(res)
            t_self._usings.add("Printf")
            return f"@printf({args})"
        return f"println({args})"

    def visit_cast_int(t_self, node, vargs) -> str:
        if hasattr(node, "args") and node.args:
            arg_type = t_self._typename_from_annotation(node.args[0])
            if arg_type is not None and arg_type.startswith("Float"):
                return f"Int(floor({vargs[0]}))"
        if vargs:
            needs_parsing = False
            for varg in vargs:
                # varg: str = varg
                if not varg.lstrip("-").isnumeric():
                    needs_parsing = True
                    break
            if needs_parsing:
                return f"parse(Int, {vargs[0]})"
            else:
                return f"Int({vargs[0]})"
        return f"zero(Int)"  # Default int value

    def visit_maketrans(t_self, node, vargs: list[str]):
        original_lst = [vargs[0][i] for i in range(2, len(vargs[0]) - 1)]
        replacement_lst = [vargs[1][i] for i in range(2, len(vargs[1]) - 1)]
        element_lst = []
        for o, r in zip(original_lst, replacement_lst):
            if o in t_self._special_character_map:
                o = t_self._special_character_map[o]
            if r in t_self._special_character_map:
                r = t_self._special_character_map[r]
            element_lst.append(f'b"{o}" => b"{r}"')
        element_lst_str = ", ".join(element_lst)
        return f"Dict({element_lst_str})"

    @staticmethod
    def visit_asyncio_run(t_self, node, vargs) -> str:
        return f"block_on({vargs[0]})"

    def visit_textio_read(t_self, node, vargs):
        # TODO
        return None

    def visit_textio_write(t_self, node, vargs):
        # TODO
        return None

    def visit_ap_dataclass(t_self, cls):
        # Do whatever transformation the decorator does to cls here
        return cls


class JuliaRewriterPlugins:
    def visit_init(t_self, node: ast.FunctionDef):
        # Visit Args
        arg_values = JuliaRewriterPlugins._get_args(t_self, node.args)
        for (name, type, default) in arg_values:
            if name not in t_self._class_fields and default:
                # TODO: Deal with linenumber (and col_offset)
                if type:
                    t_self._class_fields[name] = ast.AnnAssign(
                        target=ast.Name(id=name, ctx=ast.Store()),
                        annotation = type,
                        value = default,
                        lineno=1)
                else:
                    t_self._class_fields[name] = ast.Assign(
                        targets=[ast.Name(id=name, ctx=ast.Store())],
                        value = default,
                        lineno=1)

        constructor_body = []
        for n in node.body:
            if not (isinstance(n, ast.Assign) or isinstance(n, ast.AnnAssign)):
                constructor_body.append(n)
            t_self.visit(n)

        if constructor_body:
            parent: ast.ClassDef = node.scopes[-2]
            constructor_args = node.args
            # Remove self
            constructor_args.args = constructor_args.args[1:]
            # TODO: Check lineno and col_offset
            parent.constructor = juliaAst.Constructor(
                                    struct_name = ast.Name(id = parent.name),
                                    args=constructor_args,
                                    body = constructor_body,
                                    ctx=ast.Load(), 
                                    lineno=node.lineno + len(constructor_args.args), 
                                    col_offset=4)

    def _get_args(t_self, args: ast.arguments):
        defaults = args.defaults
        arguments: list[ast.arg] = args.args
        len_defaults = len(defaults)
        len_args = len(arguments)
        arg_values = []
        for i in range(len_args):
            arg = arguments[i]
            default = None
            if defaults:
                if len_defaults != len_args:
                    diff_len = len_args - len_defaults
                    default = defaults[i - diff_len] if i >= diff_len else None
                else:
                    default = defaults[i]
            
            # if isinstance(default, ast.Constant):
            #     default = default.value
            # else:
            #     default = get_id(default)
            arg_values.append((arg.arg, arg.annotation, default))

        return arg_values

TYPE_CODE_MAP = {
    "u": "Char",
    "b": "Int8",
    "B": "Uint8",
    "h": "Int16",
    "H": "UInt16",
    "i": "Int32",
    "I": "UInt32",
    "l": "Int64",
    "L": "UInt64",
    "q": "Int128",
    "Q": "UInt128",
    "f": "Float64",
    "d": "Float64"
}

# small one liners are inlined here as lambdas
SMALL_DISPATCH_MAP = {
    "str": lambda node, vargs: f"string({vargs[0]})" if vargs else f"string()",
    "len": lambda n, vargs: f"length({vargs[0]})",
    "enumerate": lambda n, vargs: f"{vargs[0]}.iter().enumerate()",
    # default is false
    "bool": lambda n, vargs: f"Bool({vargs[0]})" if vargs else f"false",
    # ::Int64 below is a hack to pass comb_sort.jl. Need a better solution
    "floor": lambda n, vargs: f"Int64(floor({vargs[0]}))",
    "None": lambda n, vargs: f"nothing",
    "sys.argv": lambda n, vargs: "append!([PROGRAM_FILE], ARGS)",
}

SMALL_USINGS_MAP = {
    "asyncio.run": "futures::executor::block_on",
}

DISPATCH_MAP = {
    "range": JuliaTranspilerPlugins.visit_range,
    "xrange": JuliaTranspilerPlugins.visit_range,
    "print": JuliaTranspilerPlugins.visit_print,
    "int": JuliaTranspilerPlugins.visit_cast_int,
    # TODO: array.array not supported yet
    # "array.array": JuliaTranspilerPlugins.visit_array
}

MODULE_DISPATCH_TABLE: Dict[str, str] = {
    "dataclass": "DataClass",
    "json": "JSON",
    "datetime": "Dates",
    "bisect": "BisectPy"
}

DECORATOR_DISPATCH_TABLE = {
    "jl_dataclass": JuliaTranspilerPlugins.visit_jl_dataclass,
    "dataclass": JuliaTranspilerPlugins.visit_py_dataclass,
    "jl_class": JuliaTranspilerPlugins.visit_JuliaClass,
    "resumable": JuliaTranspilerPlugins.visit_resumables
}

CLASS_DISPATCH_TABLE = {
    "bytearray": (lambda self, node, vargs: f"Vector{{Int8}}()", True),
    # "dataclass": JuliaTranspilerPlugins.visit_argparse_dataclass,
}

ATTR_DISPATCH_TABLE = {
    "temp_file.name": lambda self, node, value, attr: f"{value}.path()",
}

FuncType = Union[Callable, str]

FUNC_DISPATCH_TABLE: Dict[FuncType, Tuple[Callable, bool]] = {
    # Array Operations
    list.append: (lambda self, node, vargs: f"push!({vargs[0]}, {vargs[1]})", True),
    list.clear: (lambda self, node, vargs: f"empty!({vargs[0]})", True),
    list.remove: (lambda self, node, vargs: \
                  f"{vargs[0]} = deleteat!({vargs[0]}, findfirst(isequal({vargs[1]}), {vargs[0]}))", True),
    list.extend: (lambda self, node, vargs: f"{vargs[0]} = append!({vargs[0]}, {vargs[1]})", True),
    list.count: (lambda self, node, vargs: f"count(isequal({vargs[1]}), {vargs[0]})", True),
    list.index: (lambda self, node, vargs: f"findfirst(isequal({vargs[1]}), {vargs[0]})", True),
    list: (lambda self, node, vargs: f"Vector()" if len(vargs) == 0 else f"collect({vargs[0]})", True),
    bytearray: (lambda self, node, vargs: f"Vector{{UInt8}}()" \
                if len(vargs) == 0 \
                else f"Vector{{UInt8}}(join({vargs[0]}, \"\"))", True),
    itertools.islice: (lambda self, node, vargs: f"split({vargs[0]})[{vargs[1]}]", True),
    # Math operations
    math.pow: (lambda self, node, vargs: f"{vargs[0]}^({vargs[1]})", False),
    math.sin: (lambda self, node, vargs: f"sin({vargs[0]})", False),
    math.cos: (lambda self, node, vargs: f"cos({vargs[0]})", False),
    math.tan: (lambda self, node, vargs: f"tan({vargs[0]})", False),
    math.asin: (lambda self, node, vargs: f"asin({vargs[0]})", False),
    math.acos: (lambda self, node, vargs: f"acos({vargs[0]})", False),
    math.atan: (lambda self, node, vargs: f"atan({vargs[0]})", False),
    math.radians: (lambda self, node, vargs: f"deg2rad({vargs[0]})", False),
    math.fsum: (lambda self, node, vargs: f"fsum({', '.join(vargs)})", False),
    math.sqrt: (lambda self, node, vargs: f"√({vargs[0]})", False),
    math.trunc: (lambda self, node, vargs: f"trunc({vargs[0]})" if vargs else "trunc", False),
    sum: (lambda self, node, vargs: f"sum({', '.join(vargs)})", False),
    round: (lambda self, node, vargs: f"round({vargs[0]}, digits = {vargs[1]})", False),
    operator.mod: (lambda self, node, vargs: f"mod({vargs[0]}, {vargs[1]})" if vargs else "mod", True),
    operator.floordiv: (lambda self, node, vargs: f"div({vargs[0]}, {vargs[1]})" if vargs else "div", True),
    int.conjugate: (lambda self, node, vargs: f"conj({vargs[0]})" if vargs else "conj", True),
    float.conjugate: (lambda self, node, vargs: f"conj({vargs[0]})" if vargs else "conj", True),
    divmod: (lambda self, node, vargs: f"div({vargs[0]})" if vargs else "x -> div(x)", True), # Fallback
    # io
    argparse.ArgumentParser.parse_args: (lambda self, node, vargs: "::from_args()", False),
    sys.stdin.read: (lambda self, node, vargs: f"open({vargs[0]}, r)", True),
    sys.stdin.write: (lambda self, node, vargs: f"open({vargs[0]})", True),
    sys.stdin.close: (lambda self, node, vargs: f"close({vargs[0]})", True),
    sys.exit: (lambda self, node, vargs: f"quit({vargs[0]})", True),
    sys.stdout.buffer.write: (lambda self, node, vargs: f"write(stdout, {vargs[0]})" \
        if vargs else "x -> write(stdout, x)", True), # TODO: Is there a better way to name the variable?
    sys.stdout.buffer.flush: (lambda self, node, vargs: "flush(stdout)", True),
    open: (JuliaTranspilerPlugins.visit_open, True),
    io.TextIOWrapper.read: (JuliaTranspilerPlugins.visit_textio_read, True),
    io.TextIOWrapper.read: (JuliaTranspilerPlugins.visit_textio_write, True),
    os.unlink: (lambda self, node, vargs: f"std::fs::remove_file({vargs[0]})", True),
    # misc
    str.format: (lambda self, node, vargs: f"test", True),  # Does not work
    isinstance: (lambda self, node, vargs: f"isa({vargs[0]}, {vargs[1]})", True),
    issubclass: (lambda self, node, vargs: f"{self._map_type(vargs[0])} <: {self._map_type(vargs[1])}", True),
    NamedTemporaryFile: (JuliaTranspilerPlugins.visit_named_temp_file, True),
    time.time: (lambda self, node, vargs: "pylib::time()", False),
    random.seed: (
        lambda self, node, vargs: f"pylib::random::reseed_from_f64({vargs[0]})",
        False,
    ),
    bytes.maketrans: (JuliaTranspilerPlugins.visit_maketrans, True),
    "translate": (lambda self, node, vargs: f"replace!({vargs[1]}, {vargs[2]})", False),
    random.random: (lambda self, node, vargs: "pylib::random::random()", False),
    # TODO: remove string-based fallback
    # os.cpu_count: (lambda self, node, vargs: f"length(Sys.cpu_info())", True),
    "cpu_count": (lambda self, node, vargs: f"length(Sys.cpu_info())", True),
    # Unit Tests
    unittest.TestCase.assertTrue: (JuliaTranspilerPlugins.visit_assertTrue, True),
    unittest.TestCase.assertFalse: (JuliaTranspilerPlugins.visit_assertFalse, True),
    unittest.TestCase.assertEqual: (JuliaTranspilerPlugins.visit_assertEqual, True),
    unittest.TestCase.assertRaises: (JuliaTranspilerPlugins.visit_assertRaises, True),
    # Exceptions
    ValueError: (lambda self, node, vargs: f"ArgumentError({vargs[0]})" \
         if len(vargs) == 1 else "ArgumentError" , True),
}

# Dispatches special Functions
JULIA_SPECIAL_FUNCTION_DISPATCH_TABLE = {
    "__init__": JuliaRewriterPlugins.visit_init
}
