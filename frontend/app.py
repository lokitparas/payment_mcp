import asyncio
import streamlit as st
from typing import Optional, Dict, List, Any
from contextlib import AsyncExitStack
import json
from openai import AsyncOpenAI
import sys
import os
import atexit

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv

# Must be the first Streamlit command
st.set_page_config(page_title="Shopping Assistant", page_icon="🛍️")

# Load environment variables
load_dotenv()

print("Starting Shopping Assistant Application...")

# Create a single event loop for the entire application
if 'loop' not in st.session_state:
    st.session_state.loop = asyncio.new_event_loop()
    asyncio.set_event_loop(st.session_state.loop)

# Create a single assistant instance
if 'assistant' not in st.session_state:
    st.session_state.assistant = ShoppingAssistant()
    # Initialize the assistant
    try:
        print("Initializing assistant on startup...")
        st.session_state.loop.run_until_complete(st.session_state.assistant.initialize())
    except Exception as e:
        print(f"Error during startup initialization: {str(e)}")
        st.error(f"Failed to initialize servers: {str(e)}")

def display_item_card(item):
    """Display an item in a nice card format"""
    with st.container():
        st.markdown("""
            <style>
            .item-card {
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 15px;
                margin: 10px 0;
                background-color: white;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .item-name {
                font-size: 1.2em;
                font-weight: bold;
                color: #1f1f1f;
                margin-bottom: 5px;
            }
            .item-price {
                color: #2ecc71;
                font-weight: bold;
                font-size: 1.1em;
            }
            .item-details {
                color: #666;
                font-size: 0.9em;
                margin: 5px 0;
            }
            .item-stock {
                color: #e74c3c;
                font-size: 0.9em;
            }
            .cart-icon {
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 1000;
                background-color: white;
                padding: 10px;
                border-radius: 50%;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                cursor: pointer;
            }
            .cart-badge {
                position: absolute;
                top: -5px;
                right: -5px;
                background-color: #e74c3c;
                color: white;
                border-radius: 50%;
                padding: 2px 6px;
                font-size: 0.8em;
            }
            </style>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
            <div class="item-card">
                <div class="item-name">{item['name']}</div>
                <div class="item-price">${item['price']:.2f}</div>
                <div class="item-details">{item['description']}</div>
                <div class="item-details">Category: {item['category']}</div>
                <div class="item-stock">In Stock: {item['stock']} units</div>
                {f"<div class='item-details'>Colors: {', '.join(item.get('colors', []))}</div>" if 'colors' in item else ""}
                {f"<div class='item-details'>Sizes: {', '.join(item.get('sizes', []))}</div>" if 'sizes' in item else ""}
            </div>
        """, unsafe_allow_html=True)

def display_cart(cart):
    """Display the shopping cart"""
    if not cart:
        st.info("Your cart is empty")
        return
    
    total = sum(item['price'] for item in cart)
    st.markdown("### 🛒 Shopping Cart")
    
    for item in cart:
        display_item_card(item)
    
    st.markdown(f"### Total: ${total:.2f}")

