"""
Tool layer for E-Commerce Order Resolution Agent
Uses dynamic order simulator for realistic API behavior
"""

import random
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from enum import Enum
import config
from order_simulator import get_simulator, OrderState


# Static product catalog (products don't change like orders)
PRODUCT_CATALOG = {
    "P001": {"name": "Wireless Headphones", "category": "Electronics", "stock": 45, "price": 79.99},
    "P002": {"name": "Running Shoes", "category": "Sports", "stock": 0, "price": 89.99},
    "P003": {"name": "Coffee Maker", "category": "Home", "stock": 23, "price": 129.99},
    "P004": {"name": "Yoga Mat", "category": "Sports", "stock": 67, "price": 34.99},
    "P005": {"name": "Laptop Stand", "category": "Electronics", "price": 49.99},  # Missing stock
}


class ToolStatus(Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    ERROR = "error"
    NOT_FOUND = "not_found"


class ToolResponse:
    """Standardized tool response format"""
    def __init__(self, status: ToolStatus, data: Optional[Dict[str, Any]] = None, 
                 error: Optional[str] = None, missing_fields: Optional[List[str]] = None):
        self.status = status
        self.data = data or {}
        self.error = error
        self.missing_fields = missing_fields or []
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "data": self.data,
            "error": self.error,
            "missing_fields": self.missing_fields,
            "timestamp": self.timestamp
        }
    
    def is_successful(self) -> bool:
        return self.status == ToolStatus.SUCCESS
    
    def is_partial(self) -> bool:
        return self.status == ToolStatus.PARTIAL
    
    def has_error(self) -> bool:
        return self.status == ToolStatus.ERROR


# Dynamic inventory (not in simulator - this is product catalog)
INVENTORY = {

    "P123": {
        "product_id": "P123",
        "product_name": "Smartphone X",
        "stock": 45,
        "price": 699.99,
        "category": "electronics"
    },
    "P456": {
        "product_id": "P456",
        "product_name": "Wireless Headphones",
        "stock": 0,  # Out of stock
        "price": 89.99,
        "category": "electronics"
    },
    "P789": {
        "product_id": "P789",
        "product_name": "Smart Watch",
        "stock": 12,
        "price": 299.99,
        "category": "electronics"
    },
    "P999": {
        "product_id": "P999",
        "product_name": "Gaming Laptop",
        # Missing stock field (partial data)
        "price": 1299.99,
        "category": "electronics"
    }
}


def simulate_delay():
    """Simulate API latency"""
    if config.SIMULATE_DELAYS:
        time.sleep(random.uniform(0.1, 0.5))


def should_fail() -> bool:
    """Determine if this call should fail"""
    return random.random() < config.TOOL_FAILURE_RATE


def should_return_partial() -> bool:
    """Determine if this call should return partial data"""
    return random.random() < config.PARTIAL_DATA_RATE


def get_order_status(order_id: str) -> ToolResponse:
    """
    Retrieves order status from dynamic simulator
    
    Possible scenarios:
    - Success: Full order data returned
    - Partial: Some fields missing
    - Not Found: Order ID doesn't exist
    - Error: System failure
    """
    simulate_delay()
    
    # Simulate intermittent failures (API timeout, etc.)
    if should_fail():
        error_types = [
            "Database connection timeout. Please try again.",
            "Order service unavailable",
            "API rate limit exceeded",
            "Internal server error"
        ]
        return ToolResponse(
            status=ToolStatus.ERROR,
            error=random.choice(error_types)
        )
    
    # Get order from simulator
    simulator = get_simulator()
    order = simulator.get_order(order_id)
    
    if not order:
        return ToolResponse(
            status=ToolStatus.NOT_FOUND,
            error=f"Order ID {order_id} not found"
        )
    
    # Convert simulator format to tool response
    order_data = {
        "order_id": order["order_id"],
        "product_id": order["product_id"],
        "product_name": order["product_name"],
        "status": order["current_state"],
        "order_date": order["order_date"],
        "expected_delivery": order["expected_delivery"],
        "actual_delivery": order.get("actual_delivery"),
        "price": float(order["price"]),
        "user_id": order["user_id"],
        "last_update": order["last_update"]
    }
    
    # Add delay info if stuck
    if order.get("stuck") == "True" or order.get("stuck") is True:
        order_data["delay_reason"] = order.get("delay_reason", "unknown")
    
    # Simulate partial data responses
    if should_return_partial():
        missing_fields = random.sample(
            ["actual_delivery", "last_update", "delay_reason"],
            k=random.randint(1, 2)
        )
        for field in missing_fields:
            order_data.pop(field, None)
        
        return ToolResponse(
            status=ToolStatus.PARTIAL,
            data=order_data,
            missing_fields=missing_fields
        )
    
    return ToolResponse(status=ToolStatus.SUCCESS, data=order_data)


