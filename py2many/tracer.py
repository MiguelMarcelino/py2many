# Trace object types that are inserted into Python list.

import ast

from py2many.analysis import get_id
from py2many.clike import CLikeTranspiler
from py2many.exceptions import AstNotImplementedError

from typing import Optional


def decltype(node):
    """Create C++ decltype statement"""
    pass


# is it slow? is it correct?
def _lookup_class_or_module(name, scopes) -> Optional[ast.ClassDef]:
    for scope in scopes:
        if isinstance(scope, ast.ClassDef) and scope.name == name:
            return scope
        for entry in scope.body:
            if isinstance(entry, ast.ClassDef):
                if entry.name == name:
                    return entry
        if hasattr(scope, "imports"):
            for entry in scope.imports:
                if entry.name == name:
                    return entry
    return None


def is_class_or_module(name, scopes):
    entry = _lookup_class_or_module(name, scopes)
    return entry is not None


def is_enum(name, scopes):
    entry = _lookup_class_or_module(name, scopes)
    if entry and hasattr(entry, "bases"):
        bases = set([get_id(base) for base in entry.bases])
        enum_bases = {"Enum", "IntEnum", "IntFlag"}
        return bases & enum_bases
    return False


def is_self_arg(name, scopes):
    for scope in scopes:
        for entry in scope.body:
            if isinstance(entry, ast.FunctionDef):
                if len(entry.args.args):
                    first_arg = entry.args.args[0]
                    if get_id(first_arg) == name and hasattr(entry, "self_type"):
                        return True
    return False


def is_list(node):
    """Check if a node was assigned as a list"""
    if isinstance(node, ast.List):
        return True
    elif isinstance(node, ast.Assign):
        return is_list(node.value)
    elif isinstance(node, ast.Name):
        var = node.scopes.find(get_id(node))
        return (
            hasattr(var, "assigned_from")
            and not isinstance(var.assigned_from, ast.FunctionDef)
            and not isinstance(var.assigned_from, ast.For)
            and is_list(var.assigned_from.value)
        )
    else:
        ann = getattr(node, "annotation", None)
        list_ann = lambda x: x == "list" or x == "List"
        return (isinstance(ann, ast.Name) and list_ann(get_id(ann))) or (
            isinstance(ann, ast.Subscript) and list_ann(get_id(ann.value))
        )


############################################
# Added


# Searches if a given name is associated to a class
# object given a scope.
def is_class_type(name, scopes):
    return get_class_scope(name, scopes) is not None


# Gets the class scope given a name
def get_class_scope(name, scopes):
    entry = _lookup_value_type_name(name, scopes)
    if entry is None:
        # Try looking for class module with given name
        entry = _lookup_class_or_module(name, scopes)
    else:
        entry = _lookup_class_or_module(get_id(entry), scopes)
    return entry


# Searches for the closest scope using
# the given scope (search in reverse order)
def find_closest_scope(scopes):
    for i in range(len(scopes) - 1, 0, -1):
        sc = scopes[i]
        if (
            isinstance(sc, ast.FunctionDef)
            or isinstance(sc, ast.ClassDef)
            or isinstance(sc, ast.Module)
        ):
            return sc

    return None


# Searches for the first node of type node_type using
# the given scope (search in reverse order)
def find_node_by_type(node_type, scopes):
    c_node = None
    for i in range(len(scopes) - 1, -1, -1):
        sc = scopes[i]
        if isinstance(sc, node_type):
            c_node = sc
            break
        if hasattr(sc, "body"):
            c_node = find_in_body(sc.body, (lambda x: isinstance(x, node_type)))
            if c_node is not None:
                break
    return c_node


def find_node_by_name(name, scopes):
    if name is None:
        return None

    c_node = None
    for i in range(len(scopes) - 1, -1, -1):
        sc = scopes[i]
        if matches_name(sc, name):
            c_node = sc
            break
        c_node = find_in_body(sc.body, (lambda x: matches_name(x, name)))
    return c_node


