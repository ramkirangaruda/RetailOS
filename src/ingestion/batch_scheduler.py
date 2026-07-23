from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import asyncio
import duckdb
from datetime import datetime
import logging
from pathlib import Path
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
try:
    from config import DB_PATH
except ImportError:
    DB_PATH = 'data/warehouse/retail.duckdb'

class BatchPipelineScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.setup_logging()
        
        try:
            self.con = duckdb.connect(str(DB_PATH))
            self.setup_monitoring_tables()
        except Exception as e:
            self.logger.error(f"Database setup failed: {e}")
            raise
        
    def setup_logging(self):
        # Create logs directory if it doesn't exist
        Path('logs').mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/batch_pipeline.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('BatchScheduler')
    
    def setup_monitoring_tables(self):
        """Create tables to track pipeline runs"""
        self.con.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            run_id INTEGER PRIMARY KEY,
            pipeline_name VARCHAR,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            status VARCHAR,  -- 'running', 'success', 'failed', 'partial'
            rows_processed INTEGER,
            rows_quarantined INTEGER,
            error_message TEXT,
            duration_seconds INTEGER
        )
        """)
        
        self.con.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_metrics (
            metric_id INTEGER PRIMARY KEY,
            run_id INTEGER,
            metric_name VARCHAR,
            metric_value FLOAT,
            timestamp TIMESTAMP
        )
        """)
    
    async def run_batch_ingestion(self):
        """Execute batch ingestion pipeline"""
        try:
            run_id = self.con.execute("SELECT COALESCE(MAX(run_id), 0) + 1 FROM pipeline_runs").fetchone()[0]
        except:
            run_id = 1
            
        start_time = datetime.now()
        
        self.logger.info(f"Starting batch ingestion run #{run_id}")
        
        # Record run start
        self.con.execute(f"""
        INSERT INTO pipeline_runs VALUES (
            {run_id}, 'batch_ingestion', '{start_time}', NULL, 'running', 0, 0, NULL, 0
        )
        """)
        
        try:
            # Import with error handling to avoid crashes if modules are missing
            try:
                from ingestion.batch_pipeline import (
                    BatchIngestionPipeline,
                    default_schema_registry,
                    run_all as run_all_ingestion,
                )
            except ImportError:
                self.logger.error("Could not import BatchIngestionPipeline")
                raise

            try:
                from transformation.data_cleaning import DataCleaner
            except ImportError:
                self.logger.warning("DataCleaner not found - skipping cleaning step")
                DataCleaner = None

            try:
                from storage.partitioning import partition_fact_sales as partition_all
            except ImportError:
                self.logger.warning("Partitioning module not found - skipping")
                partition_all = None

            from ingestion.adaptive_schema_manager import AdaptiveSchemaManager

            # Stage 1: Ingest all tables. AdaptiveSchemaManager tracks schema
            # drift independently (schema_change_log/schema_approval_queue);
            # it is not yet wired into BatchIngestionPipeline's per-table
            # validation, so we just make sure its tables exist here.
            self.logger.info("Stage 1: Ingesting data...")
            registry = default_schema_registry()
            pipeline = BatchIngestionPipeline(registry)
            schema_manager = AdaptiveSchemaManager()
            schema_manager.initialize_registry()

            ingest_results = run_all_ingestion(pipeline)
            rows_processed = ingest_results['total_rows']
            rows_quarantined = ingest_results['quarantined_rows']

            # Stage 2: Clean data
            if DataCleaner:
                self.logger.info("Stage 2: Cleaning data...")
                cleaner = DataCleaner()
                clean_results = cleaner.run()
            else:
                clean_results = {'duplicates_removed': 0, 'nulls_fixed': 0, 'anomalies_flagged': 0}
            
            # Stage 3: Partition storage
            if partition_all:
                self.logger.info("Stage 3: Partitioning...")
                try:
                    partition_all()
                except Exception as e:
                    self.logger.error(f"Partitioning failed: {e}")
            
            # Mark success
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            self.con.execute(f"""
            UPDATE pipeline_runs 
            SET end_time = '{end_time}',
                status = 'success',
                rows_processed = {rows_processed},
                rows_quarantined = {rows_quarantined},
                duration_seconds = {duration}
            WHERE run_id = {run_id}
            """)
            
            self.logger.info(f"✅ Run #{run_id} completed successfully in {duration:.1f}s")
            
            # Record metrics
            self._record_metrics(run_id, clean_results)
            
            return {'status': 'success', 'run_id': run_id}
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Escape error message for SQL
            error_msg = str(e).replace("'", "''")
            
            self.con.execute(f"""
            UPDATE pipeline_runs 
            SET end_time = '{end_time}',
                status = 'failed',
                duration_seconds = {duration},
                error_message = '{error_msg}'
            WHERE run_id = {run_id}
            """)
            
            self.logger.error(f"❌ Run #{run_id} failed: {str(e)}")
            
            # Alert on failure
            await self.send_failure_alert(run_id, str(e))
            
            return {'status': 'failed', 'run_id': run_id, 'error': str(e)}
    
    async def run_ml_retraining(self):
        """Retrain ML models with latest data.

        MLPredictiveEngine trains its classifier/regressor automatically as
        part of __init__ (see src/intelligence/ml_predictive_engine.py) -
        there is no separate train_stockout_classifier()/
        train_reorder_amount_regressor()/train_demand_forecaster() API (no
        Prophet forecasting is implemented in this codebase either), so
        "retraining" is simply constructing a fresh instance.
        """
        self.logger.info("Starting ML model retraining...")

        try:
            from intelligence.ml_predictive_engine import MLPredictiveEngine

            MLPredictiveEngine()

            self.logger.info("✅ ML retraining completed")

        except Exception as e:
            self.logger.error(f"❌ ML retraining failed: {str(e)}")
    
    def _record_metrics(self, run_id, clean_results):
        """Record pipeline metrics for monitoring"""
        metrics = {
            'duplicates_removed': clean_results.get('duplicates_removed', 0),
            'nulls_fixed': clean_results.get('nulls_fixed', 0),
            'anomalies_flagged': clean_results.get('anomalies_flagged', 0),
            'data_quality_score': clean_results.get('quality_score', 0)
        }
        
        for metric_name, value in metrics.items():
            try:
                self.con.execute(f"""
                INSERT INTO pipeline_metrics VALUES (
                    NULL, {run_id}, '{metric_name}', {value}, CURRENT_TIMESTAMP
                )
                """)
            except Exception as e:
                self.logger.error(f"Failed to record metric {metric_name}: {e}")
    
    async def send_failure_alert(self, run_id, error):
        """Send WhatsApp alert on pipeline failure"""
        try:
            # Placeholder for alert logic
            # from alerts.whatsapp_alerts import send_alert
            pass
        except:
            pass
    
    def setup_schedules(self):
        """Configure all scheduled jobs"""
        
        # Job 1: Batch ingestion every 6 hours
        self.scheduler.add_job(
            self.run_batch_ingestion,
            CronTrigger(hour='*/6'),  # 0:00, 6:00, 12:00, 18:00
            id='batch_ingestion',
            name='Batch Data Ingestion',
            replace_existing=True
        )
        
        # Job 2: ML model retraining daily at 2 AM
        self.scheduler.add_job(
            self.run_ml_retraining,
            CronTrigger(hour=2, minute=0),
            id='ml_retraining',
            name='ML Model Retraining',
            replace_existing=True
        )
        
        # Job 3: Data quality checks every 30 minutes
        self.scheduler.add_job(
            self.check_data_quality,
            IntervalTrigger(minutes=30),
            id='quality_checks',
            name='Data Quality Monitoring',
            replace_existing=True
        )
        
        # Job 4: Cleanup old logs weekly
        self.scheduler.add_job(
            self.cleanup_old_data,
            CronTrigger(day_of_week='sun', hour=3),
            id='cleanup',
            name='Log Cleanup',
            replace_existing=True
        )
        
        self.logger.info("✅ All schedules configured")
    
    async def check_data_quality(self):
        """Monitor data quality metrics"""
        try:
            # Check for anomalies in recent data if table exists
            recent_issues = self.con.execute("""
            SELECT COUNT(*) as issue_count
            FROM quarantine_log
            WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL '30 minutes'
            """).fetchone()[0]
            
            if recent_issues > 100:
                self.logger.warning(f"⚠️ High quarantine rate: {recent_issues} records in last 30 min")
        except:
            pass
    
    async def cleanup_old_data(self):
        """Clean up old logs and temporary data"""
        try:
            self.con.execute("""
            DELETE FROM pipeline_runs 
            WHERE start_time < CURRENT_DATE - INTERVAL '90 days'
            """)
            
            # Optional: Clean quarantine logs if table exists
            try:
                self.con.execute("""
                DELETE FROM quarantine_log 
                WHERE timestamp < CURRENT_DATE - INTERVAL '30 days'
                """)
            except:
                pass
                
            self.logger.info("✅ Old data cleaned up")
        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")
    
    def start(self, test_mode=False):
        """Start the scheduler"""
        if test_mode:
            # Run once immediately for testing
            self.logger.info("🧪 Running in TEST MODE - single execution")
            asyncio.run(self.run_batch_ingestion())
            return

        self.setup_schedules()
        self.scheduler.start()
        self.logger.info("🚀 Batch scheduler started")
        
        try:
            # Run first batch immediately
            asyncio.run(self.run_batch_ingestion())
            
            # Keep running
            asyncio.get_event_loop().run_forever()
        except (KeyboardInterrupt, SystemExit):
            self.scheduler.shutdown()
            self.logger.info("Scheduler stopped")

# Run scheduler
if __name__ == "__main__":
    scheduler = BatchPipelineScheduler()
    scheduler.start()