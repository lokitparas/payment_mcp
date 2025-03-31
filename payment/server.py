from typing import Dict, List, Any, Optional
from datetime import datetime
from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport

# Initialize FastMCP server
mcp = FastMCP("payment")

# Payment server configuration
HOST = "localhost"
PORT = 8001
sse = SseServerTransport("/messages")
# app = Server("example-server")

async def handle_sse(scope, receive, send):
    async with sse.connect_sse(scope, receive, send) as streams:
        await mcp.run(streams[0], streams[1], mcp.create_initialization_options())

async def handle_messages(scope, receive, send):
    await sse.handle_post_message(scope, receive, send)

class PaymentMethod(BaseModel):
    id: str
    type: str
    last4: str
    exp: str

class Address(BaseModel):
    id: str
    type: str
    street: str
    city: str
    state: str
    zip: str

class PaymentSession(BaseModel):
    """Represents the current state of a payment session"""
    session_id: str
    user_id: Optional[str] = None
    cart: Optional[List[Dict]] = None
    selected_payment_method: Optional[Dict] = None
    selected_address: Optional[Dict] = None
    total_amount: Optional[float] = None
    status: str = "pending"  # pending, payment_method_selected, address_selected, ready, completed
    errors: List[str] = []

class Transaction(BaseModel):
    id: str
    status: str
    amount: float
    payment_method_id: str
    shipping_address_id: str
    items: List[Dict]

# Mock user database
USERS = {
    "user1": {
        "email": "user1@example.com",
        "wallet": [
            PaymentMethod(id="1", type="credit", last4="1234", exp="12/25"),
            PaymentMethod(id="2", type="debit", last4="5678", exp="03/26")
        ],
        "addresses": [
            Address(
                id="1",
                type="shipping",
                street="123 Main St",
                city="Springfield",
                state="IL",
                zip="62701"
            )
        ]
    }
}

# Store active payment sessions
PAYMENT_SESSIONS: Dict[str, PaymentSession] = {}

@mcp.tool()
async def create_payment_session(user_id: str, cart: List[Dict]) -> Dict[str, Any]:
    """Create a new payment session for checkout.
    
    Args:
        user_id: The ID of the user
        cart: List of items in the cart
    """
    session_id = f"session_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    total = sum(item["price"] * item.get("quantity", 1) for item in cart)
    
    session = PaymentSession(
        session_id=session_id,
        user_id=user_id,
        cart=cart,
        total_amount=total,
        status="pending"
    )
    PAYMENT_SESSIONS[session_id] = session
    return session.dict()

@mcp.tool()
async def get_payment_session(session_id: str) -> Dict[str, Any]:
    """Get the current state of a payment session.
    
    Args:
        session_id: The ID of the payment session
    """
    if session_id not in PAYMENT_SESSIONS:
        raise ValueError("Payment session not found")
    return PAYMENT_SESSIONS[session_id].dict()

@mcp.tool()
async def select_payment_method(session_id: str, payment_method_id: str) -> Dict[str, Any]:
    """Select a payment method for the session.
    
    Args:
        session_id: The ID of the payment session
        payment_method_id: The ID of the payment method to use
    """
    if session_id not in PAYMENT_SESSIONS:
        raise ValueError("Payment session not found")
    
    session = PAYMENT_SESSIONS[session_id]
    user = USERS.get(session.user_id)
    if not user:
        raise ValueError("User not found")
    
    payment_method = next((pm for pm in user["wallet"] if pm.id == payment_method_id), None)
    if not payment_method:
        raise ValueError("Payment method not found")
    
    session.selected_payment_method = payment_method.dict()
    session.status = "payment_method_selected"
    PAYMENT_SESSIONS[session_id] = session
    return session.dict()

@mcp.tool()
async def select_shipping_address(session_id: str, address_id: str) -> Dict[str, Any]:
    """Select a shipping address for the session.
    
    Args:
        session_id: The ID of the payment session
        address_id: The ID of the address to use
    """
    if session_id not in PAYMENT_SESSIONS:
        raise ValueError("Payment session not found")
    
    session = PAYMENT_SESSIONS[session_id]
    user = USERS.get(session.user_id)
    if not user:
        raise ValueError("User not found")
    
    address = next((addr for addr in user["addresses"] if addr.id == address_id), None)
    if not address:
        raise ValueError("Address not found")
    
    session.selected_address = address.dict()
    session.status = "address_selected" if not session.selected_payment_method else "ready"
    PAYMENT_SESSIONS[session_id] = session
    return session.dict()

@mcp.tool()
async def verify_email(email: str) -> bool:
    """Check if a user email exists in the database.
    
    Args:
        email: The email address to verify
    """
    return any(user["email"] == email for user in USERS.values())


@mcp.tool()
async def get_user_wallet(user_id: str) -> List[Dict[str, Any]]:
    """Get user's saved payment methods.
    
    Args:
        user_id: The ID of the user whose wallet to retrieve
    """
    if user_id not in USERS:
        raise ValueError("User not found")
    return [method.dict() for method in USERS[user_id]["wallet"]]

@mcp.tool()
async def get_user_addresses(user_id: str) -> List[Dict[str, Any]]:
    """Get user's saved addresses.
    
    Args:
        user_id: The ID of the user whose addresses to retrieve
    """
    if user_id not in USERS:
        raise ValueError("User not found")
    return [addr.dict() for addr in USERS[user_id]["addresses"]]

@mcp.tool()
async def complete_checkout(session_id: str) -> Dict[str, Any]:
    """Complete the checkout process using the payment session.
    
    Args:
        session_id: The ID of the payment session to complete
    """
    if session_id not in PAYMENT_SESSIONS:
        raise ValueError("Payment session not found")
    
    session = PAYMENT_SESSIONS[session_id]
    if session.status != "ready":
        missing = []
        if not session.selected_payment_method:
            missing.append("payment method")
        if not session.selected_address:
            missing.append("shipping address")
        raise ValueError(f"Cannot complete checkout. Missing: {', '.join(missing)}")

    # Create transaction
    transaction = Transaction(
        id=f"tx_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        status="completed",
        amount=session.total_amount,
        payment_method_id=session.selected_payment_method["id"],
        shipping_address_id=session.selected_address["id"],
        items=session.cart
    )

    # Update session status
    session.status = "completed"
    PAYMENT_SESSIONS[session_id] = session

    return {
        "transaction": transaction.dict(),
        "session": session.dict()
    }

@mcp.tool()
async def authenticate_user(identifier: str, cart: Optional[List[Dict]] = None) -> Dict[str, Any]:
    """Initialize a payment session by authenticating user with email or user_id.
    This is the first step in the payment flow.
    
    Args:
        identifier: Email or user_id to authenticate with
        cart: Optional cart items to initialize the session with
    """
    # Check if identifier is an email or user_id
    user_id = None
    for uid, user_data in USERS.items():
        if uid == identifier or user_data["email"] == identifier:
            user_id = uid
            break
    
    if not user_id:
        raise ValueError("User not found. Please provide a valid email or user ID.")
    
    # Create a new payment session
    session_id = f"session_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    session = PaymentSession(
        session_id=session_id,
        user_id=user_id,
        cart=cart,
        total_amount=sum(item["price"] * item.get("quantity", 1) for item in cart) if cart else None,
        status="pending"
    )
    PAYMENT_SESSIONS[session_id] = session
    
    # Return session along with available payment methods and addresses
    return {
        "session": session.dict(),
        "available_payment_methods": [method.dict() for method in USERS[user_id]["wallet"]],
        "available_addresses": [addr.dict() for addr in USERS[user_id]["addresses"]]
    }


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio') 