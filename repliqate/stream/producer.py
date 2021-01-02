import kafka


class StreamProducerClient(object):
    """
    Client for writing events to a Kafka stream.
    Note that the producer does not provide any idempotency guarantees.
    """

    def __init__(self, brokers, topic):
        """
        Create a producer client.

        :param brokers: List of addresses of Kafka brokers.
        :param topic: Name of the Kafka topic.
        """
        self.producer = kafka.KafkaProducer(bootstrap_servers=brokers)
        self.topic = topic

    def publish(self, message):
        """
        Synchronously publish a single message to the topic.

        :param message: Message bytes.
        """
        # Synchronous for guaranteed consistency to the client
        return self.producer.send(self.topic, message.encode('utf-8')).get()

    def publish_many(self, messages):
        """
        Synchronously publish a batch of messages to the topic.

        :param messages: Iterable of messages to publish.
        """
        # Synchronous for the entire batch
        futures = [
            self.producer.send(self.topic, message)
            for message in messages
        ]

        for future in futures:
            future.get()

    def close(self):
        """
        Gracefully close the connection to the Kafka broker.
        """
        self.producer.close()
