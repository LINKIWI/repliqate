import hashlib
import json
import time


class Message(object):
    """
    Abstraction describing a Kafka message.
    """

    def __init__(self, name, table, data, timestamp=None):
        """
        Create a message.

        :param name: Name of the replication job.
        :param table: Name of the table.
        :param data: JSON-serializable row data.
        :param timestamp: Optional timestamp override..
        """
        self.timestamp = timestamp or time.time()
        self.name = name
        self.table = table
        self.data = data

    def __repr__(self):
        """
        Generate a human-consumable representation of this message.

        :return: String representing this message object.
        """
        return 'Message(timestamp={}, name={}, table={}, data={})'.format(
            self.timestamp,
            self.name,
            self.table,
            dict(self.data),
        )

    def serialize(self):
        """
        Serialize the message into bytes for shipment to Kafka.

        :return: Serialized message bytes.
        """
        return json.dumps({
            # Timestamp at which the message was created by repliqate
            'timestamp': self.timestamp,
            # Name of the replication job
            'name': self.name,
            # Name of the source SQL table
            'table': self.table,
            # Row data serialized as JSON-ish
            'data': dict(self.data),
            # Unique hash of the fetched data
            'hash': self._data_hash(),
        })

    def _data_hash(self):
        """
        Create a deterministic hash of the row data. Used for consumer-side idempotency.

        :return: Bytes representing a checksum of a row's data.
        """
        contents = json.dumps(dict(self.data), sort_keys=True).encode('utf-8')
        return hashlib.sha256(contents).hexdigest()

    @staticmethod
    def deserialize(message):
        """
        Deserialize a message.

        :param message: Serializes message as a string/bytes.
        :return: An instance of Message that represents the serialized input.
        """
        fields = json.loads(message)

        return Message(
            name=fields['name'],
            table=fields['table'],
            data=fields['data'],
            timestamp=fields['timestamp'],
        )
