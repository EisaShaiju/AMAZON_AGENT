"""
Dynamic Order Lifecycle Simulator
Simulates real-world e-commerce order progression with CSV persistence
"""

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from enum import Enum
import threading
import time


class OrderState(Enum):
    """Order lifecycle states"""
    PLACED = "placed"
    CONFIRMED = "confirmed"
    PACKED = "packed"
    DISPATCHED = "dispatched"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    RETURNED = "returned"
    STUCK = "stuck"  # Failed state


class DelayReason(Enum):
    """Realistic delay causes"""
    WEATHER = "weather_delay"
    HIGH_DEMAND = "high_demand"
    ADDRESS_ISSUE = "address_verification_failed"
    VEHICLE_BREAKDOWN = "vehicle_breakdown"
    CUSTOMS = "customs_clearance"
    WAREHOUSE_BACKLOG = "warehouse_backlog"
    NONE = "none"


class OrderSimulator:
    """Manages dynamic order lifecycle with CSV persistence"""
    
    def __init__(self, csv_path: str = "orders_db.csv", time_multiplier: int = 3600):
        """
        Initialize order simulator
        
        Args:
            csv_path: Path to CSV database
            time_multiplier: Seconds per real second (3600 = 1 sec = 1 hour, 86400 = 1 day)
        """
        self.csv_path = Path(csv_path)
        self.time_multiplier = time_multiplier
        self.orders: Dict[str, Dict] = {}
        self.lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # State transition times (in simulated hours)
        self.transition_times = {
            OrderState.PLACED: 1,  # 1 hour to confirm
            OrderState.CONFIRMED: 2,  # 2 hours to pack
            OrderState.PACKED: 3,  # 3 hours to dispatch
            OrderState.DISPATCHED: 6,  # 6 hours to in transit
            OrderState.IN_TRANSIT: 24,  # 24 hours to out for delivery
            OrderState.OUT_FOR_DELIVERY: 4,  # 4 hours to deliver
        }
        
        # Failure probabilities
        self.failure_rates = {
            "stuck": 0.12,  # 12% get stuck
            "returned": 0.05,  # 5% get returned
            "cancelled": 0.08,  # 8% get cancelled
        }
        
        self._load_or_create_db()
    
    def _load_or_create_db(self):
        """Load existing orders or create sample data"""
        if self.csv_path.exists():
            self._load_from_csv()
        else:
            self._create_sample_orders()
            self._save_to_csv()
    
    def _create_sample_orders(self):
        """Create initial sample orders"""
        products = [
            ("P456", "Wireless Headphones", 89.99),
            ("P789", "Smart Watch", 299.99),
            ("P999", "Gaming Laptop", 1299.99),
            ("P111", "Bluetooth Speaker", 49.99),
            ("P222", "Phone Case", 19.99),
            ("P333", "USB Cable", 9.99),
            ("P444", "Laptop Skin", 14.99),
        ]
        
        base_time = datetime.now()
        order_id = 98760
        
        for i, (prod_id, prod_name, price) in enumerate(products):
            order_id += i
            order_date = base_time - timedelta(days=random.randint(1, 10))
            
            # Randomize initial state
            states = list(OrderState)[:7]  # Exclude CANCELLED, RETURNED, STUCK
            state = random.choice(states)
            
            self.orders[str(order_id)] = {
                "order_id": str(order_id),
                "product_id": prod_id,
                "product_name": prod_name,
                "price": price,
                "user_id": "user_12345",
                "order_date": order_date.isoformat(),
                "current_state": state.value,
                "last_update": order_date.isoformat(),
                "expected_delivery": (order_date + timedelta(days=7)).isoformat(),
                "actual_delivery": None,
                "delay_reason": DelayReason.NONE.value,
                "stuck": False,
            }
    
    def _load_from_csv(self):
        """Load orders from CSV"""
        with open(self.csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.orders[row["order_id"]] = row
    
    def _save_to_csv(self):
        """Save orders to CSV"""
        if not self.orders:
            return
        
        with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = list(next(iter(self.orders.values())).keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.orders.values())
    
    def get_order(self, order_id: str) -> Optional[Dict]:
        """Get order by ID"""
        with self.lock:
            return self.orders.get(order_id, None)
    
    def get_user_orders(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Get all orders for a user"""
        with self.lock:
            user_orders = [o for o in self.orders.values() if o["user_id"] == user_id]
            # Sort by order date descending
            user_orders.sort(key=lambda x: x["order_date"], reverse=True)
            return user_orders[:limit]
    
    def _progress_order(self, order: Dict) -> bool:
        """Progress order to next state, return True if changed"""
        current_state = OrderState(order["current_state"])
        
        # Skip if already in terminal state
        if current_state in [OrderState.DELIVERED, OrderState.CANCELLED, OrderState.RETURNED]:
            return False
        
        # Check if stuck
        if order.get("stuck") == "True" or order.get("stuck") is True:
            return False
        
        # Calculate time since last update
        last_update = datetime.fromisoformat(order["last_update"])
        now = datetime.now()
        elapsed_real = (now - last_update).total_seconds()
        elapsed_simulated_hours = (elapsed_real / self.time_multiplier) * 3600
        
        # Check if enough time has passed for state transition
        required_time = self.transition_times.get(current_state, 99999)
        
        if elapsed_simulated_hours < required_time:
            return False
        
        # Introduce random failures
        if random.random() < self.failure_rates["stuck"]:
            order["stuck"] = True
            order["current_state"] = OrderState.STUCK.value
            order["delay_reason"] = random.choice(list(DelayReason)[:-1]).value
            order["last_update"] = now.isoformat()
            return True
        
        if random.random() < self.failure_rates["cancelled"]:
            order["current_state"] = OrderState.CANCELLED.value
            order["last_update"] = now.isoformat()
            return True
        
        # Progress to next state
        state_progression = [
            OrderState.PLACED,
            OrderState.CONFIRMED,
            OrderState.PACKED,
            OrderState.DISPATCHED,
            OrderState.IN_TRANSIT,
            OrderState.OUT_FOR_DELIVERY,
            OrderState.DELIVERED,
        ]
        
        try:
            current_idx = state_progression.index(current_state)
            if current_idx < len(state_progression) - 1:
                next_state = state_progression[current_idx + 1]
                order["current_state"] = next_state.value
                order["last_update"] = now.isoformat()
                
                # Set actual delivery if delivered
                if next_state == OrderState.DELIVERED:
                    order["actual_delivery"] = now.isoformat()
                
                return True
        except ValueError:
            pass
        
        return False
    
    def _update_cycle(self):
        """Background thread to progress orders"""
        while self._running:
            changed = False
            with self.lock:
                for order in self.orders.values():
                    if self._progress_order(order):
                        changed = True
            
            if changed:
                self._save_to_csv()
            
            time.sleep(5)  # Check every 5 seconds
    
    def start(self):
        """Start background order progression"""
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._update_cycle, daemon=True)
            self._thread.start()
            print(f"[OrderSimulator] Started - 1 second = {self.time_multiplier/3600:.1f} hours")
    
    def stop(self):
        """Stop background progression"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        self._save_to_csv()
        print("[OrderSimulator] Stopped and saved")
    
    def reset(self):
        """Reset to fresh sample data"""
        with self.lock:
            self.orders.clear()
            self._create_sample_orders()
            self._save_to_csv()
        print("[OrderSimulator] Reset to initial state")


# Global instance
_simulator: Optional[OrderSimulator] = None

def get_simulator() -> OrderSimulator:
    """Get global simulator instance"""
    global _simulator
    if _simulator is None:
        _simulator = OrderSimulator()
        _simulator.start()
    return _simulator