# Finds a node by its name and type
def find_node_by_name_and_type(name, node_type, scopes):
    if name is None:
        return None, None

    c_node = None
    scope_name = None
    for i in range(len(scopes) - 1, -1, -1):
        sc = scopes[i]
        if isinstance(sc, node_type) and matches_name(sc, name):
            c_node = sc
            break
        c_node = find_in_body(
            sc.body, (lambda x: isinstance(x, node_type) and matches_name(x, name))
        )
        if c_node:
            scope_name = (
                get_id(sc)
                if (isinstance(sc, ast.FunctionDef) or isinstance(sc, ast.ClassDef))
                else "module"
            )
            break
    return c_node, scope_name


def find_in_body(body, fn):
    for i in range(len(body) - 1, -1, -1):
        node = body[i]
        if fn(node):
            return node
        elif isinstance(node, ast.Expr) and hasattr(node, "value") and fn(node.value):
            return node.value
        elif hasattr(node, "iter") and fn(node.iter):
            return node.iter
        elif hasattr(node, "test") and fn(node.test):
            return node.test
        elif hasattr(node, "body"):
            ret = find_in_body(node.body, fn)
            if ret:
                return ret
        elif hasattr(node, "handlers"):
            # Visit exception handlers
            ret = find_in_body(node.handlers, fn)
            if ret:
                return ret

    return None


# Finds a node in a given scope
def find_in_scope(body, fn):
    for i in range(len(body) - 1, -1, -1):
        node = body[i]
        if fn(node):
            return node
        elif isinstance(node, ast.Expr) and hasattr(node, "value") and fn(node.value):
            return node.value
        elif hasattr(node, "body") and not (
            isinstance(node, ast.FunctionDef) or isinstance(node, ast.ClassDef)
        ):
            ret = find_in_scope(node.body, fn)
            if ret:
                return ret

    return None


def find_parent_of_type(type, scopes):
    for i in range(len(scopes) - 1, -1, -1):
        node = scopes[i]
        if isinstance(node, type):
            return node


# Checks if a given node's name matches
# the supplied name
def matches_name(node, name):
    return (
        (isinstance(node, ast.Assign) and get_id(node.targets[0]) == name)
        or (
            (isinstance(node, ast.AnnAssign) or isinstance(node, ast.AugAssign))
            and get_id(node.target) == name
        )
        or (hasattr(node, "func") and get_id(node.func) == name)
        or (get_id(node) == name)
    )


def _lookup_value_type_name(name, scopes):
    for scope in scopes:
        for entry in scope.body:
            if isinstance(entry, ast.Assign):
                if (
                    name in list(map(get_id, entry.targets))
                    and hasattr(entry, "value")
                    and isinstance(entry.value, ast.Call)
                    and hasattr(entry.value, "func")
                ):
                    return entry.value.func
            if isinstance(entry, ast.AnnAssign) or isinstance(entry, ast.AugAssign):
                if name == get_id(entry.target) and hasattr(entry.value, "func"):
                    return entry.value.func
    return None


#####################################


def value_expr(node):
    """
    Follow all assignments down the rabbit hole in order to find
    the value expression of a name.
    The boundary is set to the current scope.
    """
    return ValueExpressionVisitor().visit(node)


def value_type(node):
    """
    Guess the value type of a node based on the manipulations or assignments
    in the current scope.
    Special case: If node is a container like a list the value type inside the
    list is returned not the list type itself.
    """
    return ValueTypeVisitor().visit(node)


