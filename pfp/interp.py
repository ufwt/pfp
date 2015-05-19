#!/usr/bin/env python

"""
Python format parser
"""

import copy
import glob
import sys
import os

import py010parser
from py010parser import c_ast as AST

import pfp.fields as fields
import pfp.errors as errors
import pfp.functions as functions
import pfp.builtin as builtin

class Scope(object):
	"""A class to keep track of the current scope of the interpreter"""
	def __init__(self):
		super(Scope, self).__init__()

		self._scope_stack = []
		self.push()
		
	def push(self):
		"""Create a new scope
		:returns: TODO

		"""
		self._curr_scope = {
			"types": {},
			"locals": {},
			"vars": {}
		}
		self._scope_stack.append(self._curr_scope)
	
	def clone(self):
		"""Return a new Scope object that has the curr_scope
		pinned at the current one
		:returns: A new scope object

		"""
		# TODO is this really necessary to create a brand new one?
		# I think it is... need to think about it more.
		# or... are we going to need ref counters and a global
		# scope object that allows a view into (or a snapshot of)
		# a specific scope stack?
		res = Scope()
		res._scope_stack = self._scope_stack
		res._curr_scope = self._curr_scope
		return res
	
	def pop(self):
		"""Leave the current scope
		:returns: TODO

		"""
		self._scope_stack.pop()
		self._curr_scope = self._scope_stack[-1]
	
	def add_var(self, field_name, field):
		"""Add a var to the current scope (vars are fields that
		parse the input stream)

		:field_name: TODO
		:field: TODO
		:returns: TODO

		"""
		# TODO do we allow clobbering of vars???
		self._curr_scope["vars"][field_name] = field
	
	def get_var(self, name):
		"""Return the first var of name ``name`` in the current
		scope stack (remember, vars are the ones that parse the
		input stream)

		:name: The name of the id
		:returns: TODO

		"""
		return self._search("vars", name)
	
	def add_local(self, field_name, field):
		"""Add a local variable in the current scope

		:field_name: The field's name
		:field: The field
		:returns: None

		"""
		field._pfp__name = field_name
		# TODO do we allow clobbering of locals???
		self._curr_scope["locals"][field_name] = field
	
	def get_local(self, name):
		"""Get the local field (search for it) from the scope stack

		:name: The name of the local field
		"""
		return self._search("locals", name)
	
	def add_type(self, new_name, orig_names):
		"""Record the typedefd name for orig_names. Resolve orig_names
		to their core names and save those.

		:new_name: TODO
		:orig_names: TODO
		:returns: TODO

		"""
		# TODO do we allow clobbering of types???
		res = copy.copy(orig_names)
		resolved_names = self._resolve_name(res[-1])
		if resolved_names is not None:
			res.pop()
			res += resolved_names

		self._curr_scope["types"][new_name] = res
	
	def get_type(self, name):
		"""Get the names for the typename (created by typedef)

		:name: The typedef'd name to resolve
		:returns: An array of resolved names associated with the typedef'd name

		"""
		return self._search("types", name)
	
	def get_id(self, name):
		"""Get the first id matching ``name``. Will either be a local
		or a var. Locals will be search before vars.

		:name: TODO
		:returns: TODO

		"""
		local = self._search("locals", name)
		if local is not None:
			return local

		var = self._search("vars", name)
		return var
	
	# ------------------
	# PRIVATE
	# ------------------

	def _resolve_name(self, name):
		"""TODO: Docstring for _resolve_names.

		:names: TODO
		:returns: TODO

		"""
		res = [name]
		while True:
			orig_names = self._search("types", name)
			if orig_names is not None:
				name = orig_names[-1]
				# pop off the typedefd name
				res.pop()
				# add back on the original names
				res += orig_names
			else:
				break

		return res
	
	def _search(self, category, name):
		"""Search the scope stack for the name in the specified
		category (types/locals/vars).

		:category: the category to search in (locals/types/vars)
		:name: name to search for
		:returns: None if not found, the result of the found local/type/id
		"""
		idx = len(self._scope_stack) - 1
		curr = self._curr_scope
		for scope in reversed(self._scope_stack):
			res = scope[category].get(name, None)
			if res is not None:
				return res

		return None
	
	# def __getattr__
	# def __setattr__

