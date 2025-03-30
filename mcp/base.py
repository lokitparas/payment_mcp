from typing import Dict, Any, Callable
import json
import sys

class MCPTool:
    def __init__(self, name: str, description: str, handler: Callable):
        self.name = name
        self.description = description
        self.handler = handler

class MCPServer:
    def __init__(self):
        self.tools: Dict[str, MCPTool] = {}
    
    def register_tool(self, tool: MCPTool):
        self.tools[tool.name] = tool
    
    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        tool_name = request.get("tool")
        if tool_name not in self.tools:
            return {"error": f"Tool {tool_name} not found"}
        
        tool = self.tools[tool_name]
        try:
            result = tool.handler(request.get("params", {}))
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}
    
    def start(self):
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                    
                request = json.loads(line)
                response = self.handle_request(request)
                print(json.dumps(response), flush=True)
            except Exception as e:
                print(json.dumps({"error": str(e)}), flush=True)

class MCPClient:
    def __init__(self):
        self.process = None
        self.tools = {}
    
    def call_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        request = {
            "tool": tool_name,
            "params": params
        }
        print(json.dumps(request), flush=True)
        response = json.loads(sys.stdin.readline())
        
        if "error" in response:
            raise Exception(response["error"])
        return response["result"] 