def get_user_orders(user_id: str, limit: int = 5) -> ToolResponse:
    """
    Retrieves recent orders for a user from dynamic simulator
    
    Returns sorted list of user's orders (newest first)
    """
    simulate_delay()
    
    # Simulate service failures
    if should_fail():
        return ToolResponse(
            status=ToolStatus.ERROR,
            error="User service unavailable"
        )
    
    # Get orders from simulator
    simulator = get_simulator()
    user_orders = simulator.get_user_orders(user_id, limit=limit)
    
    if not user_orders:
        return ToolResponse(
            status=ToolStatus.NOT_FOUND,
            error=f"No orders found for user {user_id}"
        )
    
    # Convert to tool format
    orders_data = []
    for order in user_orders:
        order_item = {
            "order_id": order["order_id"],
            "product_id": order["product_id"],
            "product_name": order["product_name"],
            "status": order["current_state"],
            "order_date": order["order_date"],
            "price": float(order["price"]),
            "user_id": order["user_id"]
        }
        orders_data.append(order_item)
    
    return ToolResponse(
        status=ToolStatus.SUCCESS,
        data={
            "orders": orders_data,
            "count": len(orders_data)
        }
    )


def get_refund_status(order_id: str) -> ToolResponse:
    """
    Retrieves refund status dynamically based on order state
    
    Possible scenarios:
    - Success: Refund found (cancelled/returned orders)
    - Not Found: No refund for this order
    - Error: System failure
    """
    simulate_delay()
    
    if should_fail():
        return ToolResponse(
            status=ToolStatus.ERROR,
            error="Refund service temporarily unavailable"
        )
    
    # Get order from simulator to determine if refund exists
    simulator = get_simulator()
    order = simulator.get_order(order_id)
    
    if not order:
        # Order not found - no refund exists
        return ToolResponse(
            status=ToolStatus.NOT_FOUND,
            error=f"No refund found for order {order_id}"
        )
    
    # Determine if refund should exist based on order state
    state = order["current_state"]
    has_refund = state in ["cancelled", "returned"]
    
    # Add 15% chance of refund for delivered items (return scenario)
    if state == "delivered" and random.random() < 0.15:
        has_refund = True
    
    if not has_refund:
        return ToolResponse(
            status=ToolStatus.NOT_FOUND,
            error=f"No refund found for order {order_id}"
        )
    
    # Generate dynamic refund data
    from datetime import datetime, timedelta
    order_date = datetime.fromisoformat(order["order_date"])
    
    if state == "cancelled":
        refund_status = "processed"
        refund_amount = float(order["price"])
        processed_date = (order_date + timedelta(hours=2)).isoformat()
    elif state == "returned":
        refund_status = "processed"
        refund_amount = float(order["price"]) - 5.00  # Minus restocking fee
        processed_date = (order_date + timedelta(days=3)).isoformat()
    else:  # delivered with return
        refund_status = "initiated"
        refund_amount = float(order["price"])
        processed_date = None
    
    refund_data = {
        "order_id": order_id,
        "refund_status": refund_status,
        "refund_amount": refund_amount,
        "initiated_date": (order_date + timedelta(hours=1)).isoformat(),
        "processed_date": processed_date
    }
    
    # Simulate partial data
    if should_return_partial():
        missing_fields = []
        if "processed_date" in refund_data and refund_data["processed_date"]:
            del refund_data["processed_date"]
            missing_fields.append("processed_date")
        
        return ToolResponse(
            status=ToolStatus.PARTIAL,
            data=refund_data,
            missing_fields=missing_fields
        )
    
    return ToolResponse(
        status=ToolStatus.SUCCESS,
        data=refund_data
    )