class ShoppingAssistant:
    def __init__(self):
        print("\nInitializing Shopping Assistant...")
        self.sessions: Dict[str, Optional[ClientSession]] = {
            "shopping": None,
            "payment": None
        }
        self.exit_stack = None
        self.openai = AsyncOpenAI()
        self._initialized = False
        self.last_searched_items = []  # Store last searched items for context

    async def initialize(self):
        """Initialize connections to MCP servers"""
        if self._initialized:
            print("Already initialized, skipping...")
            return

        print("\nInitializing connections to MCP servers...")
        self.exit_stack = AsyncExitStack()
        try:
            print("Connecting to shopping server...")
            await self.connect_to_server("shopping", "../shopping/server.py")
            print("Connecting to payment server...")
            await self.connect_to_server("payment", "../payment/server.py")
            print("Successfully connected to both servers!")
            self._initialized = True
        except Exception as e:
            print(f"Error during initialization: {str(e)}")
            await self.cleanup()
            raise e

    async def connect_to_server(self, name: str, server_script_path: str):
        """Connect to an MCP server"""
        print(f"\nAttempting to connect to {name} server at {server_script_path}")
        
        if not os.path.exists(server_script_path):
            error_msg = f"Server script not found: {server_script_path}"
            print(error_msg)
            raise FileNotFoundError(error_msg)

        server_params = StdioServerParameters(
            command=sys.executable,
            args=[server_script_path],
            env=os.environ.copy()
        )

        try:
            print(f"Starting {name} server process...")
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            stdio, write = stdio_transport
            
            print(f"Initializing {name} session...")
            session = await self.exit_stack.enter_async_context(ClientSession(stdio, write))
            await session.initialize()
            self.sessions[name] = session

            # List available tools
            print(f"Getting available tools from {name} server...")
            response = await session.list_tools()
            tools = response.tools
            tools_msg = f"Connected to {name} server with tools: {[tool.name for tool in tools]}"
            print(tools_msg)
            st.sidebar.success(tools_msg)
        except Exception as e:
            error_msg = f"Failed to connect to {name} server: {str(e)}"
            print(error_msg)
            st.sidebar.error(error_msg)
            raise e

    async def get_cart(self) -> List[Dict[str, Any]]:
        """Get the current cart state from the shopping server"""
        if not self._initialized:
            await self.initialize()
        
        session = self.sessions.get("shopping")
        if not session:
            raise ValueError("Shopping session not initialized")
        
        result = await session.call_tool("get_cart", {"user_id": st.session_state.user_id})
        if hasattr(result, 'content') and isinstance(result.content, list):
            cart_items = []
            for item in result.content:
                try:
                    parsed_item = json.loads(item.text)
                    cart_items.append(parsed_item)
                except json.JSONDecodeError:
                    cart_items.append(str(item.text))
            return cart_items
        return result

    async def process_query(self, query: str) -> str:
        """Process a query using GPT-4o and available tools"""
        print("\nProcessing user query...")
        if not self._initialized:
            print("Not initialized, initializing servers...")
            await self.initialize()

        messages = [
            {
                "role": "system",
                "content": """You are a helpful shopping assistant for an online store.
                You can help users browse items, add them to cart, and complete purchases.
                Use the available tools to assist users with their shopping needs.
                Format currency values properly and provide clear, helpful responses.
                When showing items, use the display_item_card function to show them in a nice format.
                IMPORTANT: After getting results from a tool, provide a clear response to the user without making additional tool calls unless explicitly needed.
                When a user wants to add an item to cart, use the context from previous search results to identify the correct item.
                If the user's request is ambiguous, ask for clarification.
                Always use the user_id from the session state when making cart operations."""
            },
            {"role": "user", "content": query}
        ]

        # Add conversation history for context
        if hasattr(st.session_state, 'messages'):
            for msg in st.session_state.messages:
                messages.append(msg)

        # Collect tools from all sessions
        available_tools = []
        for session in self.sessions.values():
            if session:
                response = await session.list_tools()
                for tool in response.tools:
                    available_tools.append({
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.inputSchema
                        }
                    })

        try:
            # Initial GPT-4o API call
            response = await self.openai.chat.completions.create(
                model="gpt-4",
                messages=messages,
                tools=available_tools,
                tool_choice="auto"
            )

            # Process response and handle tool calls
            final_text = []
            message = response.choices[0].message

            while message.tool_calls:
                final_text.append(message.content if message.content else "")

                # Handle each tool call
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        tool_args = json.loads(tool_call.function.arguments)
                        # Add user_id to cart operations
                        if tool_name in ["add_to_cart", "get_cart"]:
                            tool_args["user_id"] = st.session_state.user_id
                    except json.JSONDecodeError:
                        continue

                    # Find the right session for this tool
                    session = None
                    for s in self.sessions.values():
                        if s:
                            tools = (await s.list_tools()).tools
                            if any(t.name == tool_name for t in tools):
                                session = s
                                break

                    if session:
                        # Execute tool call
                        result = await session.call_tool(tool_name, tool_args)
                        final_text.append(f"[Using {tool_name}...]")

                        # Debug logging for result structure
                        print(f"\nTool: {tool_name}")
                        print(f"Result: {result}")

                        # Store search results for context
                        if tool_name == "search_items":
                            self.last_searched_items = result.content if hasattr(result, 'content') else result

                        # Add tool result to messages
                        messages.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [tool_call]
                        })
                        
                        # Handle the result
                        if hasattr(result, 'content') and isinstance(result.content, list):
                            # Handle MCP tool response format
                            result_content = []
                            for item in result.content:
                                try:
                                    parsed_item = json.loads(item.text)
                                    result_content.append(parsed_item)
                                except json.JSONDecodeError:
                                    result_content.append(str(item.text))
                        else:
                            result_content = result

                        # Update cart in session state if this was an add_to_cart operation
                        if tool_name == "add_to_cart":
                            try:
                                if isinstance(result_content, dict) and "cart" in result_content:
                                    st.session_state.cart = result_content["cart"]
                                    print(f"Updated cart: {st.session_state.cart}")
                            except Exception as e:
                                print(f"Error updating cart: {str(e)}")

                        # Add result to messages with tool_call_id
                        messages.append({
                            "role": "tool",
                            "content": json.dumps(result_content),
                            "tool_call_id": tool_call.id
                        })

                        # Add result to final text
                        if isinstance(result_content, list):
                            for item in result_content:
                                if isinstance(item, dict):
                                    final_text.append(json.dumps(item, indent=2))
                                else:
                                    final_text.append(str(item))
                        else:
                            final_text.append(json.dumps(result_content, indent=2))

                # Get next response from GPT-4o
                response = await self.openai.chat.completions.create(
                    model="gpt-4",
                    messages=messages,
                    tools=available_tools,
                    tool_choice="auto"
                )
                message = response.choices[0].message

            # Add final response
            if message.content:
                final_text.append(message.content)

            return "\n".join(text for text in final_text if text)

        except Exception as e:
            print(f"Error details: {str(e)}")  # Add more detailed error logging
            return f"Error processing query: {str(e)}"

    async def cleanup(self):
        """Clean up resources"""
        if not self._initialized:
            return

        print("\nCleaning up resources...")
        if self.exit_stack is not None:
            try:
                print("Closing connections...")
                await self.exit_stack.aclose()
                print("Connections closed successfully")
            except Exception as e:
                print(f"Error during cleanup: {str(e)}")
            finally:
                self.exit_stack = None
                self.sessions = {
                    "shopping": None,
                    "payment": None
                }
                self._initialized = False
                print("Reset assistant state")