class ValueExpressionVisitor(ast.NodeVisitor):
    def __init__(self):
        super().__init__()
        self._stack = []

    def visit_Constant(self, node):
        return str(node.n)

    def visit_Str(self, node):
        return node.s

    def visit_Name(self, node):
        name = get_id(node)
        if name in self._stack:
            # Avoid infinite recursion in cases like foo = bar(foo)
            return name
        self._stack.append(name)
        try:
            return self._visit_Name(node)
        finally:
            self._stack.pop()

    def _visit_Name(self, node):
        name = get_id(node)
        var = node.scopes.find(name)

        if not var:  # TODO why no scopes found for node id?
            return name

        # TODO: code looks C++ specific. Move out
        if hasattr(var, "assigned_from"):
            if isinstance(var.assigned_from, ast.For):
                it = var.assigned_from.iter
                return "std::declval<typename decltype({0})::value_type>()".format(
                    self.visit(it)
                )
            elif isinstance(var.assigned_from, ast.FunctionDef):
                return get_id(var)
            else:
                return self.visit(var.assigned_from.value)
        else:
            return name

    def visit_Call(self, node):
        arg_strings = [self.visit(arg) for arg in node.args]
        arg_strings = [a for a in arg_strings if a is not None]
        params = ",".join(arg_strings)
        return "{0}({1})".format(self.visit(node.func), params)

    def visit_Assign(self, node):
        return self.visit(node.value)

    def visit_BinOp(self, node):
        return "{0} {1} {2}".format(
            self.visit(node.left),
            CLikeTranspiler().visit(node.op),
            self.visit(node.right),
        )


class ValueTypeVisitor(ast.NodeVisitor):
    def generic_visit(self, node):
        return "auto"

    def visit_Constant(self, node):
        return value_expr(node)

    def visit_Str(self, node):
        return value_expr(node)

    def visit_Name(self, node):
        if node.id == "True" or node.id == "False":
            return CLikeTranspiler().visit(node)

        var = node.scopes.find(node.id)
        if not var:
            return get_id(node)
        if defined_before(var, node):
            return get_id(node)
        else:
            return self.visit(var.assigned_from.value)

    def visit_NameConstant(self, node):
        return CLikeTranspiler().visit(node)

    def visit_Call(self, node):
        params = [self.visit(arg) for arg in node.args]
        if any(t is None for t in params):
            raise AstNotImplementedError(f"Call({params}) not implemented", node)
        params = ",".join(params)
        return "{0}({1})".format(self.visit(node.func), params)

    def visit_Attribute(self, node):
        value_id = get_id(node.value)
        return f"{value_id}.{node.attr}"

    def visit_Assign(self, node):
        if isinstance(node.value, ast.List):
            if len(node.value.elts) > 0:
                val = node.value.elts[0]
                return self.visit(val)
            else:
                target = node.targets[0]
                var = node.scopes.find(get_id(target))
                if hasattr(var, "calls"):
                    first_added_value = var.calls[0].args[0]
                    return value_expr(first_added_value)
                else:
                    return None
        else:
            return self.visit(node.value)


def defined_before(node1, node2):
    """Check if node a has been defined before an other node b"""
    return node1.lineno < node2.lineno


def is_list_assignment(node):
    return (
        hasattr(node, "value")
        and isinstance(node.value, ast.List)
        and hasattr(node, "targets")
        and isinstance(node.targets[0].ctx, ast.Store)
    )


def is_list_addition(node):
    """Check if operation is adding something to a list"""
    list_operations = ["append", "extend", "insert"]
    return (
        isinstance(node.func.ctx, ast.Load)
        and hasattr(node.func, "value")
        and isinstance(node.func.value, ast.Name)
        and node.func.attr in list_operations
    )


def is_recursive(fun):
    finder = RecursionFinder()
    finder.visit(fun)
    return finder.recursive


class RecursionFinder(ast.NodeVisitor):
    function_name = None
    recursive = False

    def visit_FunctionDef(self, node):
        self.function_name = node.name
        self.generic_visit(node)

    def visit_Call(self, node):
        self.recursive = (
            isinstance(node.func, ast.Name) and get_id(node.func) == self.function_name
        )
        self.generic_visit(node)
