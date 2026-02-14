import asyncio
import websockets
import duckdb
import random
import json
from datetime import datetime

from src.intelligence.ml_predictive_engine import MLPredictiveEngine

DB_PATH = "data/warehouse/retail.duckdb"


class WebSocketOrderStream:

    def __init__(self, host="localhost", port=8765):
        self.host = host
        self.port = port
        self.connected_clients = set()

        # SINGLE WRITE CONNECTION (ONLY ONE IN SYSTEM)
        self.con = duckdb.connect(DB_PATH)
        print("Connected to database.")

        # Attach ML to SAME connection
        self.ml_engine = MLPredictiveEngine(self.con)
        print("ML Engine attached to existing DB connection.")
        print("Auto inventory adjustment + ML enabled.")

    # ===============================
    # CLIENT MANAGEMENT
    # ===============================
    async def register(self, websocket):
        self.connected_clients.add(websocket)

    async def unregister(self, websocket):
        if websocket in self.connected_clients:
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

        order_id = self._get_next_order_id()

        product_ids = [f"P{str(i).zfill(4)}" for i in range(50)]
        store_ids = [f"ST{str(i).zfill(3)}" for i in range(10)]

        while True:
            try:
                product_id = random.choice(product_ids)
                store_id = random.choice(store_ids)
                quantity = random.randint(1, 3)
                price = round(random.uniform(100, 3000), 2)

                # Insert streaming order
                self.con.execute("""
                    INSERT INTO streaming_orders
                    VALUES (?, ?, ?, ?, ?, ?)
                """, [
                    order_id,
                    datetime.now(),
                    product_id,
                    store_id,
                    quantity,
                    price
                ])

                print(f"✓ Order #{order_id} — ₹{price}")

                # ML Stockout Check
                try:
                    self.ml_engine.predict_stockout_with_explanation(
                        product_id,
                        store_id
                    )
                except Exception as e:
                    print("ML error:", e)

                # Broadcast to frontend
                await self.broadcast({
                    "type": "order",
                    "order_id": order_id,
                    "product_id": product_id,
                    "store_id": store_id,
                    "price": price
                })

                order_id += 1

                await asyncio.sleep(random.uniform(1, 2))

            except Exception as e:
                print("Order generation error:", e)
                await asyncio.sleep(2)

    # ===============================
    # GET NEXT ORDER ID
    # ===============================
    def _get_next_order_id(self):
        try:
            result = self.con.execute("""
                SELECT COALESCE(MAX(order_id), 0) + 1
                FROM streaming_orders
            """).fetchone()[0]
            return result
        except:
            return 1

    # ===============================
    # WEBSOCKET HANDLER
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

    # ===============================
    # START SERVER
    # ===============================
    async def start(self):

        asyncio.create_task(self.order_generator())

        async with websockets.serve(self.handler, self.host, self.port):
            print(f"🚀 WebSocket running at ws://{self.host}:{self.port}")
            await asyncio.Future()  # Run forever


# ===============================
# MAIN ENTRY
# ===============================
if __name__ == "__main__":

    stream = WebSocketOrderStream()

    try:
        asyncio.run(stream.start())

    except KeyboardInterrupt:
        print("\nServer stopped cleanly.")

    finally:
        # CLOSE CONNECTION CLEANLY
        try:
            stream.con.close()
            print("Database connection closed.")
        except:
            pass
