"""
core/publisher.py
─────────────────
RabbitMQ publisher for cold-start jobs.

Opens a short-lived blocking connection per publish — sufficient for the
expected request rate. Messages are persistent and the queue is durable so
that jobs survive a broker restart.
"""

import json

import pika

from config import COLDSTART_QUEUE, RABBITMQ_URL


def publish_coldstart_job(job_id: str) -> None:
    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    try:
        channel = connection.channel()
        channel.queue_declare(queue=COLDSTART_QUEUE, durable=True)
        channel.basic_publish(
            exchange="",
            routing_key=COLDSTART_QUEUE,
            body=json.dumps({"job_id": job_id}),
            properties=pika.BasicProperties(delivery_mode=2),
        )
    finally:
        connection.close()
