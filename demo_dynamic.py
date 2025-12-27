"""
Demonstration of Dynamic Order Lifecycle
Shows how orders progress through states in real-time
"""

import time
from datetime import datetime
from order_simulator import get_simulator
from tools import get_order_status, get_refund_status, get_user_orders

def print_separator():
    print("\n" + "="*70 + "\n")

def show_order_state(order_id):
    """Display current order state"""
    response = get_order_status(order_id)
    if response.is_successful():
        data = response.data
        print(f"Order {order_id}:")
        print(f"  Product: {data['product_name']}")
        print(f"  Status: {data['status']}")
        print(f"  Last Update: {data['last_update']}")
        if 'delay_reason' in data:
            print(f"  Delay Reason: {data['delay_reason']}")
        return data['status']
    else:
        print(f"Order {order_id}: {response.error}")
        return None

def show_refund_state(order_id):
    """Check refund status"""
    response = get_refund_status(order_id)
    if response.is_successful():
        data = response.data
        print(f"\nRefund for Order {order_id}:")
        print(f"  Status: {data['refund_status']}")
        print(f"  Amount: ${data['refund_amount']:.2f}")
        if data.get('processed_date'):
            print(f"  Processed: {data['processed_date']}")
    elif response.status.value == "not_found":
        print(f"\nNo refund exists for order {order_id} (order not cancelled/returned)")
    else:
        print(f"\nRefund check failed: {response.error}")

print("DYNAMIC ORDER LIFECYCLE DEMONSTRATION")
print_separator()

# Step 1: Show all current orders from CSV
print("STEP 1: Current Orders in Database (from CSV)")
print("-" * 70)
simulator = get_simulator()
all_orders = list(simulator.orders.values())[:5]  # Show first 5

for order in all_orders:
    print(f"\n{order['order_id']}: {order['product_name']}")
    print(f"  State: {order['current_state']}")
    print(f"  Ordered: {order['order_date'][:10]}")
    print(f"  Last Update: {order['last_update'][:19]}")

print_separator()

# Step 2: Query a specific order through the tool system
print("STEP 2: Query Order #98760 Through Agent Tools")
print("-" * 70)
initial_state = show_order_state("98760")

# Check if refund exists for this order
show_refund_state("98760")

print_separator()

# Step 3: Show user's orders
print("STEP 3: Get All Orders for User 'user_12345'")
print("-" * 70)
user_response = get_user_orders("user_12345", limit=3)
if user_response.is_successful():
    orders = user_response.data['orders']
    print(f"Found {user_response.data['count']} recent orders:\n")
    for order in orders:
        print(f"  {order['order_id']}: {order['product_name']} - {order['current_state']}")

print_separator()

# Step 4: Wait for simulator to progress orders
print("STEP 4: Waiting for Simulator to Update States...")
print("(Background thread runs every 5 seconds)")
print("-" * 70)

for countdown in range(6, 0, -1):
    print(f"Waiting... {countdown} seconds", end="\r")
    time.sleep(1)

print("\n\nChecking if order states changed...")
print_separator()

# Step 5: Re-query the same order to show progression
print("STEP 5: Re-Query Order #98760 After Time Progression")
print("-" * 70)
new_state = show_order_state("98760")

if new_state != initial_state:
    print(f"\nSTATE CHANGED: {initial_state} -> {new_state}")
else:
    print(f"\nState unchanged (may need more time to progress)")
    print("Note: Transitions depend on elapsed time since last update")

print_separator()

# Step 6: Show how refunds are dynamically generated
print("STEP 6: Dynamic Refund Generation Example")
print("-" * 70)
print("Checking all orders for refund eligibility:\n")

for order in all_orders[:3]:
    order_id = order['order_id']
    state = order['current_state']
    print(f"{order_id} ({state}):", end=" ")
    
    if state in ['cancelled', 'returned']:
        print("Has refund (cancelled/returned order)")
        show_refund_state(order_id)
    elif state == 'delivered':
        print("15% chance of return refund")
        show_refund_state(order_id)
    else:
        print("No refund (order still in progress)")

print_separator()

# Step 7: Show the actual CSV file content
print("STEP 7: Current CSV Database State")
print("-" * 70)
print("(Check orders_db.csv to see persistent storage)\n")

import csv
with open('orders_db.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    print(f"{'Order ID':<10} {'Product Name':<25} {'State':<15} {'Last Update':<20}")
    print("-" * 70)
    for i, row in enumerate(reader):
        if i >= 5:  # Show first 5
            break
        print(f"{row['order_id']:<10} {row['product_name']:<25} {row['current_state']:<15} {row['last_update'][:19]:<20}")

print_separator()

print("KEY TAKEAWAYS:")
print("-" * 70)
print("1. Orders are stored in CSV and updated by background thread")
print("2. States progress realistically (placed -> confirmed -> packed -> ...)")
print("3. Refunds are dynamically generated based on order state")
print("4. No hardcoded mock data - all responses come from simulator")
print("5. Time progression: 1 second = 1 hour (configurable)")
print("\nRun this script multiple times to see orders evolve!")
print_separator()