class PfpInterp(object):
	"""
	"""

	_builtins = {}

	@classmethod
	def add_builtin(cls, name, func, ret):
		cls._builtins[name] = functions.NativeFunction(
			name, func, ret
		)
	
	@classmethod
	def define_builtins(cls):
		"""Define the builtin functions for PFP
		"""
		if len(cls._builtins) > 0:
			return

		glob_pattern = os.path.join(os.path.dirname(__file__), "builtin", "*.py")
		for filename in glob.glob(glob_pattern):
			basename = os.path.basename(filename).replace(".py", "")
			if basename == "__init__":
				continue
			mod_base = __import__("pfp.builtin", globals(), locals(), fromlist=[basename])
			mod = getattr(mod_base, basename)
			setattr(mod, "PYVAL", fields.get_value) 

	def __init__(self):
		"""
		"""
		self.__class__.define_builtins()

		self._node_switch = {
			AST.FileAST:		self._handle_file_ast,
			AST.Decl:			self._handle_decl,
			AST.TypeDecl:		self._handle_type_decl,
			AST.Struct:			self._handle_struct,
			AST.IdentifierType:	self._handle_identifier_type,
			AST.Typedef:		self._handle_typedef,
			AST.Constant:		self._handle_constant,
			AST.BinaryOp:		self._handle_binary_op,
			AST.Assignment:		self._handle_assignment,
			AST.ID:				self._handle_id,
			AST.UnaryOp:		self._handle_unary_op,
			AST.FuncDef:		self._handle_func_def,
			AST.FuncCall:		self._handle_func_call,
			AST.FuncDecl:		self._handle_func_decl,
			AST.ParamList:		self._handle_param_list,
			AST.ExprList:		self._handle_expr_list,
			AST.Compound:		self._handle_compound,
			AST.Return:			self._handle_return,
			AST.ArrayDecl:		self._handle_array_decl
		}
	
	# --------------------
	# PUBLIC
	# --------------------

	def parse(self, stream, template):
		"""Parse the data stream using the template (e.g. parse the 010 template
		and interpret the template using the stream as the data source).

		:stream: The input data stream
		:template: The template to parse the stream with
		:returns: Pfp Dom

		"""
		self._stream = stream
		self._template = template
		self._ast = py010parser.parse_string(template)

		return self._run()
	
	# --------------------
	# PRIVATE
	# --------------------
	
	def _run(self):
		"""Interpret the parsed 010 AST
		:returns: PfpDom

		"""

		# example self._ast.show():
		#	FileAST:
		#	  Decl: data, [], [], []
		#		TypeDecl: data, []
		#		  Struct: DATA
		#			Decl: a, [], [], []
		#			  TypeDecl: a, []
		#				IdentifierType: ['char']
		#			Decl: b, [], [], []
		#			  TypeDecl: b, []
		#				IdentifierType: ['char']
		#			Decl: c, [], [], []
		#			  TypeDecl: c, []
		#				IdentifierType: ['char']
		#			Decl: d, [], [], []
		#			  TypeDecl: d, []
		#				IdentifierType: ['char']

		# it is important to pass the stream in as the stream
		# may change (e.g. compressed data)
		return self._handle_node(self._ast, None, None, self._stream)


	def _handle_node(self, node, scope, ctxt, stream):
		"""Recursively handle nodes in the 010 AST

		:node: TODO
		:scope: TODO
		:ctxt: TODO
		:stream: TODO
		:returns: TODO

		"""
		if scope is None:
			scope = self._create_scope()

		if type(node) is tuple:
			node = node[1]

		if node.__class__ not in self._node_switch:
			raise errors.UnsupportedASTNode(node.coord, node.__class__.__name__)

		return self._node_switch[node.__class__](node, scope, ctxt, stream)
	
	def _handle_file_ast(self, node, scope, ctxt, stream):
		"""TODO: Docstring for _handle_file_ast.

		:node: TODO
		:scope: TODO
		:ctxt: TODO
		:stream: TODO
		:returns: TODO

		"""
		ctxt = fields.Dom()

		for child in node.children():
			self._handle_node(child, scope, ctxt, stream)

		return ctxt
	
	def _handle_decl(self, node, scope, ctxt, stream):
		"""TODO: Docstring for _handle_decl.

		:node: TODO
		:scope: TODO
		:ctxt: TODO
		:stream: TODO
		:returns: TODO

		"""
		field = self._handle_node(node.type, scope, ctxt, stream)
		
		# locals still get a field instance, but DON'T parse the
		# stream!
		if "local" in node.quals:
			field = field()
			scope.add_local(node.name, fields)

			# this should only be able to be done with locals, right?
			# if not, move it to the bottom of the function
			if node.init is not None:
				field._pfp__value = self._handle_node(node.init, scope, ctxt, stream)

		elif isinstance(field, functions.Function):
			# eh, just add it as a local...
			# maybe the whole local/vars thinking needs to change...
			# and we should only have ONE map TODO
			field.name = node.name
			scope.add_local(node.name, field)

		elif getattr(node, "is_func_param", False):
			# we want to keep this as a class and not instantiate it
			# instantiation will be done in functions.ParamListDef.instantiate
			field = (node.name, field)

		else:
			# by this point, structs are already instantiated (they need to be
			# in order to set the new context)
			if not isinstance(field, fields.Field):
				field = field(stream)
			scope.add_var(node.name, field)
			ctxt._pfp__add_child(node.name, field)

		return field
	
	def _handle_type_decl(self, node, scope, ctxt, stream):
		"""TODO: Docstring for _handle_type_decl.

		:node: TODO
		:scope: TODO
		:ctxt: TODO
		:stream: TODO
		:returns: TODO

		"""
		decl = self._handle_node(node.type, scope, ctxt, stream)
		return decl
	
	def _handle_struct(self, node, scope, ctxt, stream):
		"""TODO: Docstring for _handle_struct.

		:node: TODO
		:scope: TODO
		:ctxt: TODO
		:stream: TODO
		:returns: TODO

		"""
		struct = fields.Struct()

		# new scope
		scope.push()

		for decl in node.decls:
			# new context! (struct)
			self._handle_node(decl, scope, struct, stream)

		return struct
	
	def _handle_identifier_type(self, node, scope, ctxt, stream):
		"""TODO: Docstring for _handle_identifier_type.

		:node: TODO
		:scope: TODO
		:ctxt: TODO
		:stream: TODO
		:returns: TODO

		"""
		cls = self._resolve_to_field_class(node.names, scope, ctxt)
		return cls
	
	def _handle_typedef(self, node, scope, ctxt, stream):
		"""TODO: Docstring for _handle_typedef.

		:node: TODO
		:scope: TODO
		:ctxt: TODO
		:stream: TODO
		:returns: TODO

		"""
		# don't actually handle the TypeDecl and Identifier nodes,
		# just directly add the types. Example structure:
		#
		#	 Typedef: BLAH, [], ['typedef']
    	#		TypeDecl: BLAH, []
      	#			IdentifierType: ['unsigned', 'char']
		#	
		scope.add_type(node.name, node.type.type.names)
	
	def _handle_constant(self, node, scope, ctxt, sream):
		"""TODO: Docstring for _handle_constant.

		:node: TODO
		:scope: TODO
		:ctxt: TODO
		:stream: TODO
		:returns: TODO

		"""
		switch = {
			"int": (int, fields.Int),
			"long": (int, fields.Int),
			"float": (float, fields.Float),
			"double": (float, fields.Double),

			# cut out the quotes
			"char": (lambda x: ord(x[1:-1]), fields.Char),

			# TODO should this be unicode?? will probably bite me later...
			# cut out the quotes
			"string": (lambda x: str(x[1:-1]), fields.String)
		}

		if node.type in switch:
			#return switch[node.type](node.value)
			conversion,field_cls = switch[node.type]
			field = field_cls()
			field._pfp__set_value(conversion(node.value))
			return field

		raise UnsupportedConstantType(node.coord, node.type)
	
	def _handle_binary_op(self, node, scope, ctxt, stream):
		"""TODO: Docstring for _handle_binary_op.

		:node: TODO
		:scope: TODO
		:ctxt: TODO
		:stream: TODO
		:returns: TODO

		"""
		switch = {
			"+": lambda x,y: x+y,
			"-": lambda x,y: x-y,
			"*": lambda x,y: x*y,
			"/": lambda x,y: x/y,
			"|": lambda x,y: x|y,
			"^": lambda x,y: x^y,
			"&": lambda x,y: x&y,
			"%": lambda x,y: x%y,
			">": lambda x,y: x>y,
			"<": lambda x,y: x<y,
			">=": lambda x,y: x>=y,
			"<=": lambda x,y: x<=y,
			"==": lambda x,y: x == y,
			"!=": lambda x,y: x != y
		}

		left_val = self._handle_node(node.left, scope, ctxt, stream)
		right_val = self._handle_node(node.right, scope, ctxt, stream)

		if node.op not in switch:
			raise errors.UnsupportedBinaryOperator(node.coord, node.op)

		return switch[node.op](left_val, right_val)
	
	def _handle_unary_op(self, node, scope, ctxt, stream):
		"""TODO: Docstring for _handle_unary_op.

		:node: TODO
		:scope: TODO
		:ctxt: TODO
		:stream: TODO
		:returns: TODO

		"""
		switch = {
			"p++": lambda x,v: x.__iadd__(1),
			"p--": lambda x,v: x.__isub__(1),
			"~":   lambda x,v: ~x,
			"!":   lambda x,v: not x
		}

		if node.op not in switch:
			raise errors.UnsupportedUnaryOperator(node.coord, node.op)

		field = self._handle_node(node.expr, scope, ctxt, stream)
		switch[node.op](field, 1)
	
	def _handle_id(self, node, scope, ctxt, stream):
		"""Handle an ID node (return a field object for the ID)

		:node: TODO
		:scope: TODO
		:ctxt: TODO
		:stream: TODO
		:returns: TODO

		"""
		field = scope.get_id(node.name)

		if field is None:
			raise errors.UnresolvedID(node.coord, node.name)

		return field
	
	def _handle_assignment(self, node, scope, ctxt, stream):
		"""Handle assignment nodes

		:node: TODO
		:scope: TODO
		:ctxt: TODO
		:stream: TODO
		:returns: TODO

		"""
		field = self._handle_node(node.lvalue, scope, ctxt, stream)
		value = self._handle_node(node.rvalue, scope, ctxt, stream)
		field._pfp__value = value
	
	def _handle_func_def(self, node, scope, ctxt, stream):
		"""Handle FuncDef nodes

		:node: TODO
		:scope: TODO
		:ctxt: TODO
		:stream: TODO
		:returns: TODO

		"""
		func = self._handle_node(node.decl, scope, ctxt, stream)
		func.body = node.body
	
	def _handle_param_list(self, node, scope, ctxt, stream):
		"""Handle ParamList nodes

		:node: TODO
		:scope: TODO
		:ctxt: TODO
		:stream: TODO
		:returns: TODO

		"""
		# params should be a list of tuples:
		# [(<name>, <field_class>), ...]
		params = []
		for param in node.params:
			param = self._handle_node(param, scope, ctxt, stream)
			params.append(param)

		param_list = functions.ParamListDef(params, node.coord)
		return param_list
	
	def _handle_func_decl(self, node, scope, ctxt, stream):
		"""Handle FuncDecl nodes

		:node: TODO
		:scope: TODO
		:ctxt: TODO
		:stream: TODO
		:returns: TODO

		"""
		# could just call _handle_param_list directly...
		for param in node.args.params:
			# see the check in _handle_decl for how this is kept from
			# being added to the local context/scope
			param.is_func_param = True
		params = self._handle_node(node.args, scope, ctxt, stream)

		func_type = self._handle_node(node.type, scope, ctxt, stream)

		func = functions.Function(func_type, params, scope)

		return func

	def _handle_func_call(self, node, scope, ctxt, stream):
		"""Handle FuncCall nodes

		:node: TODO
		:scope: TODO
		:ctxt: TODO
		:stream: TODO
		:returns: TODO

		"""
		func_args = self._handle_node(node.args, scope, ctxt, stream)
		func = self._handle_node(node.name, scope, ctxt, stream)
		return func.call(func_args, ctxt, scope, stream, self, node.coord)
	
	def _handle_expr_list(self, node, scope, ctxt, stream):
		"""Handle ExprList nodes

		:node: TODO
		:scope: TODO
		:ctxt: TODO
		:stream: TODO
		:returns: TODO

		"""
		exprs = [
			self._handle_node(expr, scope, ctxt, stream) for expr in node.exprs
		]
		return exprs
	
	def _handle_compound(self, node, scope, ctxt, stream):
		"""Handle Compound nodes

		:node: TODO
		:scope: TODO
		:ctxt: TODO
		:stream: TODO
		:returns: TODO

		"""
		scope.push()

		try:
			for child in node.children():
				self._handle_node(child, scope, ctxt, stream)

		# in case a return occurs, be sure to pop the scope
		# (returns are implemented by raising an exception)
		finally:
			scope.pop()
	
	def _handle_return(self, node, scope, ctxt, stream):
		"""Handle Return nodes

		:node: TODO
		:scope: TODO
		:ctxt: TODO
		:stream: TODO
		:returns: TODO

		"""
		ret_val = self._handle_node(node.expr, scope, ctxt, stream)
		raise errors.InterpReturn(ret_val)
	
	def _handle_array_decl(self, node, scope, ctxt, stream):
		"""Handle ArrayDecl nodes

		:node: TODO
		:scope: TODO
		:ctxt: TODO
		:stream: TODO
		:returns: TODO

		"""
		array_size = self._handle_node(node.dim, scope, ctxt, stream)
		# TODO node.dim_quals
		# node.type
		field_cls = self._handle_node(node.type, scope, ctxt, stream)
		array = fields.Array(array_size, field_cls)
		array._pfp__name = node.type.declname
		array._pfp__parse(stream)
		return array
	
	# -----------------------------
	# UTILITY
	# -----------------------------
	
	def _create_scope(self):
		"""TODO: Docstring for _create_scope.
		:returns: TODO

		"""
		res = Scope()

		for func_name,native_func in self._builtins.iteritems():
			res.add_local(func_name, native_func)

		return res

	def _get_value(self, node, scope, ctxt, stream):
		"""Return the value of the node. It is expected to be
		either an AST.ID instance or a constant

		:node: TODO
		:returns: TODO

		"""

		res = self._handle_node(node, scope, ctxt, stream)

		if isinstance(res, fields.Field):
			return res._pfp__value

		# assume it's a constant
		else:
			return res
	
	def _resolve_to_field_class(self, names, scope, ctxt):
		"""Resolve the names to a class in fields.py, resolving past
		typedefs, etc

		:names: TODO
		:scope: TODO
		:ctxt: TODO
		:returns: TODO

		"""
		switch = {
			"char":		"Char",
			"int":		"Int",
			"long": 	"Int",
			"short":	"Short",
			"double":	"Double",
			"float":	"Float",
			"void":		"Void",
			"string":	"String",
			"wstring":	"WString"
		}

		core = names[-1]
		
		if core not in switch:
			# will return a list of resolved names
			resolved_names = scope.get_type(core)
			if resolved_names[-1] not in switch:
				raise errors.UnresolvedType(node.coord, " ".join(names), " ".join(resolved_names))
			names = copy.copy(names)
			names.pop()
			names += resolved_names

		res = switch[names[-1]]

		if names[-1] in ["char", "short", "int", "long"] and "unsigned" in names[:-1]:
			res = "U" + res

		cls = getattr(fields, res)
		return cls