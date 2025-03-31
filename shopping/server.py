from typing import Dict, List, Any
from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP
from mcp import Tool
import json

# Initialize FastMCP server
mcp = FastMCP("shopping")

class CartItem(BaseModel):
    item_id: str
    quantity: int
    price: float
    name: str

# Mock inventory database
INVENTORY = {
    "1": {"id": "1", "name": "Classic T-Shirt", "price": 19.99, "category": "Clothing", "description": "A comfortable cotton t-shirt in various colors", "stock": 50, "colors": ["Black", "White", "Navy", "Red"]},
    "2": {"id": "2", "name": "Slim Fit Jeans", "price": 49.99, "category": "Clothing", "description": "Modern slim fit jeans with stretch fabric", "stock": 30, "sizes": ["28", "30", "32", "34", "36"]},
    "3": {"id": "3", "name": "Running Sneakers", "price": 79.99, "category": "Footwear", "description": "Lightweight running shoes with cushioning", "stock": 25, "sizes": ["7", "8", "9", "10", "11"]},
    "4": {"id": "4", "name": "Leather Wallet", "price": 29.99, "category": "Accessories", "description": "Genuine leather wallet with multiple card slots", "stock": 40, "colors": ["Brown", "Black"]},
    "5": {"id": "5", "name": "Denim Jacket", "price": 59.99, "category": "Clothing", "description": "Classic denim jacket with brass buttons", "stock": 20, "sizes": ["S", "M", "L", "XL"]},
    "6": {"id": "6", "name": "Smart Watch", "price": 199.99, "category": "Electronics", "description": "Fitness tracking smartwatch with heart rate monitor", "stock": 15, "colors": ["Black", "Silver", "Rose Gold"]},
    "7": {"id": "7", "name": "Backpack", "price": 39.99, "category": "Accessories", "description": "Water-resistant backpack with laptop sleeve", "stock": 35, "colors": ["Navy", "Gray", "Black"]},
    "8": {"id": "8", "name": "Sunglasses", "price": 89.99, "category": "Accessories", "description": "Polarized UV protection sunglasses", "stock": 45, "colors": ["Black", "Tortoise", "Silver"]},
    "9": {"id": "9", "name": "Hooded Sweatshirt", "price": 34.99, "category": "Clothing", "description": "Comfortable cotton blend hoodie", "stock": 40, "sizes": ["S", "M", "L", "XL"], "colors": ["Gray", "Black", "Navy"]},
    "10": {"id": "10", "name": "Wireless Earbuds", "price": 129.99, "category": "Electronics", "description": "True wireless earbuds with noise cancellation", "stock": 30, "colors": ["White", "Black", "Blue"]}
}

# Mock shopping carts
# SHOPPING_CARTS: Dict[str, List[Dict[str, Any]]] = {}
shopping_cart = []


@mcp.tool()
async def list_items() -> List[Dict[str, Any]]:
    """List all available items in the inventory."""
    return list(INVENTORY.values())

@mcp.tool()
async def get_item(item_id: str) -> Dict[str, Any]:
    """Get details of a specific item.
    
    Args:
        item_id: The ID of the item to retrieve
    """
    if item_id not in INVENTORY:
        raise ValueError(f"Item {item_id} not found")
    return INVENTORY[item_id]

@mcp.tool()
async def add_to_cart(item_id: str, quantity: int = 1) -> Dict[str, Any]:
    """Add an item to the shopping cart.
    
    Args:
        item_id: The ID of the item to add
        quantity: Number of items to add (default: 1)
    """
    # if user_id not in SHOPPING_CARTS:
    #     SHOPPING_CARTS[user_id] = []
    
    item = INVENTORY.get(item_id)
    if not item:
        raise ValueError(f"Item {item_id} not found")
    
    if item["stock"] < quantity:
        raise ValueError(f"Not enough stock. Available: {item['stock']}")
    
    # Add the full item details to the cart
    cart_item = {
        "item_id": item_id,
        "quantity": quantity,
        "price": item["price"],
        "name": item["name"],
        "description": item["description"],
        "category": item["category"],
        "stock": item["stock"]
    }
    
    # Add optional fields if they exist
    if "colors" in item:
        cart_item["colors"] = item["colors"]
    if "sizes" in item:
        cart_item["sizes"] = item["sizes"]
    
    shopping_cart.append(cart_item)
    
    return {
        "message": f"Added {item['name']} to cart",
        "cart": shopping_cart
    }

@mcp.tool()
async def get_cart(user_id: str) -> List[Dict[str, Any]]:
    """Get the current shopping cart for a user.
    
    Args:
        user_id: The ID of the user whose cart to retrieve
    """
    return shopping_cart

@mcp.tool()
async def search_items(query: str) -> List[Dict[str, Any]]:
    """Search for items by name or category.
    
    Args:
        query: The search query string
    """
    query = query.lower()
    return [
        item for item in INVENTORY.values()
        if query in item["name"].lower() or query in item["category"].lower()
    ]

# @mcp.tool()
# async def get_categories() -> List[str]:
#     """Get all available product categories."""
#     return list(set(item["category"] for item in INVENTORY.values()))

@mcp.tool()
async def get_items_by_category(category: str) -> List[Dict[str, Any]]:
    """Get all items in a specific category.
    
    Args:
        category: The category to filter by
    """
    return [item for item in INVENTORY.values() if item["category"].lower() == category.lower()]

@mcp.tool()
async def get_item_availability(item_id: str) -> Dict[str, Any]:
    """Check if an item is in stock.
    
    Args:
        item_id: The ID of the item to check
    """
    if item_id not in INVENTORY:
        raise ValueError(f"Item {item_id} not found")
    
    item = INVENTORY[item_id]
    return {
        "name": item["name"],
        "in_stock": item["stock"] > 0,
        "stock_count": item["stock"]
    }

if __name__ == "__main__":
    mcp.run() 