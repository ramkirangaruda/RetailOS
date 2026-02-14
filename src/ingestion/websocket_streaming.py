import asyncio
import websockets
import json
import duckdb
import random
import os
import sys
from datetime import datetime
from pathlib import Path

# Allow project root imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from config import DB_PATH
except ImportError:
    DB_PATH = "data/warehouse/retail.duckdb"

try:
    from src.intelligence.ml_predictive_engine import MLPredictiveEngine
    ML_ENABLED = True
except:
    ML_ENABLED = False


class WebSocketOrderStream:

    def __init__(self, host="localhost", port=8765):
        self.host = host
        self.port = port
        self.connected_clients = set()

        self.con = duckdb.connect(DB_PATH)
        print("Connected to database.")

        # Create streaming orders table
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS streaming_orders (
                order_id INTEGER,
                timestamp TIMESTAMP,
                product_id VARCHAR,
                store_id VARCHAR,
                quantity INTEGER,
                price DOUBLE
            )
        """)

        # Create ML alerts table
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS ml_alerts (
                timestamp TIMESTAMP,
                product_id VARCHAR,
                store_id VARCHAR,
                risk_level VARCHAR,
                confidence DOUBLE,
                recommended_reorder INTEGER
            )
        """)

        # Demo spike mode
        self.demo_spike = False
        self.spike_product = None
        self.spike_store = None

        if ML_ENABLED:
            self.ml_engine = MLPredictiveEngine()
            print("Auto inventory adjustment + ML enabled.")
        else:
            self.ml_engine = None
            print("ML not available.")

    # ===============================
    # DEMO CONTROL
    # ===============================
    def activate_spike(self, product_id, store_id):
        self.demo_spike = True
        self.spike_product = product_id
        self.spike_store = store_id
        print(f"🔥 DEMO SPIKE ACTIVATED for {product_id} at {store_id}")

    # ===============================
    # CLIENT MGMT
    # ===============================
    async def register(self, websocket):
        self.connected_clients.add(websocket)

    async def unregister(self, websocket):
        self.connected_clients.remove(websocket)

    async def broadcast(self, message):
        if self.connected_clients:
            await asyncio.gather(
                *[client.send(json.dumps(message)) for client in self.connected_clients],
                return_exceptions=True
            )

    # ===============================
    # ORDER GENERATOR
    # ===============================
    async def order_generator(self):
        order_id = self.con.execute(
            "SELECT COALESCE(MAX(order_id),0) FROM streaming_orders"
        ).fetchone()[0] + 1

        product_ids = [f"P{str(i).zfill(4)}" for i in range(50)]
        store_ids = [f"ST{str(i).zfill(3)}" for i in range(10)]

        while True:
            try:
                # Controlled spike
                if self.demo_spike:
                    product_id = self.spike_product
                    store_id = self.spike_store
                    quantity = random.randint(5, 10)
                else:
                    product_id = random.choice(product_ids)
                    store_id = random.choice(store_ids)
                    quantity = random.randint(1, 3)

                price = round(random.uniform(100, 3000), 2)

                self.con.execute("""
                    INSERT INTO streaming_orders VALUES (?, ?, ?, ?, ?, ?)
                """, [
                    order_id,
                    datetime.now(),
                    product_id,
                    store_id,
                    quantity,
                    price
                ])

                print(f"✓ Order #{order_id} — ₹{price}")

                # ================= ML ALERT =================
                if self.ml_engine:
                    try:
                        result = self.ml_engine.predict_stockout_with_explanation(
                            product_id,
                            store_id
                        )

                        if result:
                            risk = result["explanation"]["risk_level"]
                            confidence = result["explanation"]["ml_confidence"]
                            reorder = result["recommended_reorder"]

                            if risk in ["Medium", "High", "Critical"]:

                                print("\n🚨 ML ALERT")
                                print(f"   Product: {product_id}")
                                print(f"   Store: {store_id}")
                                print(f"   Risk: {risk}")
                                print(f"   Confidence: {confidence}%")
                                print(f"   Reorder: {reorder} units\n")

                                self.con.execute("""
                                    INSERT INTO ml_alerts VALUES (?, ?, ?, ?, ?, ?)
                                """, [
                                    datetime.now(),
                                    product_id,
                                    store_id,
                                    risk,
                                    confidence,
                                    reorder
                                ])

                                await self.broadcast({
                                    "type": "ml_alert",
                                    "product_id": product_id,
                                    "store_id": store_id,
                                    "risk_level": risk,
                                    "confidence": confidence,
                                    "reorder": reorder
                                })

                    except Exception as e:
                        print("ML error:", e)

                await self.broadcast({
                    "type": "order",
                    "order_id": order_id,
                    "product_id": product_id,
                    "store_id": store_id,
                    "price": price
                })

                order_id += 1
                await asyncio.sleep(random.uniform(1, 3))

            except Exception as e:
                print("Order generation error:", e)
                await asyncio.sleep(3)

    # ===============================
    # SERVER
    # ===============================
    async def handler(self, websocket):
        await self.register(websocket)
        try:
            await websocket.send(json.dumps({
                "type": "connected",
                "message": "Live stream started"
            }))
            async for _ in websocket:
                pass
        finally:
            await self.unregister(websocket)

    async def start(self):
        asyncio.create_task(self.order_generator())
        async with websockets.serve(self.handler, self.host, self.port):
            print(f"🚀 WebSocket running at ws://{self.host}:{self.port}")
            await asyncio.Future()


if __name__ == "__main__":
    stream = WebSocketOrderStream()
    asyncio.run(stream.start())
