"""
Calculator Tool implementation
"""
import ast
import operator
import re
from typing import Dict, Any, Optional, Type, Union
from langchain_core.tools import BaseTool
from langchain_core.callbacks import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from pydantic import BaseModel
from models.models import CalculatorInput
from utils.logging import get_logger

logger = get_logger(__name__)


class CalculatorTool(BaseTool):
    """
    Calculator tool for performing mathematical calculations
    Supports basic arithmetic operations and common mathematical functions
    """
    name: str = "calculator"
    description: str = "Performs mathematical calculations. Input should be a valid mathematical expression."
    args_schema: Type[BaseModel] = CalculatorInput
    
    _operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.BitXor: operator.xor,
        ast.USub: operator.neg,
    }
    
    _functions = {
        'abs': abs,
        'round': round,
        'min': min,
        'max': max,
        'sum': sum,
        'pow': pow,
    }
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.info("Initialized calculator tool")
        
        try:
            import math
            self._functions.update({
                'sqrt': math.sqrt,
                'sin': math.sin,
                'cos': math.cos,
                'tan': math.tan,
                'asin': math.asin,
                'acos': math.acos,
                'atan': math.atan,
                'log': math.log,
                'log10': math.log10,
                'exp': math.exp,
                'pi': math.pi,
                'e': math.e,
                'ceil': math.ceil,
                'floor': math.floor,
                'factorial': math.factorial,
                'degrees': math.degrees,
                'radians': math.radians,
            })
        except ImportError:
            logger.warning("Math module not available")

    def _evaluate_expression(self, node) -> Union[int, float]:
        """Safely evaluate mathematical expression AST node"""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.BinOp):
            left = self._evaluate_expression(node.left)
            right = self._evaluate_expression(node.right)
            return self._operators[type(node.op)](left, right)
        elif isinstance(node, ast.UnaryOp):
            operand = self._evaluate_expression(node.operand)
            return self._operators[type(node.op)](operand)
        elif isinstance(node, ast.Call):
            func_name = node.func.id if isinstance(node.func, ast.Name) else str(node.func)
            if func_name not in self._functions:
                raise ValueError(f"Function '{func_name}' is not allowed")
            args = [self._evaluate_expression(arg) for arg in node.args]
            return self._functions[func_name](*args)
        elif isinstance(node, ast.Name):
            if node.id in self._functions:
                return self._functions[node.id]
            else:
                raise ValueError(f"Variable '{node.id}' is not defined")
        else:
            raise ValueError(f"Unsupported operation: {type(node)}")

    def _calculate(self, expression: str) -> str:
        """Perform the actual calculation"""
        try:
            expression = expression.strip()
            
            replacements = {
                'π': 'pi',
                'PI': 'pi',
                'E': 'e',
                '^': '**',
            }
            
            for old, new in replacements.items():
                expression = expression.replace(old, new)
            
            if not re.match(r'^[0-9+\-*/().,\s\w]+$', expression):
                raise ValueError("Invalid characters in expression")
            
            parsed = ast.parse(expression, mode='eval')
            result = self._evaluate_expression(parsed.body)
            
            if isinstance(result, float):
                if result.is_integer():
                    return str(int(result))
                else:
                    return f"{result:.10g}"  
            else:
                return str(result)
                
        except ZeroDivisionError:
            return "Error: Division by zero"
        except ValueError as e:
            return f"Error: {str(e)}"
        except Exception as e:
            logger.error(f"Calculation error: {e}")
            return f"Error: Invalid mathematical expression"

    def _run(
        self,
        expression: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """
        Execute calculator synchronously
        
        Args:
            expression: Mathematical expression to evaluate
            run_manager: Optional callback manager for tool run
        
        Returns:
            String representation of the calculation result
        """
        logger.info(f"Calculating expression: {expression}")
        
        if not expression.strip():
            return "Error: Empty expression"
        
        result = self._calculate(expression)
        logger.info(f"Calculation result: {result}")
        
        return result

    async def _arun(
        self,
        expression: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """
        Execute calculator asynchronously
        
        Args:
            expression: Mathematical expression to evaluate
            run_manager: Optional async callback manager for tool run
        
        Returns:
            String representation of the calculation result
        """
        return self._run(expression, None)