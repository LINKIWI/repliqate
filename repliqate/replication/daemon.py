import logging
import time
import traceback

from repliqate.db.kv import KeyValueStoreClient
from repliqate.db.sql import SQLDBClient
from repliqate.metrics.hook import NoopMetricsHook
from repliqate.metrics.hook import StatsdMetricsHook
from repliqate.metrics.timer import ExecutionTimer
from repliqate.stream.message import Message
from repliqate.stream.producer import StreamProducerClient


def offset_contention_resolution(primary, secondary):
    """
    In event of a read conflict, always use the latest offset so to minimize re-publishing messages
    that have already been published.

    :param primary: Value read from the primary datastore.
    :param secondary: Value read from the secondary datastore.
    :return: The greater of the two values.
    """
    if primary is None:
        return secondary

    if secondary is None:
        return primary

    if int(primary) > int(secondary):
        return primary

    return secondary


class ReplicationDaemon(object):
    """
    Daemon for periodically executing the main replication routine.
    """

    def __init__(self, config):
        """
        Create a daemon instance from a valid config object.

        :param config: Config instance.
        """
        self.logger = logging.getLogger('repliqate')

        # Parameters
        self.name = config.get('name')
        self.poll_interval = config.get('replication.poll_interval_sec')
        self.sql_table = config.get('replication.sql_source.table')
        self.sql_primary_key = config.get('replication.sql_source.primary_key')
        self.sql_fields = config.get('replication.sql_source.fields')
        self.sql_limit = config.get('replication.sql_source.limit')
        self.kafka_topic = config.get('replication.kafka_target.topic')

        # Clients
        self.db = SQLDBClient(
            db_uri=config.get('replication.sql_source.uri'),
            table=self.sql_table,
        )
        self.kv = KeyValueStoreClient(
            addr=config.get('redis_addr'),
            prefix='repliqate',
            contention_resolution=offset_contention_resolution,
        )
        self.stream = StreamProducerClient(
            brokers=config.get('replication.kafka_target.brokers'),
            topic=self.kafka_topic,
        )

        statsd_addr = config.get('statsd_addr')
        if statsd_addr:
            self.metrics = StatsdMetricsHook(self.name, statsd_addr)
            self.logger.debug(
                'statsd address provided; enabling metrics reporting: addr={}'.format(statsd_addr),
            )
        else:
            self.metrics = NoopMetricsHook()
            self.logger.debug('statsd address omitted; disabling metrics reporting')

        self.logger.info('initialized replication daemon successfully')

    def start(self):
        """
        Start the replication routine, continuing indefinitely.
        """
        self.logger.info('starting daemon: poll_interval_sec={}'.format(self.poll_interval))

        while True:
            try:
                rows, offset = self._replication_fetch_publish()
                self.logger.info(
                    'completed replication iteration: rows={} offset={}'.format(rows, offset)
                )
            except Exception:
                self.logger.error(
                    'encountered error during replication; will abort current iteration'
                )
                traceback.print_exc()

            self.logger.debug(
                'sleeping before next iteration: duration_sec={}'.format(self.poll_interval),
            )
            time.sleep(self.poll_interval)

    def close(self):
        """
        Close active connections.
        """
        self.logger.debug('stopping daemon, closing stateful connections')

        self.db.close()
        self.stream.close()

    def _replication_fetch_publish(self):
        """
        Execute a single iteration of the replication routine.

        :return: A tuple of (number of rows published, new committed offset).
        """
        exec_timer = ExecutionTimer()
        kv_closure = self.kv.closure(
            namespace='replication',
            key='offset',
            tags={'name': self.name, 'table': self.sql_table, 'topic': self.kafka_topic},
        )

        with exec_timer.timer():
            offset = kv_closure.get() or 0
        self.metrics.emit_store_read(success=True, duration=exec_timer.duration())

        try:
            self.logger.debug('querying source with primary key offset: offset={}'.format(offset))

            with exec_timer.timer():
                rows = self.db.query(
                    fields=[self.db.field(field) for field in self.sql_fields],
                    criteria=self.db.field(self.sql_primary_key) > int(offset),
                    limit=self.sql_limit,
                )

            self.metrics.emit_sql_read(
                success=True,
                table=self.sql_table,
                num_rows=len(rows),
                duration=exec_timer.duration(),
            )
        except Exception as e:
            self.logger.error('sql source read failure: exception={}'.format(e))
            self.metrics.emit_sql_read(
                success=False,
                table=self.sql_table,
                num_rows=0,
                duration=exec_timer.duration(),
            )
            raise e

        if not rows:
            self.logger.debug('no new rows since last fetch; aborting')
            return 0, -1

        self.logger.debug('serializing messages from fetched rows: num_rows={}'.format(len(rows)))
        next_offset = -1
        messages = [
            Message(self.name, self.sql_table, row)
            for row in rows
        ]

        for message in messages:
            next_offset = message.data[self.sql_primary_key]

            try:
                self.logger.debug('publishing message: message={}'.format(message))

                with exec_timer.timer():
                    self.stream.publish(message.serialize())

                self.metrics.emit_kafka_publish(
                    success=True,
                    topic=self.kafka_topic,
                    duration=exec_timer.duration(),
                )
            except Exception as e:
                self.logger.error('kafka publication failure: exception={}'.format(e))
                self.metrics.emit_kafka_publish(
                    success=False,
                    topic=self.kafka_topic,
                    duration=exec_timer.duration(),
                )
                raise e

            self.logger.debug('storing next primary key offset: offset={}'.format(next_offset))
            with exec_timer.timer():
                kv_closure.set(next_offset)
            self.metrics.emit_store_write(success=True, duration=exec_timer.duration())
            self.metrics.emit_offset_position(table=self.sql_table, offset=next_offset)

        return len(rows), next_offset