def get_inventory(product_id: str) -> ToolResponse:
    """
    Retrieves inventory information from product catalog
    
    Possible scenarios:
    - Success: Product found with stock info
    - Partial: Product found but stock info missing
    - Not Found: Product doesn't exist
    - Error: System failure
    """
    simulate_delay()
    
    if should_fail():
        return ToolResponse(
            status=ToolStatus.ERROR,
            error="Inventory service unavailable"
        )
    
    if product_id not in PRODUCT_CATALOG:
        return ToolResponse(
            status=ToolStatus.NOT_FOUND,
            error=f"Product {product_id} not found"
        )
    
    inventory_data = PRODUCT_CATALOG[product_id].copy()
    inventory_data["product_id"] = product_id
    
    # Check if stock field is missing (partial data)
    if "stock" not in inventory_data:
        return ToolResponse(
            status=ToolStatus.PARTIAL,
            data=inventory_data,
            missing_fields=["stock"]
        )
    
    # Randomly simulate partial data
    if should_return_partial():
        del inventory_data["stock"]
        return ToolResponse(
            status=ToolStatus.PARTIAL,
            data=inventory_data,
            missing_fields=["stock"]
        )
    
    return ToolResponse(
        status=ToolStatus.SUCCESS,
        data=inventory_data
    )


def get_user_orders(user_id: str, limit: int = 5) -> ToolResponse:
    """
    Retrieves recent orders for a user from dynamic simulator
    Useful when user says "my last order" without providing order ID
    """
    simulate_delay()
    
    if should_fail():
        return ToolResponse(
            status=ToolStatus.ERROR,
            error="User service unavailable"
        )
    
    # Get orders from simulator
    simulator = get_simulator()
    user_orders = simulator.get_user_orders(user_id)
    
    if not user_orders:
        return ToolResponse(
            status=ToolStatus.NOT_FOUND,
            error=f"No orders found for user {user_id}"
        )
    
    # Limit results
    user_orders = user_orders[:limit]
    
    return ToolResponse(
        status=ToolStatus.SUCCESS,
        data={"orders": user_orders, "count": len(user_orders)}
    )


# Tool registry for the agent
AVAILABLE_TOOLS = {
    "get_order_status": {
        "function": get_order_status,
        "description": "Retrieves detailed order information including status, delivery dates, and tracking",
        "parameters": {
            "order_id": "string - The order ID to look up"
        },
        "returns": "Order details or error message"
    },
    "get_refund_status": {
        "function": get_refund_status,
        "description": "Checks if a refund exists for an order and its current status",
        "parameters": {
            "order_id": "string - The order ID to check for refunds"
        },
        "returns": "Refund details or not found message"
    },
    "get_inventory": {
        "function": get_inventory,
        "description": "Checks product availability and stock levels",
        "parameters": {
            "product_id": "string - The product ID to check"
        },
        "returns": "Inventory information including stock count"
    },
    "get_user_orders": {
        "function": get_user_orders,
        "description": "Retrieves recent orders for a user (useful when order ID is not provided)",
        "parameters": {
            "user_id": "string - The user ID",
            "limit": "int - Maximum number of orders to return (default 5)"
        },
        "returns": "List of user's recent orders"
    }
}


def execute_tool(tool_name: str, **kwargs) -> ToolResponse:
    """
    Execute a tool by name with parameters
    Provides a unified interface for the agent
    """
    if tool_name not in AVAILABLE_TOOLS:
        return ToolResponse(
            status=ToolStatus.ERROR,
            error=f"Unknown tool: {tool_name}"
        )
    
    tool_function = AVAILABLE_TOOLS[tool_name]["function"]
    
    try:
        return tool_function(**kwargs)
    except Exception as e:
        return ToolResponse(
            status=ToolStatus.ERROR,
            error=f"Tool execution failed: {str(e)}"
        )
