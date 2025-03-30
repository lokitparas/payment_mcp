from typing import Dict, List, Any
from datetime import datetime
from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("payment")

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

@mcp.tool()
async def verify_email(email: str) -> bool:
    """Check if a user email exists in the database.
    
    Args:
        email: The email address to verify
    """
    return any(user["email"] == email for user in USERS.values())

@mcp.tool()
async def authenticate_user(user_id: str) -> Dict[str, Any]:
    """Authenticate a user by ID.
    
    Args:
        user_id: The ID of the user to authenticate
    """
    if user_id not in USERS:
        raise ValueError("User not found")
    return {"authenticated": True, "user_id": user_id}

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
async def complete_checkout(
    user_id: str,
    cart: List[Dict],
    payment_method_id: str,
    address_id: str
) -> Dict[str, Any]:
    """Process the final payment.
    
    Args:
        user_id: The ID of the user making the purchase
        cart: List of items in the cart
        payment_method_id: ID of the payment method to use
        address_id: ID of the shipping address
    """
    if user_id not in USERS:
        raise ValueError("User not found")

    # Calculate total
    total = sum(item["price"] * item["quantity"] for item in cart)

    # Mock transaction
    transaction = Transaction(
        id=f"tx_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        status="completed",
        amount=total,
        payment_method_id=payment_method_id,
        shipping_address_id=address_id,
        items=cart
    )

    return transaction.dict()

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio') 