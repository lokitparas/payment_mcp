import asyncio
import streamlit as st
from typing import Optional, Dict, List, Any
from contextlib import AsyncExitStack
import json
from openai import AsyncOpenAI
import sys
import os


from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv

# Must be the first Streamlit command
st.set_page_config(page_title="Shopping Assistant", page_icon="🛍️")

# Load environment variables
load_dotenv()

print("Starting Shopping Assistant Application...")



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
        self.available_tools = []
        # self.payment_mode = False

    async def initialize(self):
        """Initialize connections to MCP servers"""
        if self._initialized:
            print("Already initialized, skipping...")
            return

        print("\nInitializing connections to MCP servers...")
        self.exit_stack = AsyncExitStack()
        try:
            print("Connecting to shopping server...")
            await self.connect_to_server("shopping", "../shopping/server.py", transport="stdio")
            print("Connecting to payment server...")
            await self.connect_to_server("payment", "../payment/server.py", transport="stdio")
            print("Successfully connected to both servers!")
            self._initialized = True

            # Collect tools from all sessions
            for session in self.sessions.values():
                if session:
                    response = await session.list_tools()
                    for tool in response.tools:
                        self.available_tools.append({
                            "type": "function",
                            "function": {
                                "name": tool.name,
                                "description": tool.description,
                                "parameters": tool.inputSchema
                            }
                        })
        except Exception as e:
            print(f"Error during initialization: {str(e)}")
            await self.cleanup()
            raise e

    async def connect_to_server(self, name: str, server_script_path: str = None, transport: str = "stdio"):
        """Connect to an MCP server"""
        print(f"\nAttempting to connect to {name} server...")
        
        try:
            
            if not os.path.exists(server_script_path):
                error_msg = f"Server script not found: {server_script_path}"
                print(error_msg)
                raise FileNotFoundError(error_msg)

            server_params = StdioServerParameters(
                command=sys.executable,
                args=[server_script_path],
                env=os.environ.copy()
            )
            print(f"Starting {name} server process...")
            transport_client = await self.exit_stack.enter_async_context(stdio_client(server_params))
            
            stdio, write = transport_client
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
        # if not self._initialized:
        #     await self.initialize()
        
        # session = self.sessions.get("shopping")
        # if not session:
        #     raise ValueError("Shopping session not initialized")
        
        # result = await session.call_tool("get_cart", {"user_id": st.session_state.user_id})
        # parsed_result = self._parse_mcp_response(result)
        
        # # If the response has a cart field, use that
        # if isinstance(parsed_result, dict) and "cart" in parsed_result:
        #     return parsed_result["cart"]
        # # If the response is a list, assume it's the cart items
        # elif isinstance(parsed_result, list):
        #     return parsed_result
        # # If we got a single item, wrap it in a list
        # elif isinstance(parsed_result, dict):
        #     return [parsed_result]
        return []

    def _parse_mcp_response(self, result):
        """Parse MCP response to handle both direct and content-based responses"""
        if hasattr(result, 'content') and isinstance(result.content, list):
            parsed_content = []
            for item in result.content:
                try:
                    if hasattr(item, 'text'):
                        parsed_item = json.loads(item.text)
                        # If this is a cart response, extract the cart items
                        if isinstance(parsed_item, dict) and "cart" in parsed_item:
                            parsed_content.extend(parsed_item["cart"])
                        else:
                            parsed_content.append(parsed_item)
                    else:
                        parsed_content.append(item)
                except (json.JSONDecodeError, AttributeError):
                    parsed_content.append(str(item))
            return parsed_content[0] if len(parsed_content) == 1 else parsed_content
        return result

    async def process_query(self, query: str, payment_mode: bool = False) -> str:
        """Process a query using GPT-4o and available tools"""
        if not self._initialized:
            await self.initialize()

        # Set the appropriate system prompt based on mode
        system_prompt = """You are a helpful shopping assistant for an online store.
        You can help users browse items and add them to cart.
        Use the available tools to assist users with their shopping needs.
        Format currency values properly and provide clear, helpful responses.
        When a user wants to add an item to cart, use the context from previous search results to identify the correct item.
        If the user's request is ambiguous, ask for clarification. Do not ask the user to specify any payment related information at this point.
        
        Once the user is ready to checkout, follow these steps strictly:
        1. First, ask the user to authenticate with their email or user ID.
        2. If the authentication is successful, review the cart items and total amount with the user and ask the user to select a payment method from their available options.
        4. Ask the user to select a shipping address from their available options.
        5. Before completing the checkout, show a summary of:
            - Selected items and total amount
            - Selected payment method
            - Selected shipping address
        6. Ask for final confirmation before completing the transaction.
        7. Only call complete_checkout after user confirmation.
        
        Important:
        - Be friendly and clear in your communication
        - Handle errors gracefully and inform the user if something goes wrong
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]

        # Add conversation history for context
        # TODO: Add conversation history properly
        if hasattr(st.session_state, 'messages'):
            for msg in st.session_state.messages:
                messages.append(msg)

        try:
            # Initial GPT-4o API call
            response = await self.openai.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=self.available_tools,
                tool_choice="auto"
            )

            final_text = []
            # print(f"Response: {response}")
            message = response.choices[0].message
            print(f"Message: {message}")
            # while message.tool_calls:
            if message.content:
                final_text.append(message.content)
            print(f"Tool calls: {message.tool_calls}")

            if message.tool_calls:
                
                for tool_call in message.tool_calls:
                    
                    tool_name = tool_call.function.name
                    print(f"Tool call: {tool_name}")
                    try:
                        tool_args = json.loads(tool_call.function.arguments)
                        session = None
                        for s in self.sessions.values():
                            if s and any(t.name == tool_name for t in (await s.list_tools()).tools):
                                session = s
                                break
                        
                        # Handle add to cart operation
                        if tool_name == "add_to_cart":
                            # Just update client-side cart

                            result = await session.call_tool(tool_name, tool_args)
                            parsed_result = self._parse_mcp_response(result)
                            print(f"Parsed result: {parsed_result}")
                            st.session_state.cart = [parsed_result]

                            print(f"Updated client-side cart: {st.session_state.cart}")
                                
                            # final_text.append(f"I have successfully added the item to your cart.")
                            messages.append({
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [tool_call]
                            })

                            # Then add the tool response
                            messages.append({
                                "role": "tool",
                                "content": json.dumps(parsed_result),
                                "tool_call_id": tool_call.id
                            })
                            
                            continue

                        # Handle authentication response
                        if tool_name == "authenticate_user":
                            # tool_args["user_id"] = st.session_state.user_id
                            session = None
                            for s in self.sessions.values():
                                if s and any(t.name == tool_name for t in (await s.list_tools()).tools):
                                    session = s
                                    break
                            
                            tool_args['cart'] = st.session_state.cart
                            if 'user_id' in tool_args:
                                tool_args['identifier'] = tool_args['user_id']
                                del tool_args['user_id']

                            print(f"Tool args: {tool_args}")
                            if session:
                                result = await session.call_tool(tool_name, tool_args)
                                print(f"Result: {result}")
                                parsed_result = self._parse_mcp_response(result)

                                # Update the response with client-side cart
                                if isinstance(parsed_result, dict):
                                    parsed_result["cart"] = st.session_state.cart
                                    st.session_state.payment_session = parsed_result
                                
                                messages.append({
                                    "role": "assistant",
                                    "content": None,
                                    "tool_calls": [tool_call]
                                })

                                # Then add the tool response
                                messages.append({
                                    "role": "tool",
                                    "content": json.dumps(parsed_result),
                                    "tool_call_id": tool_call.id
                                })
                                
                                # final_text.append(str(parsed_result))
                            continue

                        # Handle checkout completion
                        if tool_name == "complete_checkout":
                            tool_args["cart"] = st.session_state.cart
                            tool_args["user_id"] = st.session_state.user_id

                        # Execute other tool calls normally
                        session = None
                        for s in self.sessions.values():
                            if s and any(t.name == tool_name for t in (await s.list_tools()).tools):
                                session = s
                                break

                        if session:
                            result = await session.call_tool(tool_name, tool_args)
                            parsed_result = self._parse_mcp_response(result)
                            
                            print(f"Parsed result: {parsed_result}")
                            # Add tool call to messages first
                            messages.append({
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [tool_call]
                            })

                            # Then add the tool response
                            messages.append({
                                "role": "tool",
                                "content": json.dumps(parsed_result),
                                "tool_call_id": tool_call.id
                            })
                            
                            # Update payment session state if needed
                            if payment_mode and isinstance(parsed_result, dict) and "session" in parsed_result:
                                st.session_state.payment_session = parsed_result["session"]

                            # Store search results for context
                            if tool_name == "search_items":
                                self.last_searched_items = parsed_result

                            # final_text.append(str(parsed_result))

                    except Exception as e:
                        print(f"Error executing tool {tool_name}: {str(e)}")
                        continue

                # Get next response from GPT-4o
                response = await self.openai.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    tools=self.available_tools,
                    tool_choice="auto"
                )
                message = response.choices[0].message
                print(f"Message2: {message}")
            # Add final response
            if message.content:
                final_text.append(message.content)

            return "\n".join(text for text in final_text if text)

        except Exception as e:
            print(f"Error in process_query: {str(e)}")
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

async def main():
    st.title("Shopping Assistant")
    
    # Initialize session state
    if "cart" not in st.session_state:
        st.session_state.cart = []
    if "checkout_mode" not in st.session_state:
        st.session_state.checkout_mode = False
    if "payment_session" not in st.session_state:
        st.session_state.payment_session = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "user_id" not in st.session_state:
        st.session_state.user_id = "user_" + str(hash(str(st.session_state)))
    if "assistant" not in st.session_state:
        st.session_state.assistant = ShoppingAssistant()
        # Initialize the assistant
        try:
            print("Initializing assistant on startup...")
            await st.session_state.assistant.initialize()
        except Exception as e:
            print(f"Error during startup initialization: {str(e)}")
            st.error(f"Failed to initialize servers: {str(e)}")
    
    # Create sidebar for cart
    with st.sidebar:
        st.header("Shopping Cart")
        if st.session_state.cart:
            total = 0
            for item in st.session_state.cart:
                st.write(f"{item['name']} - ${item['price']:.2f}")
                total += item['price']
            st.markdown(f"### Total: ${total:.2f}")
            
            if not st.session_state.checkout_mode:
                if st.button("Proceed to Checkout"):
                    st.session_state.checkout_mode = True
                    st.session_state.messages = []  # Clear chat history for payment flow
                    st.rerun()
        else:
            st.write("Your cart is empty")
    
    # Main content area
    if st.session_state.checkout_mode:
        st.header("Checkout Process")
        
        # Show initial payment message if no messages exist
        if not st.session_state.messages:
            initial_message = """I'll help you complete your purchase. First, I need to authenticate you. 
            Please provide your email address or user ID to continue."""
            with st.chat_message("assistant"):
                st.write(initial_message)
    
    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
    
    # Chat input
    if prompt := st.chat_input("Type your message here..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)
        
        # Get assistant response
        with st.chat_message("assistant"):
            try:
                # Process message based on mode
                response = await st.session_state.assistant.process_query(
                    prompt,
                    payment_mode=st.session_state.checkout_mode
                )
                
                # Add assistant response to chat
                st.session_state.messages.append({"role": "assistant", "content": response})
                st.write(response)
                
                # Check if payment is completed
                if (st.session_state.payment_session and 
                    st.session_state.payment_session.get("status") == "completed"):
                    st.session_state.checkout_mode = False
                    st.session_state.payment_session = None
                    st.session_state.cart = []
                    st.session_state.messages = []
                    st.rerun()
                
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    # Create event loop for the application
    if 'loop' not in st.session_state:
        st.session_state.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(st.session_state.loop)
    
    # Run the main function
    st.session_state.loop.run_until_complete(main()) 