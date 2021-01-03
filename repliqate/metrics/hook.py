from repliqate.meta import constants
from repliqate.metrics.stats import StatsdClient


class MetricsHook(object):
    """
    Interface for a metrics hook. Implementations of this interface are invoked elsewhere in the
    application (i.e., "hooked" into various lifecycle points) to trigger metrics emissions.
    """

    def emit_sql_read(self, success, table, num_rows, duration):
        """
        Emit a read event from the source SQL database.

        :param success: True if the read was successful; False otherwise.
        :param table: Name of the table from which rows were read.
        :param num_rows: Number of rows read.
        :param duration: Duration of the read operation.
        """
        raise NotImplementedError

    def emit_kafka_publish(self, success, topic, duration):
        """
        Emit a write event to the target Kafka topic.

        :param success: True if the write was successful; False otherwise.
        :param topic: Name of the Kafka topic.
        :param duration: Duration of the write operation.
        """
        raise NotImplementedError

    def emit_store_read(self, success, duration):
        """
        Emit a read event from the key-value store.

        :param success: True if the read was successful; False otherwise.
        :param duration: Duration of the read operation.
        """
        raise NotImplementedError

    def emit_store_write(self, success, duration):
        """
        Emit a write event to the key-value store.

        :param success: True if the write was successful; False otherwise.
        :param duration: Duration of the write operation.
        """
        raise NotImplementedError

    def emit_offset_position(self, table, offset):
        """
        Emit a gauge indicating the current SQL offset.

        :param table: Name of the source SQL table.
        :param offset: Integer offset of the primary key describing the current replication
                       position.
        """
        raise NotImplementedError


class NoopMetricsHook(MetricsHook):
    """
    MetricsHook implementation that noops on all operations; used when metrics reporting is
    disabled.
    """

    def __init__(self, *args, **kwargs):
        pass

    def emit_sql_read(self, success, table, num_rows, duration):
        pass

    def emit_kafka_publish(self, success, topic, duration):
        pass

    def emit_store_read(self, success, duration):
        pass

    def emit_store_write(self, success, duration):
        pass

    def emit_offset_position(self, table, offset):
        pass


class StatsdMetricsHook(MetricsHook):
    """
    MetricsHook implementation that emits statsd metrics.
    """

    def __init__(self, name, addr):
        """
        Create a StatsdMetricsHook.

        :param name: Name of the repliqate instance.
        :param addr: Address of the statsd listener/server.
        """
        self.statsd = StatsdClient(
            addr=addr,
            prefix='repliqate',
            default_tags={
                'name': name,
                'version': constants.REPLIQATE_VERSION,
            },
        )

    def emit_sql_read(self, success, table, num_rows, duration):
        tags = {'success': str(success).lower(), 'table': table}

        self.statsd.count('source.read', 1, tags)
        self.statsd.timing('source.read_latency', duration, tags)

        if success:
            self.statsd.count('source.rows_read', num_rows, tags)

    def emit_kafka_publish(self, success, topic, duration):
        tags = {'success': str(success).lower(), 'topic': topic}

        self.statsd.count('target.publish', 1, tags)
        self.statsd.timing('target.publish_latency', duration, tags)

    def emit_store_read(self, success, duration):
        tags = {'success': str(success).lower()}

        self.statsd.count('store.read', 1, tags)
        self.statsd.timing('store.read_latency', duration, tags)

    def emit_store_write(self, success, duration):
        tags = {'success': str(success).lower()}

        self.statsd.count('store.write', 1, tags)
        self.statsd.timing('store.write_latency', duration, tags)

    def emit_offset_position(self, table, offset):
        tags = {'table': table}

        self.statsd.gauge('offset.position', offset, tags)