def main():
    st.title("Shopping Assistant")

    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "cart" not in st.session_state:
        st.session_state.cart = []
    if "show_cart" not in st.session_state:
        st.session_state.show_cart = False
    if "user_id" not in st.session_state:
        # Generate a unique user ID for this session
        st.session_state.user_id = "user_" + str(hash(str(st.session_state)))

    # Add cart icon in the top right
    col1, col2, col3 = st.columns([1, 1, 1])
    with col3:
        if st.button("🛒 Cart", key="cart_button"):
            st.session_state.show_cart = not st.session_state.show_cart
            # Fetch latest cart state when showing cart
            if st.session_state.show_cart:
                try:
                    cart = st.session_state.loop.run_until_complete(st.session_state.assistant.get_cart())
                    st.session_state.cart = cart
                except Exception as e:
                    st.error(f"Error fetching cart: {str(e)}")
            st.rerun()

    # Show cart if toggled
    if st.session_state.show_cart:
        display_cart(st.session_state.cart)

    # Add a reconnect button in the sidebar
    if st.sidebar.button("Reconnect to Servers"):
        print("\nReconnection requested...")
        st.session_state.loop.run_until_complete(st.session_state.assistant.cleanup())
        try:
            st.session_state.loop.run_until_complete(st.session_state.assistant.initialize())
            st.sidebar.success("Successfully reconnected to servers!")
        except Exception as e:
            st.sidebar.error(f"Reconnection failed: {str(e)}")

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                # Try to parse the content as JSON to check if it's an item or cart
                try:
                    content = json.loads(message["content"])
                    if isinstance(content, list):
                        for item in content:
                            display_item_card(item)
                    elif isinstance(content, dict) and "message" in content:
                        st.write(content["message"])
                    else:
                        st.write(message["content"])
                except json.JSONDecodeError:
                    st.write(message["content"])
            else:
                st.write(message["content"])

    # Chat input
    if prompt := st.chat_input():
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        # Get assistant response
        with st.chat_message("assistant"):
            try:
                response = st.session_state.loop.run_until_complete(st.session_state.assistant.process_query(prompt))
                st.write(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
            except Exception as e:
                st.error(f"Error: {str(e)}")

if __name__ == "__main__":
    main() 