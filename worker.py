"""
worker.py
─────────
RabbitMQ consumer for cold-start jobs.

Run in a separate terminal alongside the API:
    python worker.py

On startup the worker replicates main.py's lifespan: loads the store, builds
the Jaccard graph and the TF-IDF index. Then it blocks on the queue and
processes one job at a time (prefetch_count=1).

Failure policy (decided in plan):
    OpenAI / pipeline failure → nack(requeue=False), job marked 'failed'.
    No automatic retry — the user resubmits from the UI.
"""

import json
import logging

import pika

from config import COLDSTART_QUEUE, RABBITMQ_URL
from core.coldstart import UserAnswers, get_coldstart_recommendations
from core.supabase_client import get_supabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [worker] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _bootstrap() -> None:
    """Replicate main.py lifespan: load store, build graph + tfidf."""
    from core.store import store
    store.load()

    from core.graph import graph
    graph.build(store.all_items())

    from core.tfidf import tfidf_index
    tfidf_index.build(store.all_items())


def _process(ch, method, properties, body: bytes) -> None:
    job_id = json.loads(body)["job_id"]
    client = get_supabase()
    logger.info("job %s received", job_id)

    try:
        row = (
            client.table("cold_start_jobs")
            .select("answers")
            .eq("id", job_id)
            .single()
            .execute()
        )
        answers = UserAnswers(**row.data["answers"])

        client.table("cold_start_jobs").update(
            {"status": "running", "started_at": "now()"}
        ).eq("id", job_id).execute()

        result = get_coldstart_recommendations(answers)

        client.table("cold_start_jobs").update(
            {
                "status": "completed",
                "signals": {
                    "genres": result.signals.genres,
                    "keywords": result.signals.keywords,
                    "reference_titles": result.signals.reference_titles,
                    "mood": result.signals.mood,
                },
                "seed_ids": result.seed_ids,
                "recommendations": [
                    {"tmdb_id": int(sid), "score": score}
                    for sid, score in result.recommendations
                ],
                "token_cost": {
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                },
                "llm_time_ms": result.llm_time_ms,
                "total_time_ms": result.total_time_ms,
                "completed_at": "now()",
            }
        ).eq("id", job_id).execute()

        logger.info("job %s completed in %.0fms", job_id, result.total_time_ms)
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as exc:
        logger.exception("job %s failed: %s", job_id, exc)
        try:
            client.table("cold_start_jobs").update(
                {
                    "status": "failed",
                    "error_message": str(exc),
                    "completed_at": "now()",
                }
            ).eq("id", job_id).execute()
        except Exception:
            logger.exception("could not record failure for job %s", job_id)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def main() -> None:
    logger.info("bootstrapping store + graph + tfidf...")
    _bootstrap()
    logger.info("bootstrap complete")

    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue=COLDSTART_QUEUE, durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=COLDSTART_QUEUE, on_message_callback=_process)

    logger.info("ready — waiting for jobs on '%s'", COLDSTART_QUEUE)
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        logger.info("shutting down")
        channel.stop_consuming()
    finally:
        connection.close()


if __name__ == "__main__":
    main()
